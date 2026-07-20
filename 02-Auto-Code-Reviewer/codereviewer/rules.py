"""
Regelbasierter statischer Analyzer (AST) — die Offline-Baseline des Reviewers.

Funktioniert wie ein kleiner Linter/Bug-Finder ganz ohne LLM. Die gefundenen
Findings dienen zugleich als *Grounding* fuer den LLM-Review: sie werden dem
Modell als Kontext mitgegeben, damit es weniger halluziniert und sich auf echte
Stellen konzentriert (vgl. statische Analyse in CoverUp / Kontext-Tools in
AutoCodeRover, VL11).

Jede Regel liefert ein `Finding` mit source="static".
"""
from __future__ import annotations

import ast
import re

from .models import CodeStructure, Finding

_BUILTINS = {
    "list", "dict", "set", "tuple", "str", "int", "float", "bool", "id", "type",
    "max", "min", "sum", "len", "input", "map", "filter", "range", "object", "bytes",
    "vars", "dir", "hash", "next", "iter", "format",
}
_SECRET_NAMES = re.compile(r"(password|passwd|secret|token|api_?key|access_?key|"
                           r"private_?key|credential)", re.IGNORECASE)
_TODO = re.compile(r"#.*\b(TODO|FIXME|XXX|HACK)\b", re.IGNORECASE)


