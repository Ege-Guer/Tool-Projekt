"""
Offline-Testgenerator (SBST-Baseline, ohne LLM).

Erzeugt aus der statischen AST-Analyse "Smoke-/Charakterisierungs-Tests": jede
Callable wird mit einer Reihe heuristisch gewaehlter Eingaben (Grenzwerte,
typische Werte je nach Type-Hint) aufgerufen. Das entspricht der zufaelligen
Testfall-Generierung der SBST-Pipeline (VL11, Folie 22) bzw. Werkzeugen wie
Pynguin.

Bewusst OHNE Ausfuehrung des Nutzercodes im selben Prozess (Sicherheit / keine
Endlosschleifen). Deshalb pruefen die Tests vor allem, dass der Code laeuft
(Coverage) und deterministisch ist. Das illustriert zugleich einen wichtigen
Punkt aus VL11: hohe Coverage bedeutet nicht automatisch hohe Testguete – die
schwaecheren Assertions dieser Baseline zeigen sich spaeter an einem niedrigeren
Mutation Score als bei den LLM-Tests.
"""
from __future__ import annotations

import ast

from .models import CodeAnalysis
from .runner import MODULE_NAME

# Wertepools je (grob erkanntem) Typ – dienen als Testeingaben.
_POOLS: dict[str, list] = {
    "int": [0, 1, -1, 2, 10],
    "float": [0.0, 1.0, -1.5, 3.14],
    "str": ["", "a", "abc", "hello world"],
    "bool": [True, False],
    "list": [[], [1, 2, 3]],
    "dict": [{}, {"k": 1}],
    "tuple": [(), (1, 2)],
    "bytes": [b"", b"ab"],
    "set": [set(), {1, 2}],
}
_DEFAULT_POOL = [0, 1, -1, 2, "abc", "", [1, 2, 3], None]
_MAX_CASES = 5
_MAX_UNITS = 25

# "Vernuenftige" Einzelwerte, um einen Konstruktor moeglichst gueltig aufzurufen
# (damit die Methoden-Tests den Objektzustand ueberhaupt erreichen).
_REASONABLE: dict[str, object] = {
    "int": 1, "float": 1.0, "str": "test", "bool": True,
    "list": [1, 2, 3], "dict": {"k": 1}, "tuple": (1, 2),
    "bytes": b"ab", "set": {1, 2},
}


def _reasonable_value(annotation: ast.expr | None):
    if annotation is not None:
        try:
            text = ast.unparse(annotation).lower()
            for key, val in _REASONABLE.items():
                if key in text:
                    return val
        except Exception:
            pass
    return 1


def _reasonable_args(params: list[ast.arg]) -> list:
    return [_reasonable_value(p.annotation) for p in params]


def _pool_for(annotation: ast.expr | None) -> list:
    if annotation is None:
        return _DEFAULT_POOL
    try:
        text = ast.unparse(annotation).lower()
    except Exception:
        return _DEFAULT_POOL
    for key, pool in _POOLS.items():
        if key in text:
            return pool
    if "optional" in text or "none" in text:
        return [None] + _DEFAULT_POOL
    return _DEFAULT_POOL


def _positional_params(func: ast.FunctionDef | ast.AsyncFunctionDef,
                       drop_self: bool) -> list[ast.arg]:
    args = list(func.args.posonlyargs) + list(func.args.args)
    if drop_self and args and args[0].arg in ("self", "cls"):
        args = args[1:]
    return args


def _arg_tuples(params: list[ast.arg], n: int = _MAX_CASES) -> list[list]:
    """Erzeugt bis zu n diverse Argument-Tupel (ohne Kombinatorik-Explosion)."""
    if not params:
        return [[]]
    pools = [_pool_for(p.annotation) for p in params]
    tuples = []
    for i in range(n):
        tuples.append([pool[i % len(pool)] for pool in pools])
    # Duplikate entfernen (Reihenfolge erhalten)
    seen, unique = set(), []
    for t in tuples:
        key = repr(t)
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique


def _find_class_init(tree: ast.Module, class_name: str):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and item.name == "__init__":
                    return item
    return None


