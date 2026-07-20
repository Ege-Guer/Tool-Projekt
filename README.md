# Tool-Projekt · KI im Software Engineering (SoSe 2026)

**Auto Code Reviewer** — ein agentisches KI-Tool, das Python-Code reviewt: es findet
**Bugs, Sicherheitslücken, Performance- und Wartbarkeitsprobleme**, prüft jedes
Finding **adversarial** (Reflection) und schlägt optional eine **korrigierte
Version** vor (Program Repair). Umgesetzt als Web-Anwendung (Streamlit).

➡️ Der eigentliche Code liegt in [`02-Auto-Code-Reviewer/`](02-Auto-Code-Reviewer/).

---

## Schnellstart

```bash
cd 02-Auto-Code-Reviewer
python -m pip install -r requirements.txt
streamlit run app.py
```

Danach die angezeigte URL im Browser öffnen (i.d.R. `http://localhost:8501`).

### LLM-Zugang (ChatAI der AcademicCloud)

Das Tool ist **provider-agnostisch** (jeder OpenAI-kompatible Endpunkt: ChatAI,
OpenAI, Ollama) und funktioniert zusätzlich **komplett offline** (statische
Regel-Analyse ohne API-Key).

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

| Konzept | Umsetzung |
|---|---|
| Zero-Shot + Self-Consistency *(VL5)* | mehrere LLM-Review-Durchläufe → Konsens |
| Agentic AI / ReAct / Tool-Usage *(VL8)* | statische Analyse als Tool + Review-Agent |
| Reflection / Multi-Agent *(VL8)* | Kritiker-Agent filtert Falsch-Positive → Precision |
| Program Repair *(VL11)* | korrigierte, AST-validierte Code-Version |
| Grounding durch statische Analyse *(CoverUp/AutoCodeRover, VL11)* | Regel-Findings als Kontext |

Details in [`02-Auto-Code-Reviewer/docs/VORLESUNGSBEZUG.md`](02-Auto-Code-Reviewer/docs/VORLESUNGSBEZUG.md).

---

## Projektstruktur

```
Tool-Projekt/
├── README.md                    ← diese Datei
└── 02-Auto-Code-Reviewer/       ← Auto Code Reviewer
    ├── app.py                   ← Streamlit-UI
    ├── codereviewer/            ← Kern-Paket
    ├── examples/  tests/  docs/
    └── requirements.txt
```

## Tests

```bash
cd 02-Auto-Code-Reviewer && python -m pytest -q
```

## Team

Zakarya · Moad · Yussef · Ege

*Modul „KI im Software Engineering", Prof. Dr. Dominik Sobania, SoSe 2026.*
