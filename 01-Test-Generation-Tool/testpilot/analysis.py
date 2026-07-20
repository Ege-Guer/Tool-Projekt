"""
Statische Code-Analyse per AST (Abstract Syntax Tree).

Entspricht dem ersten Teil der SBST-Pipeline (VL11): "Abzudeckende Bereiche
ermitteln" (Branches) und "Aufrufbare Methoden ermitteln" (Callables). Ausserdem
extrahieren wir Kontext (Imports, Docstrings, Signaturen), um dem LLM einen
moeglichst reichhaltigen Prompt geben zu koennen (VL11, Folie 15: mehr Kontext ->
bessere Tests) und um bei fehlender Abdeckung gezielt nachzusteuern (wie CoverUp).
"""
from __future__ import annotations

import ast

from .models import CodeAnalysis, SourceUnit


# Knotentypen, die eine Verzweigung (Branch) einfuehren:
_BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler,
                 ast.With, ast.AsyncWith)


def _count_branches(node: ast.AST) -> int:
    """Zaehlt die Verzweigungspunkte in einem AST-Teilbaum (Naeherung).

    Die massgebliche Branch Coverage liefert spaeter coverage.py zur Laufzeit;
    dieser Wert dient nur der Anzeige und dem Prompt-Kontext.
    """
    count = 0
    for child in ast.walk(node):
        if isinstance(child, _BRANCH_NODES):
            count += 1
        elif isinstance(child, ast.BoolOp):          # and / or -> Kurzschluss-Branch
            count += max(0, len(child.values) - 1)
        elif isinstance(child, ast.IfExp):            # ternary a if c else b
            count += 1
        elif isinstance(child, (ast.comprehension,)):
            count += len(child.ifs)
    return count


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        args = ast.unparse(node.args)
    except Exception:
        args = ", ".join(a.arg for a in node.args.args)
    ret = ""
    if node.returns is not None:
        try:
            ret = " -> " + ast.unparse(node.returns)
        except Exception:
            ret = ""
    return f"({args}){ret}"


def _get_source_segment(source: str, node: ast.AST) -> str:
    try:
        seg = ast.get_source_segment(source, node)
        if seg:
            return seg
    except Exception:
        pass
    # Fallback ueber Zeilennummern
    lines = source.splitlines()
    start = getattr(node, "lineno", 1) - 1
    end = getattr(node, "end_lineno", start + 1)
    return "\n".join(lines[start:end])


def analyze_source(source: str, module_name: str = "module_under_test") -> CodeAnalysis:
    """Analysiert Quelltext und liefert eine `CodeAnalysis`.

    Bei Syntaxfehlern wird `syntax_ok=False` gesetzt (statt einer Exception),
    damit die UI eine saubere Fehlermeldung anzeigen kann.
    """
    analysis = CodeAnalysis(module_name=module_name, source=source)

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        analysis.syntax_ok = False
        analysis.syntax_error = f"Zeile {exc.lineno}: {exc.msg}"
        return analysis

    analysis.num_branches = _count_branches(tree)
    analysis.num_statements = sum(1 for _ in ast.walk(tree)
                                  if isinstance(_, ast.stmt))

    # Imports einsammeln (fuer den Prompt-Kontext / statische Analyse wie CoverUp)
    for node in tree.body:
        if isinstance(node, ast.Import):
            analysis.imports.append(ast.unparse(node))
        elif isinstance(node, ast.ImportFrom):
            analysis.imports.append(ast.unparse(node))

    def add_function(node, qualname, kind):
        analysis.units.append(SourceUnit(
            name=node.name,
            qualname=qualname,
            kind=kind,
            signature=_signature(node),
            docstring=ast.get_docstring(node),
            lineno=node.lineno,
            end_lineno=getattr(node, "end_lineno", node.lineno),
            source=_get_source_segment(source, node),
            num_branches=_count_branches(node),
        ))

    # Top-Level-Funktionen + Klassenmethoden
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                add_function(node, node.name, "function")
        elif isinstance(node, ast.ClassDef):
            analysis.classes.append(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # dunder wie __init__ zulassen, private _helper ausblenden
                    if item.name.startswith("_") and not (
                        item.name.startswith("__") and item.name.endswith("__")
                    ):
                        continue
                    add_function(item, f"{node.name}.{item.name}", "method")

    return analysis


def build_context_block(analysis: CodeAnalysis, max_units: int | None = None) -> str:
    """Erzeugt eine kompakte Kontext-Zusammenfassung fuer LLM-Prompts."""
    lines = [f"Modul: {analysis.module_name}.py",
             f"Klassen: {', '.join(analysis.classes) or 'keine'}",
             f"Verzweigungen (geschaetzt): {analysis.num_branches}",
             "Testbare Einheiten (Callables):"]
    units = analysis.units if max_units is None else analysis.units[:max_units]
    for u in units:
        doc = f"  # {u.docstring.splitlines()[0]}" if u.docstring else ""
        lines.append(f"  - {u.qualname}{u.signature}{doc}")
    return "\n".join(lines)
