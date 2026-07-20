"""Unit-Tests fuer die Kern-Bausteine von TestPilot (ohne LLM/Netzwerk).

Ausfuehren:  pytest -q   (im Ordner 01-Test-Generation-Tool)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from testpilot.analysis import analyze_source                       # noqa: E402
from testpilot.heuristic import generate_tests                       # noqa: E402
from testpilot.metrics import pass_at_k                              # noqa: E402
from testpilot.mutation import _MutationCollector, _make_mutant      # noqa: E402
from testpilot.models import TestCandidate, TestExecution, CoverageReport  # noqa: E402
from testpilot import pareto                                         # noqa: E402
import ast                                                           # noqa: E402


# ---- Analyse ------------------------------------------------------------- #
def test_analysis_finds_callables_and_branches():
    src = "def f(x):\n    if x > 0:\n        return 1\n    return 0\n"
    a = analyze_source(src)
    assert a.syntax_ok
    assert any(u.name == "f" for u in a.units)
    assert a.num_branches >= 1


def test_analysis_reports_syntax_error():
    a = analyze_source("def f(:\n")
    assert not a.syntax_ok and a.syntax_error


# ---- Heuristik-Generator ------------------------------------------------- #
def test_heuristic_generates_valid_python():
    src = "def add(a, b):\n    return a + b\n"
    code = generate_tests(analyze_source(src))
    ast.parse(code)                       # muss parsebar sein
    assert "def test_" in code


# ---- pass@k -------------------------------------------------------------- #
def test_pass_at_k_bounds():
    assert pass_at_k(5, 0, 1) == 0.0      # keine korrekte Stichprobe
    assert pass_at_k(5, 5, 1) == 1.0      # alle korrekt
    assert 0.0 < pass_at_k(5, 1, 1) < 1.0


# ---- Mutation-Engine ----------------------------------------------------- #
def test_mutation_collector_and_apply():
    src = "def f(a, b):\n    return a + b\n"
    coll = _MutationCollector()
    coll.visit(ast.parse(src))
    assert coll.points                     # mindestens eine Mutationsstelle
    kind, idx = coll.points[0]
    mutant = _make_mutant(src, kind, idx)
    assert mutant and mutant.strip() != src.strip()


# ---- Pareto / NSGA-II ---------------------------------------------------- #
def _cand(cid, branch, ntests):
    c = TestCandidate(id=cid, code="", strategy="x", num_tests=ntests)
    c.execution = TestExecution(passed=ntests, failed=0, collected=ntests)
    c.coverage = CoverageReport(branch_percent=branch, num_branches=10,
                                covered_branches=int(branch / 10))
    return c


def test_pareto_front_is_non_dominated():
    # A: hohe Coverage viele Tests; B: mittlere Coverage wenige Tests -> beide non-dominiert
    # C: schlechter als A in beidem -> dominiert
    a = _cand("A", 90, 10)
    b = _cand("B", 60, 3)
    c = _cand("C", 50, 12)
    front = pareto.pareto_front([a, b, c])
    ids = {x.id for x in front}
    assert "A" in ids and "B" in ids and "C" not in ids


def test_dominance_relation():
    strong = _cand("s", 90, 3)
    weak = _cand("w", 80, 5)
    assert pareto.dominates(strong, weak)
    assert not pareto.dominates(weak, strong)
