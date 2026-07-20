"""
Statische Struktur-Analyse per AST.

Liefert Kontext fuer den LLM-Review (Funktionen, Klassen, Imports) und die Basis
fuer die Regelpruefung. Entspricht der "Kontext-Beschaffung" agentischer
Reviewer/Repair-Systeme (VL11, AutoCodeRover) und dem statischen Analyse-Schritt
von CoverUp.
"""
from __future__ import annotations

import ast

from .models import CodeStructure, FunctionInfo

_BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)


def _count_branches(node: ast.AST) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, _BRANCH_NODES):
            count += 1
        elif isinstance(child, ast.BoolOp):
            count += max(0, len(child.values) - 1)
        elif isinstance(child, ast.IfExp):
            count += 1
    return count


def analyze_source(source: str, module_name: str = "module") -> CodeStructure:
    struct = CodeStructure(module_name=module_name, source=source,
                           loc=len(source.splitlines()))
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        struct.syntax_ok = False
        struct.syntax_error = f"Zeile {exc.lineno}: {exc.msg}"
        return struct

    struct.num_branches = _count_branches(tree)

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            struct.imports.append(ast.unparse(node))

    def add_func(node, qualname):
        struct.functions.append(FunctionInfo(
            name=node.name, qualname=qualname,
            lineno=node.lineno, end_lineno=getattr(node, "end_lineno", node.lineno),
            num_branches=_count_branches(node),
            length=getattr(node, "end_lineno", node.lineno) - node.lineno + 1,
            has_docstring=ast.get_docstring(node) is not None,
        ))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add_func(node, node.name)
        elif isinstance(node, ast.ClassDef):
            struct.classes.append(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add_func(item, f"{node.name}.{item.name}")
    return struct


def context_block(struct: CodeStructure) -> str:
    lines = [f"Modul: {struct.module_name}.py  ({struct.loc} LOC, "
             f"~{struct.num_branches} Verzweigungen)",
             f"Klassen: {', '.join(struct.classes) or 'keine'}",
             f"Imports: {', '.join(struct.imports) or 'keine'}",
             "Funktionen/Methoden:"]
    for f in struct.functions:
        doc = "" if f.has_docstring else "  [kein Docstring]"
        lines.append(f"  - {f.qualname} (Z. {f.lineno}-{f.end_lineno}, "
                     f"{f.num_branches} Branches){doc}")
    return "\n".join(lines)
