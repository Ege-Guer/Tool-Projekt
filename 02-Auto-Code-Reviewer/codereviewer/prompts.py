"""
Prompt-Vorlagen fuer den Auto Code Reviewer.

Bezug zur Vorlesung:
  * Zero-Shot-Review mit reichem Kontext + Grounding durch statische Analyse
    (VL5/VL11): die Regel-Findings werden als Hinweise mitgegeben.
  * Verifikation = Reflection / Selbstkritik (VL8, Folie 64) und zugleich ein
    "Kritiker"-Agent (Multi-Agent Collaboration, VL8 Folie 67): jeder Befund
    wird adversarial geprueft (echt oder Falsch-Positiv?).
  * Reparatur = Program Repair / Dialogue-based Repair (VL11): der Agent schlaegt
    korrigierten Code vor.
"""
from __future__ import annotations

import json

from .models import CodeStructure, Finding
from .analysis import context_block

REVIEW_SYSTEM = (
    "Du bist ein sehr erfahrener Senior-Software-Ingenieur und fuehrst ein "
    "praezises Code-Review durch. Du meldest nur ECHTE, konkrete Probleme – "
    "keine erfundenen. Du antwortest AUSSCHLIESSLICH mit einem JSON-Array von "
    "Findings, ohne weiteren Text.\n\n"
    "Jedes Finding ist ein Objekt mit den Feldern:\n"
    '  "line": <int, betroffene Zeilennummer>,\n'
    '  "category": <"bug"|"security"|"performance"|"maintainability"|"smell"|"style"|"docs">,\n'
    '  "severity": <"critical"|"high"|"medium"|"low"|"info">,\n'
    '  "title": <kurze Ueberschrift>,\n'
    '  "explanation": <1-3 Saetze: WARUM ist das ein Problem>,\n'
    '  "suggestion": <konkreter Verbesserungsvorschlag>\n'
    "Gib maximal 15 Findings zurueck, priorisiere die wichtigsten (bugs/security "
    "zuerst). Wenn der Code fehlerfrei ist, gib ein leeres Array [] zurueck."
)


def review_prompt(struct: CodeStructure, static_findings: list[Finding]) -> str:
    ctx = context_block(struct)
    hints = ""
    if static_findings:
        items = [f"  - Z.{f.line}: {f.title} ({f.severity})" for f in static_findings[:15]]
        hints = ("\n\n## Hinweise eines statischen Analyzers (zur Orientierung, "
                 "bitte eigenstaendig pruefen und ergaenzen):\n" + "\n".join(items))
    numbered = _numbered(struct.source)
    return (
        "Reviewe den folgenden Python-Code gruendlich auf Bugs, Sicherheitsluecken, "
        "Performance-Probleme, Wartbarkeit und Stil.\n\n"
        f"## Kontext\n{ctx}{hints}\n\n"
        f"## Quellcode (mit Zeilennummern)\n```python\n{numbered}\n```\n\n"
        "Gib nur das JSON-Array der Findings zurueck."
    )


VERIFY_SYSTEM = (
    "Du bist ein kritischer Gutachter. Du pruefst vorgeschlagene Code-Review-"
    "Findings darauf, ob sie im gegebenen Code WIRKLICH zutreffen. Sei streng: "
    "Verwirf Falsch-Positive, doppelte oder unbegruendete Findings. Im Zweifel "
    "('unsicher') verwirf das Finding. Antworte AUSSCHLIESSLICH mit einem "
    "JSON-Array von Urteilen, je Finding ein Objekt:\n"
    '  "id": <die uebergebene id>,\n'
    '  "verdict": <"keep"|"discard">,\n'
    '  "reason": <kurze Begruendung>'
)


def verify_prompt(struct: CodeStructure, findings: list[Finding]) -> str:
    items = []
    for f in findings:
        items.append({
            "id": f.id, "line": f.line, "category": f.category,
            "severity": f.severity, "title": f.title, "explanation": f.explanation,
        })
    numbered = _numbered(struct.source)
    return (
        "Pruefe fuer jedes der folgenden Findings, ob es im Code tatsaechlich "
        "zutrifft. Behalte nur korrekte, relevante Findings.\n\n"
        f"## Quellcode (mit Zeilennummern)\n```python\n{numbered}\n```\n\n"
        f"## Zu pruefende Findings\n```json\n{json.dumps(items, ensure_ascii=False, indent=2)}\n```\n\n"
        "Gib nur das JSON-Array der Urteile zurueck."
    )


REPAIR_SYSTEM = (
    "Du bist ein erfahrener Entwickler. Du erhaeltst Code und eine Liste "
    "bestaetigter Findings und lieferst eine KORRIGIERTE Version des GESAMTEN "
    "Codes zurueck, die die Probleme behebt und das Verhalten ansonsten erhaelt. "
    "Antworte nur mit der korrigierten Datei in einem ```python Codeblock."
)


def repair_prompt(struct: CodeStructure, findings: list[Finding]) -> str:
    items = [f"  - Z.{f.line} [{f.severity}/{f.category}] {f.title}: {f.suggestion or f.explanation}"
             for f in findings]
    return (
        "Behebe die folgenden bestaetigten Findings im Code. Aendere nur das "
        "Noetige, erhalte das restliche Verhalten und die oeffentliche API.\n\n"
        "## Findings\n" + "\n".join(items) + "\n\n"
        f"## Quellcode\n```python\n{struct.source}\n```\n\n"
        "Gib die vollstaendige korrigierte Datei als einen ```python Codeblock zurueck."
    )


def _numbered(source: str) -> str:
    return "\n".join(f"{i:>4} | {line}"
                     for i, line in enumerate(source.splitlines(), start=1))
