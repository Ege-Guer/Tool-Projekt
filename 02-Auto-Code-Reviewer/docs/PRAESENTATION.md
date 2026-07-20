# Auto Code Reviewer — Skript für die 5-Minuten-Videovorstellung

Ziel: Features zeigen + Live-Demo. Rollen (Vorschlag): 2 sprechen, 1 bedient die
App, 1 macht Bildschirmaufnahme/Schnitt. Zeiten sind Richtwerte.

---

### 0:00–0:40 · Motivation & Thema
- „Code-Reviews sind wichtig, aber teuer und uneinheitlich."
- „Der **Auto Code Reviewer** ist ein **agentisches** Tool: es findet Bugs,
  Sicherheitslücken und Smells, **prüft die Findings selbst kritisch** und schlägt
  eine korrigierte Version vor."
- Ein Satz zur Idee: „LLM-Review, **gegroundet** durch statische Analyse, gefiltert
  durch einen **Kritiker-Agenten** (Reflection, VL8)."

### 0:40–1:30 · Überblick & Bedienung
- App zeigen: Beispiel `insecure_service.py` laden, Struktur-Kacheln.
- Seitenmenü: Provider **ChatAI**, Strategie **agentic**, Durchläufe (Self-Consistency),
  Toggles **Reflection/Verifikation** und **Program Repair**.
- Drei Strategien nennen: `agentic` / `llm` / `rules` (offline, wie ein Linter).

### 1:30–3:00 · Live-Demo: der agentische Review
- „Code reviewen" klicken. **Live-Log** mitlesen:
  - „Statische Analyse: N Findings" (Grounding)
  - „LLM-Review Durchlauf 1/2, 2/2" (Self-Consistency)
  - „Reflection/Verifikation: X bestätigt, Y als Falsch-Positiv verworfen"
- **Findings-Liste** zeigen: farbige Schweregrad-Badges, Kategorie, Zeile, Quelle
  („Regel" vs. „LLM-Konsens"), Code-Ausschnitt, Vorschlag.
- **Highlight**: ein Finding zeigen, das **nur das LLM** gefunden hat und das die
  Regeln nicht sehen (z. B. in `messy_utils.py` die **Division durch Null** in
  `average()`). „Das ist der Mehrwert des LLM über einen klassischen Linter."

### 3:00–4:00 · Reflection & Metriken (das Besondere)
- Auf **Precision** zeigen: „Der Kritiker-Agent hat Falsch-Positive aussortiert —
  Precision = Anteil bestätigter LLM-Findings." (Reflection-Pattern, VL8)
- **Severity-Chart** + **Risk-Score** kurz erklären.
- Kontrast zeigen: Strategie auf **rules** umstellen → „nur der Linter", dann
  **agentic** → „Linter + LLM + Selbstkritik".

### 4:00–4:40 · Program Repair
- Toggle **Program Repair** an, erneut laufen lassen (oder vorbereiteten Lauf zeigen).
- **Korrigierte Version** zeigen + Download. „Das LLM behebt die bestätigten
  Findings; wir validieren, dass der Code syntaktisch korrekt bleibt (AST)."
  → Bezug: AutoCodeRover / Dialogue-based Repair (VL11).

### 4:40–5:00 · Abschluss & Vorlesungsbezug
- Konzept-Landkarte: **Self-Consistency (VL5) · Agentic/ReAct/Tool-Usage/Reflection/
  Multi-Agent (VL8) · Program Repair & Grounding (VL11)**.
- „Provider-agnostisch und **offline-fähig** (reiner Regelmodus). Bericht als
  Markdown exportierbar (z. B. für CI). Danke!"

---

**Demo-Tipps**
- Vor der Aufnahme `CHATAI_API_KEY` setzen und einen Probelauf machen.
- `insecure_service.py` zeigt viele **Security**-Findings (eval, os.system,
  shell=True, pickle, hartkodiertes Secret) → sehr anschaulich.
- `messy_utils.py` eignet sich, um den **LLM-Mehrwert** (Division durch Null) und
  **Program Repair** zu zeigen.
- Falls kein Netz: Strategie **rules** — findet offline zuverlässig die Kern-Bugs.
