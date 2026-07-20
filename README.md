# Tool-Projekt · KI im Software Engineering (SoSe 2026)

Dieses Repository enthält **zwei** agentische KI-Tools für das Software Engineering.
Beide sind eigenständige Web-Anwendungen (Streamlit), teilen sich aber dieselbe
Architektur-Idee: **ein LLM-Agent in einer iterativen Schleife**, gegroundet durch
klassische Programmanalyse und geleitet durch messbare Metriken.

| # | Tool | Ordner | Was es macht |
|---|------|--------|--------------|
| 1 | **TestPilot** – Unit-Test-Generierung | [`01-Test-Generation-Tool/`](01-Test-Generation-Tool/) | Erzeugt automatisch `pytest`-Tests, verbessert die **Branch-Coverage** in einem agentischen Feedback-Loop und optimiert die Test-Suite multikriteriell (**Pareto / NSGA-II**). |
| 2 | **Auto Code Reviewer** | [`02-Auto-Code-Reviewer/`](02-Auto-Code-Reviewer/) | Reviewt Python-Code, findet **Bugs / Security / Smells**, prüft die Findings adversarial (**Reflection**) und schlägt eine korrigierte Version vor (**Program Repair**). |

> Beide Themen stammen aus den Projektvorschlägen der Vorlesung. Wir haben beide
> umgesetzt, damit nichts verworfen werden musste.

---

## Schnellstart

Für **jedes** Tool identisch (im jeweiligen Ordner):

```bash
cd 01-Test-Generation-Tool      # bzw. 02-Auto-Code-Reviewer
python -m pip install -r requirements.txt
streamlit run app.py
```

Danach im Browser die angezeigte URL öffnen (i.d.R. `http://localhost:8501`).

### LLM-Zugang (ChatAI der AcademicCloud)

Beide Tools sind **provider-agnostisch** (jeder OpenAI-kompatible Endpunkt) und
funktionieren zusätzlich **komplett offline** (statische Baseline ohne API-Key).

Für die LLM-Modi den ChatAI-Key setzen – **nicht** in den Code schreiben:

```bash
# Windows (PowerShell)
$env:CHATAI_API_KEY = "<euer-key>"
# Linux/macOS
export CHATAI_API_KEY="<euer-key>"
```

Oder den Key direkt im Seitenmenü der Web-App eintragen. Empfohlene Modelle:
`qwen3-coder-next`, `devstral-2-123b-instruct-2512`.

---

## Bezug zur Vorlesung (Kurzüberblick)

| Konzept | TestPilot | Auto Code Reviewer |
|---|---|---|
| Zero-Shot + iteratives Prompting *(VL5/VL11)* | ✅ Test-Erstwurf → Feedback-Loop | ✅ Review-Erstwurf → Verifikation |
| Agentic AI / ReAct / Tool-Usage *(VL8)* | ✅ Observe→Reason→Act-Loop | ✅ statische Analyse als Tool + Agent |
| Reflection / Multi-Agent *(VL8)* | ✅ Selbstkritik pro Iteration | ✅ Kritiker-Agent filtert Falsch-Positive |
| Self-Consistency *(VL5)* | ✅ pass@k über Stichproben | ✅ Mehrfach-Review + Konsens |
| SBSE / Fitness-Funktion *(VL6/7)* | ✅ Coverage als Fitness | – |
| Multi-Objective / Pareto / NSGA-II *(VL7)* | ✅ Coverage ↑ vs. #Tests ↓ | – |
| Program Repair *(VL11)* | – | ✅ korrigierte Code-Version |
| Test-Generierung / Coverage / Mutation Score *(VL11)* | ✅ | – |
| Grounding durch statische Analyse *(CoverUp/AutoCodeRover, VL11)* | ✅ AST-Kontext | ✅ Regel-Findings als Kontext |

Details je Tool in `docs/VORLESUNGSBEZUG.md`.

---

## Projektstruktur

```
Tool-Projekt/
├── README.md                    ← diese Datei
├── ARBEITSTEILUNG.md            ← wer im Team was gemacht hat (Abgabe)
├── 01-Test-Generation-Tool/     ← Tool 1: TestPilot
│   ├── app.py                   ← Streamlit-UI
│   ├── testpilot/               ← Kern-Paket
│   ├── examples/  tests/  docs/
│   └── requirements.txt
└── 02-Auto-Code-Reviewer/       ← Tool 2: Auto Code Reviewer
    ├── app.py
    ├── codereviewer/
    ├── examples/  tests/  docs/
    └── requirements.txt
```

## Tests

```bash
cd 01-Test-Generation-Tool && python -m pytest -q
cd 02-Auto-Code-Reviewer  && python -m pytest -q
```

## Team

Zakarya · Moad · Yussef · Ege — siehe [`ARBEITSTEILUNG.md`](ARBEITSTEILUNG.md).

*Modul „KI im Software Engineering", Prof. Dr. Dominik Sobania, SoSe 2026.*
