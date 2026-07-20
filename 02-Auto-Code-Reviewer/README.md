# 🔍 Auto Code Reviewer — Agentisches Code-Review

Reviewt Python-Code, findet **Bugs, Sicherheitslücken, Performance- und
Wartbarkeitsprobleme**, prüft jedes Finding **adversarial** (Reflection) und
schlägt optional eine **korrigierte Code-Version** vor (Program Repair).

Umgesetzt als Web-Anwendung (Streamlit). Vorbild sind agentische Verfahren aus der
Vorlesung: **AutoCodeRover** und **Dialogue-based Repair** (VL11) sowie die
**Agentic-AI-Patterns** aus VL8 (Reflection, Tool-Usage, Multi-Agent).

---

## Features

- **Drei Strategien**:
  - `agentic` *(Standard)* — LLM-Review (Self-Consistency) + Reflection/Verifikation
  - `llm` — einmaliger Zero-Shot-Review
  - `rules` — **offline**, statische AST-Regelprüfung (wie ein Linter), **ohne API-Key**
- **Statische Analyse als Grounding** (~15 Regeln): nacktes `except`, veränderliche
  Default-Argumente, `== None`, `eval`/`exec`, `os.system`, `subprocess(shell=True)`,
  unsicheres `pickle`/`yaml.load`, hartkodierte Secrets, `assert`-Tupel, Wildcard-/
  ungenutzte Imports, überschriebene Builtins, zu lange Funktionen, fehlende
  Docstrings, TODO/FIXME. Diese Findings groundеn zugleich den LLM-Prompt.
- **Self-Consistency** (VL5): mehrere Review-Durchläufe, Findings werden
  zusammengeführt (Mehrheit → Konsens, gezählte „Stimmen").
- **Reflection / Kritiker-Agent** (VL8): jedes LLM-Finding wird adversarial geprüft
  („echt oder Falsch-Positiv?") → **Precision**-Metrik.
- **Program Repair** (VL11, optional): das LLM erzeugt eine korrigierte, AST-validierte
  Version des Codes zum Download.
- **Metriken**: Findings nach Schweregrad/Kategorie, Precision, Risk-Score.
- **Markdown-Bericht** zum Download (z. B. als CI-Kommentar nutzbar).
- Provider-agnostisch: **ChatAI (AcademicCloud)**, OpenAI, Ollama oder offline.

## Installation & Start

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

LLM-Key (optional, für `agentic`/`llm`): `CHATAI_API_KEY` als Umgebungsvariable
setzen oder im Seitenmenü eintragen. Ohne Key läuft die Strategie `rules`.

## Architektur

Die UI (`app.py`) ist eine dünne Schicht über dem Paket `codereviewer/`:

| Modul | Aufgabe |
|---|---|
| `models.py` | Datenmodelle: `Finding`, `ReviewReport` (inkl. Metriken) |
| `config.py` | Provider-Presets (ChatAI …) + Lauf-Konfiguration |
| `analysis.py` | AST-Struktur (Funktionen, Klassen, Imports) = Kontext-Beschaffung |
| `rules.py` | **Regelbasierter statischer Analyzer** (Offline-Baseline + Grounding) |
| `prompts.py` | Review-, Verifikations- und Repair-Prompts |
| `llm.py` | OpenAI-kompatibler Client + robuste JSON-Extraktion |
| `agent.py` | **Orchestrator**: Self-Consistency → Reflection → Program Repair |
| `report.py` | Markdown-Export |

### Ablauf (vereinfacht)

```
Quellcode ──► AST-Analyse ──► Regel-Analyzer (statische Findings, gegroundet)
                                      │
                       ┌──────────────┘  (als Kontext in den Prompt)
                       ▼
        LLM-Review ×N (Self-Consistency) ──► Findings zusammenführen (Konsens)
                       │
                       ▼
        Reflection/Kritiker-Agent: jedes LLM-Finding echt? ──► Precision
                       │
                       ▼
        Finale Findings ──► (optional) Program Repair: korrigierter Code
                       │
                       ▼
        Metriken + Markdown-Bericht
```

## Tests

```bash
python -m pytest -q      # 10 Tests: Regeln + JSON-Extraktion
```

## Bezug zur Vorlesung

Ausführlich in [`docs/VORLESUNGSBEZUG.md`](docs/VORLESUNGSBEZUG.md).
Kurz: **VL5** (Self-Consistency, Prompting), **VL8** (Agentic AI, ReAct, Reflection,
Tool-Usage, Multi-Agent), **VL11** (Program Repair / AutoCodeRover / Dialogue-based
Repair; statische Analyse als Grounding wie bei CoverUp).
