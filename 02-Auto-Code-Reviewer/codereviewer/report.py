"""Markdown-Export eines Review-Berichts (fuer Download / CI-Kommentar)."""
from __future__ import annotations

from .models import ReviewReport

_SEV_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}


def to_markdown(report: ReviewReport) -> str:
    s = report.summary()
    lines = [
        f"# Code-Review-Bericht: `{s['module']}.py`",
        "",
        f"- **Findings gesamt:** {s['total']}",
        f"- **Verteilung:** 🔴 {s['critical']} critical · 🟠 {s['high']} high · "
        f"🟡 {s['medium']} medium · 🔵 {s['low']} low · ⚪ {s['info']} info",
        f"- **Risk-Score:** {s['risk_score']}",
    ]
    if s["precision"] is not None:
        lines.append(f"- **Precision nach Verifikation:** {s['precision']:.0f}% "
                     f"der LLM-Findings bestaetigt")
    lines += [f"- **Review-Durchlaeufe:** {s['passes']}",
              f"- **Dauer:** {s['elapsed']:.1f}s", "", "---", "", "## Findings", ""]

    if not report.findings:
        lines.append("_Keine Findings – der Code sieht gut aus._")
    for i, f in enumerate(report.findings, start=1):
        emoji = _SEV_EMOJI.get(f.severity, "•")
        src = {"static": "Regel", "consensus": "LLM-Konsens", "llm": "LLM"}.get(f.source, f.source)
        lines += [
            f"### {i}. {emoji} [{f.severity.upper()}] {f.title}",
            f"- **Zeile:** {f.line} · **Kategorie:** {f.category} · **Quelle:** {src}"
            + (f" · **Stimmen:** {f.votes}" if f.votes > 1 else ""),
        ]
        if f.code_snippet:
            lines.append(f"- **Code:** `{f.code_snippet}`")
        lines.append(f"- **Problem:** {f.explanation}")
        if f.suggestion:
            lines.append(f"- **Vorschlag:** {f.suggestion}")
        if f.verify_reason:
            lines.append(f"- **Verifikation:** {f.verify_reason}")
        lines.append("")

    if report.repaired_code:
        lines += ["---", "", "## Vorgeschlagene korrigierte Version", "",
                  "```python", report.repaired_code, "```", ""]

    lines += ["---", "", "_Erzeugt mit dem Auto Code Reviewer "
              "(Tool-Projekt · KI im Software Engineering)._"]
    return "\n".join(lines)
