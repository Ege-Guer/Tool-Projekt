# 🧪 TestPilot — Agentische Unit-Test-Generierung

Erzeugt automatisch `pytest`-Unit-Tests für Python-Code, **verbessert die
Branch-Coverage in einem agentischen Feedback-Loop** und wählt aus allen erzeugten
Test-Suiten multikriteriell die besten aus (**Pareto-Front / NSGA-II**).

Umgesetzt als Web-Anwendung (Streamlit). Vorbild sind die aktuellen Verfahren aus
der Vorlesung: **TestForge**, **CoverUp** und **CodaMosa** (VL11).

---

## Features

- **Drei Strategien** (entsprechen den Ansätzen aus VL11):
  - `hybrid` *(Standard)* — Heuristik-Baseline + LLM-Erstwurf + agentischer Loop
  - `llm` — nur LLM (Zero-Shot + Reparatur)
  - `heuristic` — **offline**, SBST-artige AST-Generierung (wie Pynguin), **ohne API-Key**
- **Agentischer Feedback-Loop**: Tests ausführen → Coverage & Fehler messen →
  gezieltes Feedback (nicht abgedeckte Zeilen/Branches) → LLM verbessert → wiederholen.
- **Coverage = Fitness-Funktion** einer suchbasierten Optimierung (SBSE, VL6/7).
- **Multi-Objective / Pareto-Front (NSGA-II)**: Branch-Coverage ↑ vs. Anzahl Tests ↓,
  inkl. Non-Dominated Sorting, Crowding Distance und Knie-Punkt — selbst implementiert.
- **Mutation Score** (VL11): injiziert Fehler und misst, ob die Suite sie erkennt.
- **pass@k** (VL5) über mehrere Zero-Shot-Stichproben.
- Provider-agnostisch: **ChatAI (AcademicCloud)**, OpenAI, Ollama oder offline.

## Installation & Start

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

LLM-Key (optional, für `hybrid`/`llm`): `CHATAI_API_KEY` als Umgebungsvariable
setzen oder im Seitenmenü eintragen. Ohne Key läuft die Strategie `heuristic`.

## Architektur

Die UI (`app.py`) ist eine dünne Schicht über dem Paket `testpilot/`:

| Modul | Aufgabe |
|---|---|
| `models.py` | Datenmodelle (Contract): `TestCandidate` = „Individuum" im SBSE-Sinn |
| `config.py` | Provider-Presets (ChatAI …) + Lauf-Konfiguration |
| `analysis.py` | Statische AST-Analyse: Callables, Branches, Kontext |
| `heuristic.py` | Offline-Generator (SBST-Baseline, Smoke-/Determinismus-Tests) |
| `prompts.py` | Zero-Shot- + Feedback-Prompts (Prompt Engineering) |
| `llm.py` | OpenAI-kompatibler Client (+ Offline-fähig) |
| `runner.py` | **Fitness-Evaluation**: sandboxed `pytest` + `coverage.py` (Branch-Coverage) |
| `agent.py` | **Orchestrator**: agentischer Coverage-Loop (Observe→Reason→Act) |
| `pareto.py` | NSGA-II: Non-Dominated Sorting, Crowding Distance, Knie-Punkt |
| `mutation.py` | Mutation Testing → Mutation Score |
| `metrics.py` | pass@k |

### Ablauf (vereinfacht)

```
Quellcode ──► AST-Analyse ──► [Heuristik-Baseline]
                               [Zero-Shot LLM]  ─┐
                                                 ▼
                     ┌──────────► Test-Suite ausführen (pytest+coverage)
                     │                     │  Coverage + Fehler = Fitness
                     │                     ▼
              Feedback-Prompt ◄──── nicht abgedeckte Zeilen/Branches
                     ▲                     │
                     └──── LLM verbessert ◄┘   (bis Ziel-Coverage / Plateau / Budget T)
                                           │
             Archiv aller Suiten ──► Pareto-Front (NSGA-II) + Mutation Score
```

## Tests

```bash
python -m pytest -q
```

## Bezug zur Vorlesung

Ausführlich in [`docs/VORLESUNGSBEZUG.md`](docs/VORLESUNGSBEZUG.md).
Kurz: **VL5** (Prompting, pass@k), **VL6/7** (SBSE, Fitness, NSGA-II/Pareto),
**VL8** (Agentic AI, ReAct, Reflection), **VL11** (Test-Generierung, Coverage,
Mutation Score; TestForge/CoverUp/CodaMosa).

> ⚠️ Sicherheit: Das Tool führt generierten Code in einem temporären, isolierten
> Verzeichnis mit Timeout aus. Für den Produktivbetrieb wäre eine Container-Sandbox
> sinnvoll (siehe VL „Datenschutz & Verantwortung").
