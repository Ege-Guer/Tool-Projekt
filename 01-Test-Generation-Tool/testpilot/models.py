"""
Zentrale Datenmodelle (Contract) fuer TestPilot.

Alle Module (Analyse, Runner, Agent, Pareto, Mutation, UI) tauschen ausschliesslich
diese Dataclasses aus. Dadurch bleibt die Architektur entkoppelt: die UI kennt nur
diese Objekte, nicht die Interna der einzelnen Schritte.

Bezug zur Vorlesung: Die Test-Suite wird als "Individuum" im Sinne der
Search-Based Software Engineering (SBSE) betrachtet. Ein `TestCandidate` ist ein
Loesungskandidat, dessen "Fitness" durch Coverage / bestandene Tests / Groesse
ausgedrueckt wird (VL6/VL7).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# --------------------------------------------------------------------------- #
# 1. Analyse des zu testenden Codes
# --------------------------------------------------------------------------- #
@dataclass
class SourceUnit:
    """Eine testbare Einheit (Funktion oder Methode) im Quellcode.

    Entspricht den "Callables" aus der SBST-Pipeline (VL11): alle Methoden und
    Funktionen, die aufgerufen werden koennen.
    """
    name: str
    qualname: str            # z.B. "BankAccount.withdraw"
    kind: str                # "function" | "method"
    signature: str           # z.B. "(self, amount: float) -> None"
    docstring: Optional[str]
    lineno: int
    end_lineno: int
    source: str              # Quelltext der Einheit (fuer den Prompt-Kontext)
    num_branches: int = 0    # Anzahl Verzweigungen in dieser Einheit


@dataclass
class CodeAnalysis:
    """Ergebnis der statischen Analyse eines Moduls (siehe analysis.py)."""
    module_name: str
    source: str
    units: list[SourceUnit] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    num_branches: int = 0            # Verzweigungen im gesamten Modul
    num_statements: int = 0
    syntax_ok: bool = True
    syntax_error: Optional[str] = None

    @property
    def callable_names(self) -> list[str]:
        return [u.qualname for u in self.units]


# --------------------------------------------------------------------------- #
# 2. Ausfuehrung & Coverage
# --------------------------------------------------------------------------- #
@dataclass
class CoverageReport:
    """Coverage-Ergebnis von coverage.py (Line + Branch Coverage).

    Branch Coverage ist laut VL11 (Folie 16) das zentrale Evaluationskriterium:
    Prozentsatz der durch die Tests ausgefuehrten Verzweigungen (if/switch...).
    """
    line_percent: float = 0.0
    branch_percent: float = 0.0
    covered_lines: int = 0
    num_statements: int = 0
    covered_branches: int = 0
    num_branches: int = 0
    missing_lines: list[int] = field(default_factory=list)
    missing_branches: list[list[int]] = field(default_factory=list)

    @property
    def combined_percent(self) -> float:
        """Kombiniertes Mass aus Line- und Branch-Coverage (fuer Anzeige)."""
        if self.num_branches > 0:
            return round((self.line_percent + self.branch_percent) / 2, 1)
        return round(self.line_percent, 1)


@dataclass
class TestExecution:
    """Ergebnis eines pytest-Laufs einer Test-Suite."""
    __test__ = False  # kein pytest-Testobjekt (Name beginnt nur zufaellig mit 'Test')
    passed: int = 0
    failed: int = 0
    errors: int = 0
    collected: int = 0
    collect_error: bool = False       # Suite konnte nicht importiert/gesammelt werden
    duration: float = 0.0             # Laufzeit in Sekunden (Objective 2 fuer Pareto)
    stdout: str = ""
    stderr: str = ""
    failure_messages: list[str] = field(default_factory=list)

    @property
    def compiles(self) -> bool:
        """'Kompilierungsrate' (VL11): laeuft die Suite ueberhaupt (importierbar)?"""
        return not self.collect_error and self.errors == 0

    @property
    def total_tests(self) -> int:
        return self.passed + self.failed

    @property
    def correctness(self) -> float:
        """Anteil bestandener Tests (VL11: 'Korrektheit')."""
        if self.total_tests == 0:
            return 0.0
        return round(100.0 * self.passed / self.total_tests, 1)


# --------------------------------------------------------------------------- #
# 3. Test-Kandidat (= Individuum im SBSE-Sinn)
# --------------------------------------------------------------------------- #
@dataclass
class TestCandidate:
    """Eine komplette pytest-Datei als Loesungskandidat.

    `objectives` fuer die Multi-Objective-Optimierung (VL7):
      * maximiere Branch Coverage
      * minimiere Anzahl Tests (bzw. Laufzeit)
    """
    __test__ = False  # kein pytest-Testobjekt (Name beginnt nur zufaellig mit 'Test')
    id: str
    code: str
    strategy: str                     # "zero-shot" | "feedback" | "heuristic" | "hybrid"
    iteration: int = 0
    num_tests: int = 0
    execution: Optional[TestExecution] = None
    coverage: Optional[CoverageReport] = None

    # ---- Fitness / Objectives ------------------------------------------- #
    @property
    def branch_cov(self) -> float:
        return self.coverage.branch_percent if self.coverage else 0.0

    @property
    def line_cov(self) -> float:
        return self.coverage.line_percent if self.coverage else 0.0

    @property
    def passing_tests(self) -> int:
        return self.execution.passed if self.execution else 0

    @property
    def runtime(self) -> float:
        return self.execution.duration if self.execution else 0.0

    @property
    def is_valid(self) -> bool:
        """Nur lauffaehige Suiten mit >=1 bestandenen Test kommen ins Archiv."""
        return bool(self.execution and self.execution.compiles and self.passing_tests > 0)

    def fitness(self, w_line: float = 0.5, w_branch: float = 0.5) -> float:
        """Skalare Fitness fuer die einzielige Suche (Agent-Loop).

        Wichtig (VL7, Folie 24): die Fitness muss die Suche *leiten* – eine reine
        0/1-Bewertung ("crasht / crasht nicht") reicht nicht. Deshalb kombinieren wir
        Line- und Branch-Coverage zu einem kontinuierlichen Wert.
        """
        cov = w_line * self.line_cov + w_branch * self.branch_cov
        # kleiner Bonus fuer bestandene Tests, kleine Strafe fuer fehlgeschlagene
        if self.execution:
            fails = self.execution.failed + self.execution.errors
            cov += 0.2 * self.passing_tests - 0.5 * fails
        return round(cov, 3)

    def objectives(self) -> tuple[float, float]:
        """(minimierbares) Objective-Tupel fuer Pareto: (-branch_cov, num_tests).

        Beide Werte werden minimiert -> hohe Coverage (negiert) und wenige Tests
        sind gut. Entspricht dem Beispiel aus VL7 (Folie 57): Branch Coverage
        maximieren, Ausfuehrungszeit / Testanzahl minimieren.
        """
        return (-self.branch_cov, float(self.num_tests))


# --------------------------------------------------------------------------- #
# 4. Iterationen & Gesamtergebnis
# --------------------------------------------------------------------------- #
@dataclass
class IterationRecord:
    """Protokoll einer einzelnen Iteration des Agent-Loops (fuer die Live-Anzeige)."""
    iteration: int
    strategy: str
    branch_cov: float
    line_cov: float
    passed: int
    failed: int
    num_tests: int
    fitness: float
    note: str = ""
    accepted: bool = False            # hat diese Iteration den Best-Kandidaten verbessert?


@dataclass
class MutationReport:
    """Ergebnis des Mutation Testings (VL11, Folie 42)."""
    total: int = 0
    killed: int = 0
    survived: int = 0
    timeout: int = 0
    details: list[dict] = field(default_factory=list)

    @property
    def score(self) -> float:
        if self.total == 0:
            return 0.0
        return round(100.0 * self.killed / self.total, 1)


@dataclass
class RunReport:
    """Vollstaendiges Ergebnis eines Generierungslaufs."""
    analysis: CodeAnalysis
    iterations: list[IterationRecord] = field(default_factory=list)
    best: Optional[TestCandidate] = None
    archive: list[TestCandidate] = field(default_factory=list)
    pareto_front: list[TestCandidate] = field(default_factory=list)
    mutation: Optional[MutationReport] = None
    pass_at_k: Optional[dict] = None          # {"k": 1, "value": 0.8, "n": 5, "c": 4}
    config: dict = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    elapsed: float = 0.0

    def summary(self) -> dict:
        best = self.best
        return {
            "module": self.analysis.module_name,
            "iterations": len(self.iterations),
            "branch_cov": best.branch_cov if best else 0.0,
            "line_cov": best.line_cov if best else 0.0,
            "num_tests": best.num_tests if best else 0,
            "passing": best.passing_tests if best else 0,
            "mutation_score": self.mutation.score if self.mutation else None,
            "archive_size": len(self.archive),
            "pareto_size": len(self.pareto_front),
            "elapsed": round(self.elapsed, 1),
        }