class _StaticAnalyzer(ast.NodeVisitor):
    def __init__(self, source: str):
        self.source = source
        self.src_lines = source.splitlines()
        self.findings: list[Finding] = []
        self._n = 0
        # Import-Tracking fuer "unused import"
        self.imported: dict[str, int] = {}    # name -> lineno
        self.used_names: set[str] = set()

    def _add(self, node_or_line, category, severity, title, explanation, suggestion=""):
        line = node_or_line if isinstance(node_or_line, int) else getattr(
            node_or_line, "lineno", 1)
        self._n += 1
        snippet = self.src_lines[line - 1].strip() if 1 <= line <= len(self.src_lines) else ""
        self.findings.append(Finding(
            id=f"static-{self._n}", line=line, category=category, severity=severity,
            title=title, explanation=explanation, suggestion=suggestion,
            source="static", confidence=1.0, code_snippet=snippet,
        ))

    # ---- Namen/Imports einsammeln ---------------------------------------- #
    def visit_Import(self, node):
        for alias in node.names:
            name = (alias.asname or alias.name).split(".")[0]
            self.imported[name] = node.lineno
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if any(a.name == "*" for a in node.names):
            self._add(node, "smell", "low", "Wildcard-Import (from ... import *)",
                      "Wildcard-Importe verschmutzen den Namensraum und verstecken "
                      "Herkunft von Namen.", "Importiere nur die benoetigten Namen explizit.")
        else:
            for alias in node.names:
                name = alias.asname or alias.name
                self.imported[name] = node.lineno
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        elif isinstance(node.ctx, ast.Store) and node.id in _BUILTINS:
            self._add(node, "smell", "low", f"Ueberschreibt Builtin '{node.id}'",
                      f"Die Zuweisung an '{node.id}' verdeckt eine eingebaute Funktion/Typ.",
                      "Benenne die Variable um.")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        # os.system(...) / subprocess(..., shell=True) etc. werden in visit_Call geprueft
        self.generic_visit(node)

    # ---- Exception-Handling ---------------------------------------------- #
    def visit_ExceptHandler(self, node):
        body_is_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
        if node.type is None:
            self._add(node, "bug", "high", "Nacktes 'except:'",
                      "Ein nacktes except faengt ALLES ab (auch KeyboardInterrupt/"
                      "SystemExit) und versteckt Fehler.",
                      "Fange konkrete Exception-Typen ab, z.B. 'except ValueError:'.")
        elif isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"):
            sev = "medium" if body_is_pass else "low"
            self._add(node, "smell", sev, f"Sehr breites 'except {node.type.id}'",
                      "Das Abfangen sehr breiter Exceptions verdeckt oft echte Fehler.",
                      "Fange moeglichst spezifische Exceptions ab.")
        if body_is_pass:
            self._add(node, "smell", "medium", "Verschluckte Exception (except: pass)",
                      "Der Fehler wird stillschweigend ignoriert – Bugs bleiben unbemerkt.",
                      "Logge den Fehler oder behandle ihn sinnvoll.")
        self.generic_visit(node)

    # ---- Funktionsdefinitionen ------------------------------------------- #
    def _check_func(self, node):
        # Mutable Default Arguments
        for default in node.args.defaults + node.args.kw_defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self._add(default, "bug", "high",
                          "Veraenderliches Default-Argument",
                          "Mutable Defaults ([]/{}/set()) werden zwischen Aufrufen "
                          "geteilt und fuehren zu subtilen Bugs.",
                          "Nutze None als Default und erzeuge das Objekt im Rumpf.")
        # Fehlender Docstring bei oeffentlichen Funktionen
        if not node.name.startswith("_") and ast.get_docstring(node) is None:
            self._add(node, "docs", "info", f"Kein Docstring: {node.name}()",
                      "Oeffentliche Funktionen sollten dokumentiert sein.",
                      "Fuege einen kurzen Docstring hinzu.")
        # Zu lang
        length = getattr(node, "end_lineno", node.lineno) - node.lineno + 1
        if length > 50:
            self._add(node, "maintainability", "low",
                      f"Sehr lange Funktion: {node.name}() ({length} Zeilen)",
                      "Lange Funktionen sind schwer zu testen und zu verstehen.",
                      "Zerlege sie in kleinere Funktionen.")

    def visit_FunctionDef(self, node):
        self._check_func(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._check_func(node)
        self.generic_visit(node)

    # ---- Vergleiche ------------------------------------------------------ #
    def visit_Compare(self, node):
        for op, comp in zip(node.ops, node.comparators):
            if isinstance(comp, ast.Constant) and comp.value is None \
                    and isinstance(op, (ast.Eq, ast.NotEq)):
                self._add(node, "style", "low", "Vergleich mit None via == / !=",
                          "None sollte per Identitaet verglichen werden.",
                          "Nutze 'is None' bzw. 'is not None'.")
            if isinstance(comp, ast.Constant) and isinstance(comp.value, bool) \
                    and isinstance(op, (ast.Eq, ast.NotEq)):
                self._add(node, "style", "low", "Vergleich mit True/False via ==",
                          "Boolesche Werte nicht mit == vergleichen.",
                          "Nutze direkt 'if x:' bzw. 'if not x:'.")
        self.generic_visit(node)

    # ---- assert (a, b) ist immer wahr ------------------------------------ #
    def visit_Assert(self, node):
        if isinstance(node.test, ast.Tuple) and len(node.test.elts) > 0:
            self._add(node, "bug", "high", "assert mit Tupel ist immer wahr",
                      "assert (bedingung, 'msg') prueft ein nicht-leeres Tupel -> "
                      "immer True. Der Test greift nie.",
                      "Schreibe: assert bedingung, 'msg'  (ohne Klammern-Tupel).")
        self.generic_visit(node)

    # ---- gefaehrliche Aufrufe ------------------------------------------- #
    def visit_Call(self, node):
        fname = self._call_name(node.func)
        if fname in ("eval", "exec"):
            self._add(node, "security", "high", f"Nutzung von {fname}()",
                      f"{fname}() fuehrt beliebigen Code aus und ist ein "
                      "Sicherheitsrisiko bei nicht vertrauenswuerdigen Eingaben.",
                      "Vermeide eval/exec; nutze sichere Alternativen (z.B. ast.literal_eval).")
        if fname == "os.system":
            self._add(node, "security", "high", "os.system() (Command Injection)",
                      "os.system fuehrt Shell-Kommandos aus und ist anfaellig fuer "
                      "Command Injection.",
                      "Nutze subprocess.run([...]) ohne shell=True.")
        if fname in ("pickle.load", "pickle.loads"):
            self._add(node, "security", "high", "Unsicheres pickle.load",
                      "pickle deserialisiert beliebige Objekte und kann Code ausfuehren.",
                      "Nutze ein sicheres Format (z.B. JSON) fuer nicht vertrauenswuerdige Daten.")
        if fname in ("yaml.load",) and not any(k.arg == "Loader" for k in node.keywords):
            self._add(node, "security", "high", "yaml.load ohne Loader",
                      "yaml.load ohne SafeLoader kann beliebige Objekte instanziieren.",
                      "Nutze yaml.safe_load(...).")
        for kw in node.keywords:
            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                self._add(node, "security", "high", "subprocess mit shell=True",
                          "shell=True ermoeglicht Command Injection.",
                          "Uebergib eine Argumentliste und lass shell=False.")
        self.generic_visit(node)

    # ---- hardcodierte Secrets ------------------------------------------- #
    def visit_Assign(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) \
                and node.value.value.strip():
            for target in node.targets:
                if isinstance(target, ast.Name) and _SECRET_NAMES.search(target.id):
                    self._add(node, "security", "high",
                              f"Moeglicherweise hartkodiertes Secret: {target.id}",
                              "Zugangsdaten/Schluessel gehoeren nicht in den Quellcode "
                              "(landen sonst in der Versionsverwaltung).",
                              "Lade Secrets aus Umgebungsvariablen oder einem Secret-Store.")
        self.generic_visit(node)

    # ---- Hilfen ---------------------------------------------------------- #
    @staticmethod
    def _call_name(func) -> str:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            parts = []
            cur = func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            return ".".join(reversed(parts))
        return ""


def analyze(struct: CodeStructure) -> list[Finding]:
    """Fuehrt alle Regeln aus und liefert die Findings sortiert nach Schwere/Zeile."""
    if not struct.syntax_ok:
        return []
    analyzer = _StaticAnalyzer(struct.source)
    tree = ast.parse(struct.source)
    analyzer.visit(tree)

    # Nachlauf: ungenutzte Imports
    for name, line in analyzer.imported.items():
        if name not in analyzer.used_names:
            analyzer._add(line, "smell", "low", f"Ungenutzter Import: {name}",
                          "Der Import wird nirgends verwendet.",
                          "Entferne den ungenutzten Import.")

    # Nachlauf: TODO/FIXME-Kommentare (nicht im AST enthalten)
    for i, text in enumerate(struct.source.splitlines(), start=1):
        if _TODO.search(text):
            analyzer._add(i, "maintainability", "info", "Offener TODO/FIXME-Kommentar",
                          "Unerledigte Aufgabe im Code.", "Erledigen oder Ticket anlegen.")

    return sorted(analyzer.findings, key=lambda f: (f.severity_rank, f.line))
