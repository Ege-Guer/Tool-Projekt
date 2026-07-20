"""
Datenmodelle (Contract) fuer den Auto Code Reviewer.

Ein `Finding` ist ein einzelner Review-Befund. Der agentische Prozess erzeugt
zunaechst Roh-Findings (Regeln + LLM), verifiziert sie (Reflection) und liefert
am Ende einen `ReviewReport`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

SEVERITIES = ["critical", "high", "medium", "low", "info"]
_SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}
SEVERITY_WEIGHT = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}


@dataclass
class Finding:
    """Ein einzelner Review-Befund."""
    id: str
    line: int
    category: str                     # bug|security|performance|maintainability|smell|style|docs
    severity: str                     # critical|high|medium|low|info
    title: str
    explanation: str
    suggestion: str = ""
    end_line: Optional[int] = None
    source: str = "llm"               # "static" (Regel) | "llm" | "consensus"
    confidence: float = 1.0
    votes: int = 1                    # wie viele Review-Durchlaeufe dieses Finding fanden
    verified: Optional[bool] = None   # None = nicht geprueft, True/False = Reflection-Urteil
    verify_reason: str = ""
    code_snippet: str = ""

    @property
    def severity_rank(self) -> int:
        return _SEV_RANK.get(self.severity, len(SEVERITIES))

    @property
    def weight(self) -> int:
        return SEVERITY_WEIGHT.get(self.severity, 1)

    def dedupe_key(self) -> tuple:
        # Findings gelten als "gleich", wenn Zeile (grob) + Kategorie uebereinstimmen
        return (self.line, self.category)

    def to_dict(self) -> dict:
        return {
            "line": self.line, "severity": self.severity, "category": self.category,
            "title": self.title, "explanation": self.explanation,
            "suggestion": self.suggestion, "source": self.source,
            "votes": self.votes, "verified": self.verified,
        }


@dataclass
class FunctionInfo:
    name: str
    qualname: str
    lineno: int
    end_lineno: int
    num_branches: int
    length: int
    has_docstring: bool


@dataclass
class CodeStructure:
    """Ergebnis der statischen Struktur-Analyse."""
    module_name: str
    source: str
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    loc: int = 0
    num_branches: int = 0
    syntax_ok: bool = True
    syntax_error: Optional[str] = None

    def snippet(self, line: int, context: int = 0) -> str:
        lines = self.source.splitlines()
        i = max(0, line - 1 - context)
        j = min(len(lines), line + context)
        return "\n".join(lines[i:j])


@dataclass
class ReviewReport:
    structure: CodeStructure
    findings: list[Finding] = field(default_factory=list)      # finale (gefilterte) Findings
    raw_findings: list[Finding] = field(default_factory=list)  # vor Verifikation
    repaired_code: Optional[str] = None
    passes: int = 0
    log: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    elapsed: float = 0.0

    # ---- Metriken -------------------------------------------------------- #
    def counts_by_severity(self) -> dict:
        out = {s: 0 for s in SEVERITIES}
        for f in self.findings:
            out[f.severity] = out.get(f.severity, 0) + 1
        return out

    def counts_by_category(self) -> dict:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.category] = out.get(f.category, 0) + 1
        return out

    @property
    def precision(self) -> Optional[float]:
        """Anteil der verifizierten (echten) Findings an allen LLM-Roh-Findings.

        Ein Mass fuer die Wirkung der Reflection/Verifikations-Stufe: wie viele
        der zunaechst gemeldeten LLM-Findings ueberstehen die Selbstkritik.
        """
        llm_raw = [f for f in self.raw_findings if f.source != "static"]
        if not llm_raw:
            return None
        kept = [f for f in llm_raw if f.verified is not False]
        return round(100.0 * len(kept) / len(llm_raw), 1)

    @property
    def risk_score(self) -> int:
        """Gewichteter Risiko-Score (Summe der Schweregrad-Gewichte)."""
        return sum(f.weight for f in self.findings)

    def summary(self) -> dict:
        cs = self.counts_by_severity()
        return {
            "module": self.structure.module_name,
            "total": len(self.findings),
            "critical": cs["critical"], "high": cs["high"], "medium": cs["medium"],
            "low": cs["low"], "info": cs["info"],
            "risk_score": self.risk_score,
            "precision": self.precision,
            "passes": self.passes,
            "elapsed": round(self.elapsed, 1),
        }
