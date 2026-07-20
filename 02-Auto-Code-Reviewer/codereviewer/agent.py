"""
Der agentische Code-Reviewer (Orchestrator).

Ablauf (verbindet VL8 Agentic AI mit VL11 Testgenerierung/Program Repair):

  1. Kontext-Beschaffung / Tool-Usage: statische AST-Analyse + Regelpruefung
     liefern gegroundete Findings (wie CoverUp/AutoCodeRover Kontext sammeln).
  2. Zero-Shot-Review durch das LLM, mehrfach (Self-Consistency, VL5): mehrere
     Durchlaeufe, deren Findings zusammengefuehrt werden (Mehrheit => Konsens).
  3. Reflection / Kritiker-Agent (VL8): jedes LLM-Finding wird adversarial
     verifiziert (echt oder Falsch-Positiv?). Erhoeht die Precision.
  4. Program Repair (VL11, optional): das LLM erzeugt eine korrigierte Version
     des Codes fuer die bestaetigten Findings.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from .config import RunConfig, SEVERITY_RANK
from .models import CodeStructure, Finding, ReviewReport
from .analysis import analyze_source
from . import rules, prompts
from .llm import LLMClient, LLMError

EventCb = Optional[Callable[[dict], None]]

_ALLOWED_CAT = {"bug", "security", "performance", "maintainability", "smell", "style", "docs"}
_ALLOWED_SEV = {"critical", "high", "medium", "low", "info"}


class ReviewAgent:
    def __init__(self, config: RunConfig, on_event: EventCb = None):
        self.config = config.resolve()
        self.on_event = on_event
        self.log: list[str] = []
        self._llm: Optional[LLMClient] = None

    # ------------------------------------------------------------------ #
    def _emit(self, type_: str, **data):
        self.on_event and self.on_event({"type": type_, **data})

    def _say(self, msg: str):
        self.log.append(msg)
        self._emit("log", msg=msg)

    def _client(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient(self.config)
        return self._llm

    # ------------------------------------------------------------------ #
    def _parse_findings(self, data, pass_idx: int, struct: CodeStructure) -> list[Finding]:
        out: list[Finding] = []
        if not isinstance(data, list):
            return out
        max_line = max(1, struct.loc)
        for k, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            try:
                line = int(item.get("line", 0))
            except (TypeError, ValueError):
                line = 0
            line = min(max(line, 1), max_line)
            cat = str(item.get("category", "smell")).lower()
            sev = str(item.get("severity", "low")).lower()
            if cat not in _ALLOWED_CAT:
                cat = "smell"
            if sev not in _ALLOWED_SEV:
                sev = "low"
            title = str(item.get("title", "")).strip()[:160]
            if not title:
                continue
            out.append(Finding(
                id=f"llm-{pass_idx}-{k}", line=line, category=cat, severity=sev,
                title=title,
                explanation=str(item.get("explanation", "")).strip()[:600],
                suggestion=str(item.get("suggestion", "")).strip()[:600],
                source="llm", confidence=0.7, votes=1,
                code_snippet=struct.snippet(line),
            ))
        return out

    def _review_passes(self, struct: CodeStructure, static: list[Finding]) -> list[Finding]:
        client = self._client()
        prompt = prompts.review_prompt(struct, static)
        collected: list[Finding] = []
        n = max(1, self.config.passes)
        for i in range(n):
            self._say(f"LLM-Review Durchlauf {i + 1}/{n} ({self.config.model}) ...")
            # leichte Temperatur-Variation fuer Diversitaet (Self-Consistency, VL5)
            temp = self.config.temperature + (0.15 * i if n > 1 else 0)
            data = client.complete_json(prompts.REVIEW_SYSTEM, prompt, temperature=temp)
            found = self._parse_findings(data, i, struct)
            self._say(f"  -> {len(found)} Findings in Durchlauf {i + 1}.")
            collected.extend(found)
        return collected

    def _merge(self, findings: list[Finding]) -> list[Finding]:
        """Dedupliziert nach (Zeile, Kategorie); zaehlt Stimmen (Self-Consistency)."""
        buckets: dict[tuple, Finding] = {}
        for f in findings:
            key = f.dedupe_key()
            if key in buckets:
                ex = buckets[key]
                ex.votes += f.votes
                if f.severity_rank < ex.severity_rank:
                    ex.severity, ex.title = f.severity, f.title
                    ex.explanation, ex.suggestion = f.explanation, f.suggestion
                if f.source == "static":       # Regel-Finding "gewinnt" das Label
                    ex.source = "static"
                    ex.confidence = 1.0
            else:
                buckets[key] = f
        result = list(buckets.values())
        for f in result:
            if f.source == "llm" and f.votes > 1:
                f.source = "consensus"
                f.confidence = min(1.0, 0.6 + 0.15 * f.votes)
        return result

    def _verify(self, struct: CodeStructure, findings: list[Finding]):
        """Reflection/Kritiker: markiert LLM-Findings als verified True/False."""
        to_check = [f for f in findings if f.source in ("llm", "consensus")]
        if not to_check:
            return
        self._say(f"Reflection/Verifikation: pruefe {len(to_check)} LLM-Findings "
                  "adversarial (Falsch-Positive aussortieren) ...")
        client = self._client()
        data = client.complete_json(prompts.VERIFY_SYSTEM,
                                    prompts.verify_prompt(struct, to_check),
                                    temperature=0.0)
        verdicts = {}
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "id" in item:
                    verdicts[str(item["id"])] = item
        kept, dropped = 0, 0
        for f in to_check:
            v = verdicts.get(f.id)
            if v is None:
                f.verified = True       # ohne Urteil im Zweifel behalten
                kept += 1
                continue
            verdict = str(v.get("verdict", "keep")).lower()
            f.verify_reason = str(v.get("reason", ""))[:300]
            if verdict == "discard":
                f.verified = False
                dropped += 1
            else:
                f.verified = True
                kept += 1
        self._say(f"  -> {kept} bestaetigt, {dropped} als Falsch-Positiv verworfen.")

    def _repair(self, struct: CodeStructure, findings: list[Finding]) -> Optional[str]:
        import ast
        self._say("Program Repair: erzeuge korrigierte Code-Version ...")
        try:
            code = self._client().complete_code(prompts.REPAIR_SYSTEM,
                                                prompts.repair_prompt(struct, findings))
        except LLMError as exc:
            self._say(f"  -> Repair fehlgeschlagen: {exc}")
            return None
        if not code:
            return None
        try:
            ast.parse(code)
        except SyntaxError as exc:
            self._say(f"  -> verworfen: korrigierter Code hat Syntaxfehler ({exc.msg}).")
            return None
        self._say("  -> korrigierte Version erzeugt (Syntax ok).")
        return code

    # ------------------------------------------------------------------ #
    def run(self, source: str, module_name: str = "module") -> ReviewReport:
        start = time.time()
        struct = analyze_source(source, module_name)
        report = ReviewReport(structure=struct, config=self.config.redacted())

        if not struct.syntax_ok:
            self._say(f"Syntaxfehler: {struct.syntax_error}")
            report.findings = [Finding(
                id="syntax", line=1, category="bug", severity="critical",
                title="SyntaxError – Code laesst sich nicht parsen",
                explanation=struct.syntax_error or "",
                suggestion="Behebe den Syntaxfehler, dann erneut reviewen.",
                source="static")]
            report.raw_findings = list(report.findings)
            report.log = self.log
            report.elapsed = time.time() - start
            self._emit("done", report=report)
            return report

        self._emit("phase", msg="statische Analyse")
        static_findings = rules.analyze(struct)
        self._say(f"Statische Analyse: {len(static_findings)} regelbasierte Findings "
                  f"in {len(struct.functions)} Funktionen.")

        cfg = self.config
        raw: list[Finding] = list(static_findings)
        llm_used = False

        if cfg.strategy in ("llm", "agentic") and not cfg.is_offline:
            self._emit("phase", msg="LLM-Review")
            try:
                llm_findings = self._review_passes(struct, static_findings)
                raw.extend(llm_findings)
                llm_used = True
            except LLMError as exc:
                self._say(f"LLM nicht verfuegbar ({exc}). Nutze nur die Regel-Findings.")

        merged = self._merge(raw)
        report.raw_findings = merged

        if cfg.strategy == "agentic" and cfg.run_verification and llm_used:
            self._emit("phase", msg="Reflection/Verifikation")
            self._verify(struct, merged)

        # Finale Findings: Regeln immer, LLM-Findings nur wenn nicht verworfen
        threshold = SEVERITY_RANK.get(cfg.min_severity, len(SEVERITY_RANK))
        final = [f for f in merged
                 if (f.source == "static" or f.verified is not False)
                 and f.severity_rank <= threshold]
        final.sort(key=lambda f: (f.severity_rank, -f.votes, f.line))
        report.findings = final
        report.passes = cfg.passes if llm_used else 0

        if cfg.run_repair and llm_used and final:
            self._emit("phase", msg="Program Repair")
            report.repaired_code = self._repair(struct, final)

        report.log = self.log
        report.elapsed = time.time() - start
        self._say(f"Fertig: {len(final)} Findings (Risk-Score {report.risk_score}).")
        self._emit("done", report=report)
        return report


def review(source: str, config: RunConfig, on_event: EventCb = None,
           module_name: str = "module") -> ReviewReport:
    """Bequeme Funktions-API fuer die UI."""
    return ReviewAgent(config, on_event).run(source, module_name)
