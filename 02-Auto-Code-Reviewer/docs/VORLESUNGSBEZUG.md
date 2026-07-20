# Auto Code Reviewer — Bezug zu den Vorlesungsinhalten

Dieses Dokument ordnet die Funktionen des Tools den Konzepten der Vorlesung
„KI im Software Engineering" zu (Bewertungskriterium: *Sinnvolle Integration der
Vorlesungsinhalte*).

---

## VL5 — Prompt-Engineering, Modelltypen & Benchmarks

| Konzept | Umsetzung im Tool |
|---|---|
| **Zero-Shot-Prompting** | Review-Erstwurf aus Code + Kontext (`prompts.review_prompt`). |
| **Self-Consistency** | Mehrere Review-Durchläufe (`passes`), Findings werden per Mehrheit zusammengeführt (`agent._merge`, gezählte „Stimmen" → Konsens). |
| **Strukturierte Ausgabe** | Findings als JSON; robuste Extraktion (`llm.extract_json`). |

## VL8 — Agentic AI / Tool-Usage / Patterns

| Konzept | Umsetzung im Tool |
|---|---|
| **Agent = LLM + Tools** | `agent.py` kombiniert LLM-Aufrufe mit statischer Analyse als „Werkzeug". |
| **ReAct (Observe → Reason → Act)** | Observe: AST/Regel-Analyse · Reason: Findings + Verifikation · Act: Reparaturvorschlag. |
| **Pattern: Reflection** | **Kritiker-/Verifikations-Stufe**: jedes LLM-Finding wird adversarial geprüft („echt oder Falsch-Positiv?", `agent._verify`) → **Precision**. |
| **Pattern: Tool-Usage** | Regelbasierter Analyzer (`rules.py`) als deterministisches Tool; seine Findings **grounden** den LLM-Prompt. |
| **Pattern: Multi-Agent Collaboration** | Rollen-Trennung: „Reviewer" erzeugt Findings, „Kritiker" verwirft Falsch-Positive. |

## VL11 — Program Repair / Testgenerierung

| Konzept | Umsetzung im Tool |
|---|---|
| **Dialogue-based Program Repair** | Iterativer Dialog: Findings → korrigierte Code-Version (`prompts.repair_prompt`). |
| **Agentic Program Repair (AutoCodeRover)** | Zwei Phasen: (1) Kontext-Beschaffung (AST + Regeln), (2) Patch-Generierung; Patch wird **AST-validiert** (`agent._repair`). |
| **Statische Analyse als Grounding (CoverUp)** | `rules.py` liefert gegroundete Findings + Kontext, reduziert Halluzinationen. |
| **Evaluationsdenken** | Precision (bestätigte Findings), Risk-Score, Verteilung nach Schweregrad/Kategorie. |

## Grounding / RAG-Gedanke (VL5/VL8)

- Statt frei zu halluzinieren, bekommt das LLM **strukturierte Fakten** aus der
  statischen Analyse in den Kontext — analog zum RAG-Grundgedanken „externe,
  verlässliche Informationen in den Prompt holen".

## VL „Datenschutz & Verantwortung"

- Der Reviewer **führt den Code nicht aus** (rein statische Analyse + LLM) →
  keine Ausführung nicht vertrauenswürdigen Codes. Secrets werden nie geloggt.

---

### Was die Stufen konkret bringen (am Beispiel `examples/messy_utils.py`)

| Stufe | Ergebnis |
|---|---|
| **Regeln (offline)** | Findet Bugs/Smells zuverlässig: mutable Default, nacktes `except`, `assert`-Tupel, `== None`, ungenutzter Import … |
| **LLM (Self-Consistency)** | Findet **zusätzlich** Semantik-Bugs, die Regeln nicht sehen — z. B. **Division durch Null bei leerer Liste** in `average()`. |
| **Reflection/Verifikation** | Verwirft Falsch-Positive → höhere Precision. |
| **Program Repair** | Erzeugt eine korrigierte, lauffähige Version (None-Default, `is None`, Docstrings, Logging …). |

### Wo im Code?

```
codereviewer/rules.py    → statischer Analyzer / Grounding / Tool-Usage (VL8/11)
codereviewer/agent.py    → Self-Consistency + Reflection + Repair (VL5/8/11)
codereviewer/prompts.py  → Review-, Verify-, Repair-Prompts
codereviewer/report.py   → Markdown-Bericht
```
