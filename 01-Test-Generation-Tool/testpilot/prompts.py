"""
Prompt-Vorlagen fuer die LLM-basierte Testgenerierung.

Direkt an die Vorlesung angelehnt:
  * Zero-Shot mit reichem Kontext (VL11, Folie 14/15): Aufgabenbeschreibung,
    Signaturen, Docstrings.
  * Feedback-/Reparatur-Prompt (VL11, Folie 34 & 69, "Dialogue-based Repair";
    CoverUp/TestForge): dem Modell werden Fehlermeldungen und *nicht abgedeckte*
    Zeilen/Branches zurueckgegeben, damit es gezielt nachbessert.
  * Reflection-Pattern (VL8, Folie 64): das Modell verbessert die eigene Ausgabe
    anhand konkreter Kritik.
"""
from __future__ import annotations

from .models import CodeAnalysis, TestCandidate
from .analysis import build_context_block
from .runner import MODULE_NAME

SYSTEM_PROMPT = (
    "Du bist ein erfahrener Python-Test-Ingenieur. Du schreibst praezise, "
    "lauffaehige Unit-Tests mit pytest. Du gibst AUSSCHLIESSLICH eine einzige "
    "vollstaendige Python-Testdatei zurueck, eingefasst in einen ```python "
    "Codeblock. Kein erklaerender Text davor oder danach.\n\n"
    "Feste Regeln:\n"
    f"1. Der zu testende Code liegt im Modul `{MODULE_NAME}`. Importiere daraus, "
    f"   z.B. `from {MODULE_NAME} import <name>` oder `import {MODULE_NAME}`.\n"
    "2. Jede Testfunktion beginnt mit `test_`.\n"
    "3. Nutze `pytest.raises(...)` fuer erwartete Ausnahmen.\n"
    "4. Schreibe echte Assertions (kein `assert True`). Decke Normalfaelle UND "
    "   Randfaelle/Grenzwerte ab (leere Eingaben, 0, negative Werte, Fehlerpfade).\n"
    "5. Keine Netzwerk-/Datei-/Zeit-Abhaengigkeiten; Tests muessen deterministisch sein.\n"
)


def zero_shot_prompt(analysis: CodeAnalysis) -> str:
    """Erster Prompt (Zero-Shot) mit maximalem Kontext."""
    ctx = build_context_block(analysis)
    return (
        "Erzeuge eine moeglichst vollstaendige pytest-Test-Suite fuer den folgenden "
        "Python-Code. Ziel: hohe Branch-Coverage und aussagekraeftige Assertions.\n\n"
        f"## Kontext\n{ctx}\n\n"
        f"## Quellcode ({MODULE_NAME}.py)\n```python\n{analysis.source}\n```\n\n"
        "Gib nur die Testdatei als einen ```python Codeblock zurueck."
    )


def _format_uncovered(candidate: TestCandidate, analysis: CodeAnalysis) -> str:
    cov = candidate.coverage
    if not cov:
        return ""
    parts = []
    if cov.missing_lines:
        src_lines = analysis.source.splitlines()
        shown = []
        for ln in cov.missing_lines[:15]:
            if 1 <= ln <= len(src_lines):
                shown.append(f"  Zeile {ln}: {src_lines[ln - 1].strip()}")
        if shown:
            parts.append("Nicht abgedeckte Zeilen:\n" + "\n".join(shown))
    if cov.missing_branches:
        br = ", ".join(f"{a}->{b}" for a, b in cov.missing_branches[:15])
        parts.append(f"Nicht abgedeckte Branches (Zeilenuebergaenge): {br}")
    return "\n".join(parts)


def feedback_prompt(candidate: TestCandidate, analysis: CodeAnalysis) -> str:
    """Reparatur-/Verbesserungs-Prompt auf Basis von Coverage- und Fehler-Feedback.

    Dies ist der Kern der agentischen Feedbackschleife (CoverUp/TestForge, VL11).
    """
    execu = candidate.execution
    cov = candidate.coverage
    fb = []

    if execu and not execu.compiles:
        fb.append("PROBLEM: Die Test-Suite liess sich NICHT ausfuehren "
                  "(Import-/Collection-Fehler). Korrigiere die Imports/Syntax.")
    if execu and execu.failure_messages:
        fb.append("Fehlgeschlagene Tests (korrigiere die Assertions passend zum "
                  "tatsaechlichen Verhalten des Codes):\n  - "
                  + "\n  - ".join(execu.failure_messages[:10]))
    if execu and (execu.stderr.strip()):
        tail = "\n".join(execu.stderr.strip().splitlines()[-12:])
        fb.append(f"stderr (Auszug):\n{tail}")

    uncovered = _format_uncovered(candidate, analysis)
    if uncovered:
        fb.append("Noch NICHT abgedeckter Code – schreibe gezielt Tests, die genau "
                  "diese Stellen ausfuehren:\n" + uncovered)

    cov_txt = (f"aktuell Branch-Coverage {cov.branch_percent:.0f}% / "
               f"Line-Coverage {cov.line_percent:.0f}%") if cov else "unbekannt"

    return (
        f"Die bisherige Test-Suite erreicht {cov_txt}. Verbessere sie.\n\n"
        "## Aktuelle Test-Suite\n```python\n" + candidate.code + "\n```\n\n"
        "## Rueckmeldung\n" + "\n\n".join(fb) + "\n\n"
        f"## Quellcode ({MODULE_NAME}.py)\n```python\n" + analysis.source + "\n```\n\n"
        "Gib die VOLLSTAENDIGE, korrigierte und erweiterte Testdatei als einen "
        "einzigen ```python Codeblock zurueck. Behalte funktionierende Tests bei "
        "und ergaenze neue fuer die nicht abgedeckten Stellen."
    )
