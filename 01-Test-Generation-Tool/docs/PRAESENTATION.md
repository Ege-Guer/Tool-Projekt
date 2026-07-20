# TestPilot — Skript für die 5-Minuten-Videovorstellung

Ziel: Features zeigen + Live-Demo. Rollen (Vorschlag): 2 sprechen, 1 bedient die
App, 1 macht Bildschirmaufnahme/Schnitt. Zeiten sind Richtwerte.

---

### 0:00–0:40 · Motivation & Thema
- „Nur ~17 % der GitHub-Projekte haben Tests (VL11). Tests von Hand sind teuer."
- „**TestPilot** generiert automatisch `pytest`-Tests und **verbessert die
  Branch-Coverage in einem agentischen Loop** — Vorbild: TestForge/CoverUp/CodaMosa."
- Ein Satz zur Architektur: „Ein LLM-Agent, gegroundet durch AST-Analyse, geleitet
  durch Coverage als **Fitness-Funktion**."

### 0:40–1:30 · Überblick & Bedienung (Web-App)
- App zeigen: Code laden (Beispiel `bank_account.py`), Analyse-Kacheln (Callables,
  Branches).
- Seitenmenü: Provider **ChatAI**, Strategie **hybrid**, Ziel-Coverage, Iterationen.
- Kurz die drei Strategien nennen (hybrid / llm / heuristic = offline).

### 1:30–3:00 · Live-Demo: der agentische Loop
- „Tests generieren" klicken. **Live-Log** mitlesen:
  - Heuristik-Baseline → erste Coverage
  - Zero-Shot LLM → erster Entwurf
  - **Feedback-Iterationen**: „Branch 62 % → 87 % → 100 %" zeigen
- Auf den **Coverage-Verlauf-Chart** zeigen: „Hier sieht man, wie der Agent die
  Coverage Schritt für Schritt hochtreibt — das ist die geführte Suche (SBSE)."

### 3:00–4:00 · Pareto-Front & Mutation Score (das Besondere)
- **Pareto-Plot** zeigen: „Branch-Coverage ↑ vs. Anzahl Tests ↓. NSGA-II wählt die
  nicht-dominierten Suiten — der **Knie-Punkt** ist der beste Kompromiss (VL7)."
- **Mutation Score** zeigen: „Strenger als Coverage — misst, ob die Assertions
  echte Fehler fangen. Hier sieht man den Unterschied zwischen der schwachen
  Heuristik-Baseline und den LLM-Tests."

### 4:00–4:40 · Ergebnis & Vorlesungsbezug
- Beste Suite + Download zeigen.
- Kurz die Konzept-Landkarte: **Zero-Shot (VL5) · Agentic/ReAct (VL8) · SBSE/Fitness
  (VL6/7) · Pareto/NSGA-II (VL7) · Coverage & Mutation Score (VL11)**.

### 4:40–5:00 · Abschluss
- „Läuft provider-agnostisch (ChatAI/OpenAI/Ollama) **und komplett offline**."
- „Danke — Code & Doku im Repository."

---

**Demo-Tipps**
- Vor der Aufnahme `CHATAI_API_KEY` setzen und **einmal** einen Lauf machen (Modelle
  „aufwärmen"), damit die Live-Demo flüssig ist.
- Falls kein Netz: Strategie **heuristic** wählen — läuft offline und zeigt trotzdem
  Coverage, Pareto und Mutation Score.
- Kleines Beispiel wählen (`bank_account.py`, `string_utils.py`), damit ein Lauf
  in <30 s durch ist.
