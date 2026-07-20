"""
Mutation Testing -> Mutation Score (VL11, Folie 42).

Wir injizieren kuenstliche Fehler ("Mutanten") in den Quellcode (z.B. `<` -> `<=`,
`+` -> `-`, `and` -> `or`) und lassen die generierte Test-Suite dagegen laufen.
Wird ein Mutant von der Suite "getoetet" (mindestens ein Test schlaegt fehl), war
die Suite gut genug, den Fehler zu erkennen.

    Mutation Score = getoetete Mutanten / Gesamtzahl Mutanten * 100

Der Mutation Score ist ein deutlich strengeres Guetemass als reine Coverage, da er
nicht nur die *Ausfuehrung*, sondern die tatsaechliche *Pruefung durch Assertions*
misst (VL11).
"""
from __future__ import annotations

import ast

from .models import MutationReport
from .runner import run_suite

# Ersetzungsregeln fuer Vergleichs-, Rechen- und Bool-Operatoren.
_CMP_SWAP = {
    ast.Lt: ast.LtE, ast.LtE: ast.Lt,
    ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
}
_BIN_SWAP = {
    ast.Add: ast.Sub, ast.Sub: ast.Add,
    ast.Mult: ast.Div, ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mult, ast.Mod: ast.Mult,
}
# Augmented Assignments (+=, -=, *=, /=) sind eigene AST-Knoten und muessen
# separat mutiert werden (sonst entgehen uns z.B. `self.balance += amount`).
_AUG_SWAP = _BIN_SWAP
_BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}


class _MutationCollector(ast.NodeVisitor):
    """Sammelt alle moeglichen Mutationsstellen als (kind, per_kind_index).

    Wichtig: Der jeweilige Knoten wird VOR dem Abstieg in seine Kinder gezaehlt
    (Pre-Order). Der Applier muss exakt dieselbe Reihenfolge verwenden.
    """

    def __init__(self):
        self.points: list[tuple[str, int]] = []
        self._counts: dict[str, int] = {}

    def _add(self, kind: str):
        idx = self._counts.get(kind, 0)
        self.points.append((kind, idx))
        self._counts[kind] = idx + 1

    def visit_Compare(self, node):
        for op in node.ops:
            if type(op) in _CMP_SWAP:
                self._add("cmp")
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if type(node.op) in _BIN_SWAP:
            self._add("bin")
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        if type(node.op) in _AUG_SWAP:
            self._add("aug")
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        if type(node.op) in _BOOL_SWAP:
            self._add("bool")
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            self._add("boolconst")
        elif isinstance(node.value, int):
            self._add("intconst")


class _MutationApplier(ast.NodeTransformer):
    """Wendet genau EINE Mutation an: die (kind, target_index)-te ihrer Art.

    Zaehlt pro Art (Pre-Order, identisch zum Collector), damit target_index
    stabil dieselbe Stelle trifft.
    """

    def __init__(self, target_kind: str, target_index: int):
        self.tk = target_kind
        self.ti = target_index
        self._counts: dict[str, int] = {}
        self.applied = False

    def _hit(self, kind: str) -> bool:
        idx = self._counts.get(kind, 0)
        self._counts[kind] = idx + 1
        return kind == self.tk and idx == self.ti

    def visit_Compare(self, node):
        new_ops = []
        for op in node.ops:
            if type(op) in _CMP_SWAP and self._hit("cmp"):
                new_ops.append(_CMP_SWAP[type(op)]())
                self.applied = True
            else:
                new_ops.append(op)
        node.ops = new_ops
        self.generic_visit(node)
        return node

    def visit_BinOp(self, node):
        if type(node.op) in _BIN_SWAP and self._hit("bin"):
            node.op = _BIN_SWAP[type(node.op)]()
            self.applied = True
        self.generic_visit(node)
        return node

    def visit_AugAssign(self, node):
        if type(node.op) in _AUG_SWAP and self._hit("aug"):
            node.op = _AUG_SWAP[type(node.op)]()
            self.applied = True
        self.generic_visit(node)
        return node

    def visit_BoolOp(self, node):
        if type(node.op) in _BOOL_SWAP and self._hit("bool"):
            node.op = _BOOL_SWAP[type(node.op)]()
            self.applied = True
        self.generic_visit(node)
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            if self._hit("boolconst"):
                self.applied = True
                return ast.copy_location(ast.Constant(value=not node.value), node)
        elif isinstance(node.value, int):
            if self._hit("intconst"):
                self.applied = True
                return ast.copy_location(ast.Constant(value=node.value + 1), node)
        return node


def _make_mutant(source: str, kind: str, index: int) -> str | None:
    tree = ast.parse(source)
    applier = _MutationApplier(kind, index)
    mutated = applier.visit(tree)
    if not applier.applied:
        return None
    ast.fix_missing_locations(mutated)
    try:
        return ast.unparse(mutated)
    except Exception:
        return None


def run_mutation_testing(source: str, test_code: str, max_mutants: int = 15,
                         timeout: int = 30) -> MutationReport:
    """Fuehrt Mutation Testing mit der gegebenen Suite durch."""
    report = MutationReport()

    collector = _MutationCollector()
    try:
        collector.visit(ast.parse(source))
    except SyntaxError:
        return report

    points = collector.points
    if not points:
        return report

    # Gleichmaessig ueber die Mutationsstellen samplen, falls es zu viele gibt.
    if len(points) > max_mutants:
        step = len(points) / max_mutants
        selected = [points[int(i * step)] for i in range(max_mutants)]
    else:
        selected = points

    src_norm = source.strip()
    for kind, index in selected:
        mutant_src = _make_mutant(source, kind, index)
        if mutant_src is None or mutant_src.strip() == src_norm:
            continue
        report.total += 1
        try:
            execu, _cov, _dir = run_suite(mutant_src, test_code, timeout=timeout)
        except Exception:
            report.timeout += 1
            report.survived += 1
            continue

        # Mutant "getoetet", wenn die Suite ihn bemerkt (Fehler/Failure/Nicht-Lauf).
        killed = (not execu.compiles) or execu.failed > 0 or execu.errors > 0
        if killed:
            report.killed += 1
        else:
            report.survived += 1
        report.details.append({
            "kind": kind, "index": index, "killed": killed,
            "passed": execu.passed, "failed": execu.failed,
        })

    return report
