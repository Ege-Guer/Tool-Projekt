# Arbeitsteilung im Team

**Modul:** KI im Software Engineering · **Team:** Zakarya, Moad, Yussef, Ege

> **Hinweis:** Dies ist ein **Vorschlag / Ausgangspunkt**. Bitte an die tatsächliche
> Aufteilung anpassen, bevor ihr abgebt (die Abgabe verlangt „wer im Team was gemacht
> hat", max. 1 Seite).

---

| Person | Schwerpunkt | Konkrete Beiträge |
|---|---|---|
| **Ege** | Architektur & Koordination | Gesamtarchitektur beider Tools, agentischer Loop (`agent.py`), LLM-Anbindung (`config.py`, `llm.py`), ChatAI-Integration, Repository & Abgabe |
| **Zakarya** | TestPilot – Ausführung & Qualität | Sandbox-Runner (`runner.py`, `pytest`+`coverage.py`), Mutation Testing (`mutation.py`), heuristischer Offline-Generator (`heuristic.py`), Unit-Tests |
| **Moad** | TestPilot – Optimierung & UI | Multi-Objective / Pareto-Front, NSGA-II (`pareto.py`), Metriken/pass@k (`metrics.py`), AST-Analyse (`analysis.py`), Streamlit-UI |
| **Yussef** | Auto Code Reviewer | Regelbasierter Analyzer (`rules.py`), Prompts & Verifikation (`prompts.py`), Markdown-Report (`report.py`), Streamlit-UI, Beispiel-Dateien |

**Gemeinsam:** Konzeption & Themenwahl, Dokumentation (`README`, `VORLESUNGSBEZUG`),
Präsentations-/Video-Skript, Testen & Debugging, Abschluss-Review.

---

### Zeitlicher Ablauf (grob)

1. Themenanalyse & Vorlesungsbezug festlegen (alle)
2. Gemeinsame Basis: Provider-Config + LLM-Client (Ege)
3. Parallel: TestPilot (Zakarya, Moad) und Auto Code Reviewer (Yussef, Ege)
4. Integration, Metriken, UI-Feinschliff (alle)
5. Tests, Dokumentation, Video (alle)
