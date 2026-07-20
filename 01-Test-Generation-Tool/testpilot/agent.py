"""
Der agentische Test-Generator (Orchestrator).

Setzt die Kernidee aus VL11 (TestForge / CoverUp) um und verbindet sie mit den
Konzepten aus SBSE (VL6/7) und Agentic AI (VL8):

  1.  Zero-Shot: erster LLM-Entwurf mit reichem Kontext (VL11, Folie 14).
  2.  Agentic Feedback-Loop (ReAct: Observe -> Reason -> Act, VL8):
        - Observe: Suite ausfuehren, Coverage & Fehler messen (Fitness-Evaluation)
        - Reason:  Feedback-Prompt aus nicht abgedeckten Zeilen/Branches + Fehlern
        - Act:     LLM erzeugt eine verbesserte Suite (Reflection-Pattern, VL8)
  3.  Die Coverage ist die Fitness-Funktion, die die Suche leitet (VL7, Folie 24):
      ein kontinuierlicher Wert statt 0/1, damit die Suche nicht zur
      "Nadel im Heuhaufen" wird.
  4.  Alle validen Suiten wandern ins Archiv (vgl. SBST-Archiv, VL11, Folie 23),
      aus dem am Ende die Pareto-Front (NSGA-II) bestimmt wird.
  5.  Stopp-Kriterium: Ziel-Coverage erreicht, Plateau, oder Iterationsbudget T.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from .config import RunConfig
from .models import (CodeAnalysis, IterationRecord, RunReport, TestCandidate)
from .analysis import analyze_source
from .runner import run_suite, quick_syntax_check
from . import prompts, pareto, mutation, metrics
from .llm import LLMClient, LLMError
from .heuristic import generate_tests as heuristic_tests

EventCb = Optional[Callable[[dict], None]]


def _count_tests(code: str) -> int:
    import re
    return len(re.findall(r"^\s*def test_", code, re.MULTILINE))


class TestPilotAgent:
    def __init__(self, config: RunConfig, on_event: EventCb = None):
        self.config = config.resolve()
        self.on_event = on_event
        self.archive: list[TestCandidate] = []
        self.iterations: list[IterationRecord] = []
        self.log: list[str] = []
        self._llm: Optional[LLMClient] = None

    # ------------------------------------------------------------------ #
    # Hilfsfunktionen
    # ------------------------------------------------------------------ #
    def _emit(self, type_: str, **data):
        self.on_event and self.on_event({"type": type_, **data})

    def _say(self, msg: str):
        self.log.append(msg)
        self._emit("log", msg=msg)

    def _llm_client(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient(self.config)
        return self._llm

    def _evaluate(self, code: str, strategy: str, iteration: int,
                  sample: int = 0) -> TestCandidate:
        """Fuehrt Fitness-Evaluation durch: Syntaxcheck -> pytest+coverage."""
        cand = TestCandidate(
            id=f"{strategy}-i{iteration}-s{sample}",
            code=code, strategy=strategy, iteration=iteration,
            num_tests=_count_tests(code),
        )
        syn = quick_syntax_check(code)
        if syn is not None:
            from .models import TestExecution
            cand.execution = TestExecution(collect_error=True, stderr=syn)
            from .models import CoverageReport
            cand.coverage = CoverageReport()
            return cand

        # run_suite(source_code, test_code) -> Fitness-Evaluation
        execu, cov, _ = run_suite(self.source, code, timeout=self.config.pytest_timeout)
        cand.execution = execu
        cand.coverage = cov
        if execu.collected:
            cand.num_tests = execu.collected
        return cand

    def _record(self, cand: TestCandidate, note: str, accepted: bool):
        rec = IterationRecord(
            iteration=cand.iteration, strategy=cand.strategy,
            branch_cov=cand.branch_cov, line_cov=cand.line_cov,
            passed=cand.passing_tests,
            failed=(cand.execution.failed + cand.execution.errors) if cand.execution else 0,
            num_tests=cand.num_tests, fitness=cand.fitness(self.config.w_line, self.config.w_branch),
            note=note, accepted=accepted,
        )
        self.iterations.append(rec)
        self._emit("iteration", record=rec)

    def _add_to_archive(self, cand: TestCandidate):
        if cand.is_valid:
            self.archive.append(cand)

    # ------------------------------------------------------------------ #
    # Generierungs-Bausteine
    # ------------------------------------------------------------------ #
    def _heuristic_candidate(self, iteration: int) -> TestCandidate:
        self._say("Heuristik (SBST-Baseline): generiere Tests aus AST-Analyse ...")
        code = heuristic_tests(self.analysis)
        return self._evaluate(code, "heuristic", iteration)

    def _zero_shot(self) -> list[TestCandidate]:
        """Zero-Shot-Erstwurf, ggf. mehrere Stichproben fuer pass@k."""
        client = self._llm_client()
        prompt = prompts.zero_shot_prompt(self.analysis)
        cands: list[TestCandidate] = []
        for s in range(max(1, self.config.samples_per_step)):
            self._say(f"Zero-Shot LLM-Anfrage (Stichprobe {s + 1}/"
                      f"{self.config.samples_per_step}) an {self.config.model} ...")
            code = client.generate_tests(prompts.SYSTEM_PROMPT, prompt)
            if not code:
                self._say("  -> Modell lieferte keinen Codeblock, ueberspringe.")
                continue
            cand = self._evaluate(code, "zero-shot", 0, sample=s)
            cands.append(cand)
            self._record(cand, "Zero-Shot", accepted=False)
            self._add_to_archive(cand)
        return cands

    def _feedback_step(self, best: TestCandidate, iteration: int) -> TestCandidate:
        client = self._llm_client()
        prompt = prompts.feedback_prompt(best, self.analysis)
        self._say(f"Iteration {iteration}: Feedback-Prompt (Coverage/Fehler) an LLM ...")
        code = client.generate_tests(prompts.SYSTEM_PROMPT, prompt)
        if not code:
            # Fallback: alten Code behalten
            code = best.code
        return self._evaluate(code, "feedback", iteration)

    # ------------------------------------------------------------------ #
    # Hauptablauf
    # ------------------------------------------------------------------ #
    def run(self, source: str, module_name: str = "module_under_test") -> RunReport:
        start = time.time()
        self.source = source
        self.analysis: CodeAnalysis = analyze_source(source, module_name)

        report = RunReport(analysis=self.analysis, config=self.config.redacted())

        if not self.analysis.syntax_ok:
            self._say(f"Syntaxfehler im Quellcode: {self.analysis.syntax_error}")
            report.log = self.log
            report.elapsed = time.time() - start
            return report

        self._emit("phase", msg="analyse")
        self._say(f"Analyse: {len(self.analysis.units)} Callables, "
                  f"~{self.analysis.num_branches} Verzweigungen erkannt.")

        cfg = self.config
        best: Optional[TestCandidate] = None
        zero_shot_samples: list[TestCandidate] = []

        # -------------------------------------------------------------- #
        # Strategie: heuristisch (offline) ODER llm/hybrid
        # -------------------------------------------------------------- #
        use_llm = cfg.strategy in ("llm", "hybrid") and not cfg.is_offline

        # Hybrid & (fallback) immer: eine Heuristik-Baseline erzeugen
        if cfg.strategy == "hybrid" or cfg.strategy == "heuristic" or not use_llm:
            try:
                hcand = self._heuristic_candidate(0)
                self._record(hcand, "Heuristik-Baseline", accepted=True)
                self._add_to_archive(hcand)
                best = hcand
            except Exception as exc:
                self._say(f"Heuristik fehlgeschlagen: {exc}")

        # LLM-gestuetzte Generierung
        if use_llm:
            self._emit("phase", msg="zero-shot")
            try:
                zero_shot_samples = self._zero_shot()
                for cand in zero_shot_samples:
                    if best is None or cand.fitness() > best.fitness():
                        best = cand
            except LLMError as exc:
                self._say(f"LLM nicht verfuegbar ({exc}). Nutze Heuristik-Baseline.")
                use_llm = False

        # -------------------------------------------------------------- #
        # Agentic Feedback-Loop (nur mit LLM)
        # -------------------------------------------------------------- #
        if use_llm and best is not None:
            self._emit("phase", msg="feedback-loop")
            patience, no_improve = 2, 0
            for it in range(1, cfg.max_iterations + 1):
                # Stopp-Kriterium: Ziel-Coverage erreicht
                if best.branch_cov >= cfg.target_coverage and best.line_cov >= cfg.target_coverage:
                    self._say(f"Ziel-Coverage {cfg.target_coverage:.0f}% erreicht "
                              f"-> Stopp nach Iteration {it - 1}.")
                    break
                try:
                    cand = self._feedback_step(best, it)
                except LLMError as exc:
                    self._say(f"LLM-Fehler in Iteration {it}: {exc} -> Abbruch der Schleife.")
                    break

                improved = cand.is_valid and cand.fitness() > best.fitness()
                self._add_to_archive(cand)
                self._record(cand, "Feedback-Iteration", accepted=improved)

                if improved:
                    delta = cand.branch_cov - best.branch_cov
                    self._say(f"  -> Verbesserung: Branch {best.branch_cov:.0f}% "
                              f"-> {cand.branch_cov:.0f}% (Fitness {cand.fitness():.2f}).")
                    best = cand
                    no_improve = 0
                else:
                    no_improve += 1
                    self._say(f"  -> keine Verbesserung ({no_improve}/{patience}).")
                    if no_improve >= patience:
                        self._say("Plateau erkannt -> Stopp (vgl. CodaMosa "
                                  "'coverage plateau').")
                        break

        # -------------------------------------------------------------- #
        # Nachbereitung: Bestes waehlen, Pareto, Mutation, pass@k
        # -------------------------------------------------------------- #
        if self.archive:
            best = max(self.archive, key=lambda c: c.fitness(cfg.w_line, cfg.w_branch))
        report.best = best
        report.archive = self.archive
        report.iterations = self.iterations
        report.log = self.log

        if cfg.run_pareto and self.archive:
            self._emit("phase", msg="pareto")
            report.pareto_front = pareto.pareto_front(self.archive)
            self._say(f"Pareto-Front (NSGA-II): {len(report.pareto_front)} "
                      f"nicht-dominierte Suiten von {len(self.archive)} im Archiv.")

        if zero_shot_samples:
            report.pass_at_k = metrics.compute_pass_at_k(zero_shot_samples)

        if cfg.run_mutation and best and best.is_valid:
            self._emit("phase", msg="mutation")
            self._say("Mutation Testing: injiziere Fehler und pruefe, ob die "
                      "Suite sie erkennt ...")
            report.mutation = mutation.run_mutation_testing(
                self.source, best.code, timeout=min(30, cfg.pytest_timeout))
            self._say(f"Mutation Score: {report.mutation.score:.0f}% "
                      f"({report.mutation.killed}/{report.mutation.total} Mutanten getoetet).")

        report.elapsed = time.time() - start
        self._emit("done", report=report)
        return report


def generate(source: str, config: RunConfig, on_event: EventCb = None,
             module_name: str = "module_under_test") -> RunReport:
    """Bequeme Funktions-API fuer die UI."""
    return TestPilotAgent(config, on_event).run(source, module_name)