def generate_tests(analysis: CodeAnalysis) -> str:
    """Erzeugt eine vollstaendige pytest-Datei (String)."""
    tree = ast.parse(analysis.source)
    lines = [
        '"""Automatisch generierte Baseline-Tests (Offline-Heuristik / SBST).',
        "Smoke- & Determinismus-Tests: rufen jede Callable mit heuristischen",
        'Eingaben auf und pruefen deterministisches Verhalten."""',
        f"import {MODULE_NAME} as m",
        "import pytest",
        "",
    ]

    # Map: qualname -> (node, ctor)
    func_nodes = {n.name: n for n in tree.body
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    count = 0
    for unit in analysis.units:
        if count >= _MAX_UNITS:
            break
        if unit.kind == "function":
            node = func_nodes.get(unit.name)
            if node is None:
                continue
            lines += _emit_function_tests(unit.name, node)
            count += 1
        else:  # method: "Class.method"
            cls_name, meth = unit.qualname.split(".", 1)
            cls_node = next((n for n in tree.body
                             if isinstance(n, ast.ClassDef) and n.name == cls_name), None)
            if cls_node is None:
                continue
            meth_node = next((it for it in cls_node.body
                              if isinstance(it, (ast.FunctionDef, ast.AsyncFunctionDef))
                              and it.name == meth), None)
            if meth_node is None:
                continue
            init_node = _find_class_init(tree, cls_name)
            lines += _emit_method_tests(cls_name, meth, meth_node, init_node)
            count += 1

    if count == 0:
        lines.append("def test_module_importierbar():")
        lines.append("    assert m is not None")
        lines.append("")
    return "\n".join(lines)


def _emit_function_tests(name: str, node) -> list[str]:
    params = _positional_params(node, drop_self=False)
    out = []
    for idx, args in enumerate(_arg_tuples(params)):
        call = f"m.{name}({', '.join(repr(a) for a in args)})"
        out += [
            f"def test_{name}_case_{idx}():",
            "    try:",
            f"        _r1 = {call}",
            "    except Exception:",
            "        return  # Ausnahme ist zulaessiges Verhalten (Zweig ausgefuehrt)",
            f"    _r2 = {call}",
            "    assert _r1 == _r2  # deterministisch",
            "",
        ]
    return out


def _emit_method_tests(cls: str, meth: str, meth_node, init_node) -> list[str]:
    safe = f"{cls}_{meth}".replace(".", "_").replace("__", "_")

    # Sonderfall Konstruktor: verschiedene Eingaben durchprobieren (deckt die
    # Validierungs-Branches im __init__ ab), ohne Objektvergleich.
    if meth == "__init__":
        params = _positional_params(meth_node, drop_self=True)
        out = []
        for idx, args in enumerate(_arg_tuples(params)):
            call = f"m.{cls}({', '.join(repr(a) for a in args)})"
            out += [
                f"def test_{safe}_case_{idx}():",
                "    try:",
                f"        obj = {call}",
                "    except Exception:",
                "        return  # ungueltige Eingabe -> Ausnahme-Zweig ausgefuehrt",
                "    assert obj is not None",
                "",
            ]
        return out

    # Regulaere Methode: Konstruktor mit "vernuenftigen" Werten aufrufen, damit
    # das Objekt gueltig ist und die Methode ihren Rumpf tatsaechlich erreicht.
    if init_node is not None:
        ctor_args = _reasonable_args(_positional_params(init_node, drop_self=True))
    else:
        ctor_args = []
    ctor_call = f"m.{cls}({', '.join(repr(a) for a in ctor_args)})"

    params = _positional_params(meth_node, drop_self=True)
    out = []
    for idx, args in enumerate(_arg_tuples(params)):
        arg_str = ", ".join(repr(a) for a in args)
        out += [
            f"def test_{safe}_case_{idx}():",
            "    try:",
            f"        obj = {ctor_call}",
            f"        _r1 = obj.{meth}({arg_str})",
            "    except Exception:",
            "        return  # Aufruf wirft -> zulaessig (Zweig ausgefuehrt)",
            f"    obj2 = {ctor_call}",
            f"    _r2 = obj2.{meth}({arg_str})",
            "    assert _r1 == _r2  # deterministisch",
            "",
        ]
    return out
