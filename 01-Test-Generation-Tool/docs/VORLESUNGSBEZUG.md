# TestPilot — Bezug zu den Vorlesungsinhalten

Dieses Dokument ordnet die Funktionen des Tools den Konzepten der Vorlesung
„KI im Software Engineering" zu (Bewertungskriterium: *Sinnvolle Integration der
Vorlesungsinhalte*).

---

## VL5 — Prompt-Engineering, Modelltypen & Benchmarks

| Konzept | Umsetzung im Tool |
|---|---|
| **Zero-Shot-Prompting** | Erster Test-Entwurf aus Code + Kontext (`prompts.zero_shot_prompt`). |
| **Prompt Chaining / iterativ** | Ausgabe eines Schritts (Coverage/Fehler) wird Eingabe des nächsten Feedback-Prompts. |
| **Self-Consistency** | Mehrere Zero-Shot-Stichproben (`samples_per_step`) als Grundlage für pass@k. |
| **pass@k** | `metrics.pass_at_k` implementiert den unverzerrten Schätzer $\text{pass@}k = \mathbb{E}[1 - \binom{n-c}{k}/\binom{n}{k}]$. |

## VL6/VL7 — Search-Based Software Engineering (SBSE)

| Konzept | Umsetzung im Tool |
|---|---|
| **Suchbasierte Optimierung** | Der agentische Loop ist eine geführte Suche über den Raum der Test-Suiten. |
| **Fitness-Funktion muss die Suche leiten** (nicht 0/1) | **Coverage** (Line+Branch) als kontinuierliche Fitness (`TestCandidate.fitness`) — kein „Needle-in-a-Haystack". |
| **Archiv** (vgl. SBST) | Alle validen Suiten werden gesammelt (`agent.archive`). |
| **Multi-Objective Optimization** | Zwei konfliktäre Ziele: Branch-Coverage ↑ **vs.** Anzahl Tests ↓. |
| **Pareto-Front / Pareto-Dominanz** | `pareto.dominates`, `pareto.pareto_front`. |
| **NSGA-II** | Non-Dominated Sorting (`non_dominated_sort`) + Crowding Distance (`crowding_distance`) — selbst implementiert (statt `pymoo`). |
| **Knie-Punkt** | Bester Kompromiss auf der Front (`pareto.knee_point`). |

> Beispiel aus VL7 (Folie 57) direkt umgesetzt: „Test-Suite bzgl. Branch-Coverage
> (max) und Ausführungszeit (min) optimieren — selbst die leere Suite liegt auf
> der Pareto-Front." Genau dieser Trade-off wird im UI-Plot sichtbar.

## VL8 — Agentic AI / Tool-Usage / Patterns

| Konzept | Umsetzung im Tool |
|---|---|
| **Agent = LLM + Tools in einer Schleife** | `agent.py` orchestriert LLM-Aufrufe + Ausführung + Messung. |
| **ReAct (Observe → Reason → Act)** | Observe: `runner` misst Coverage/Fehler · Reason: Feedback-Prompt · Act: LLM erzeugt neue Suite. |
| **Reflection** | Das Modell verbessert die eigene Ausgabe anhand konkreter Kritik (nicht abgedeckte Zeilen). |
| **Tool-Usage** | Ausführung von `pytest`/`coverage` als „Werkzeug" des Agenten. |
| **Iterativer Suchprozess** (Ralph-Loop-Idee) | Variation (neue Tests) und Messung (Coverage) wechseln sich ab. |

## VL11 — Testgenerierung / Program Repair

| Konzept | Umsetzung im Tool |
|---|---|
| **LLM-basierte Testgenerierung (Zero/Few-Shot)** | Kernfunktion. |
| **Prompt-Engineering für Tests** (Docstrings, Signaturen, Beispiele) | Kontext-Block aus der AST-Analyse (`analysis.build_context_block`). |
| **Evaluationskriterien**: Kompilierungsrate, Korrektheit, **Branch Coverage** | `TestExecution.compiles`, `.correctness`, `CoverageReport.branch_percent`. |
| **SBST-Archiv-Loop (CodaMosa)** | Iterativer Loop mit Archiv + Abbruch bei Plateau/Budget. |
| **Hybrid SBST + LLM (CodaMosa)** | Strategie `hybrid`: Heuristik-Baseline + LLM. |
| **Agentische Verfahren (TestForge / CoverUp)** | Zero-Shot → Feedback-Loop mit Coverage-/Fehler-Rückmeldung; Fokus auf nicht abgedeckte Segmente. |
| **Mutation Score** | `mutation.py`: injiziert Mutanten (Vergleichs-, Rechen-, Aug-Assign-, Bool-, Konstanten-Mutationen) und misst getötete Mutanten. |
| **SBST-Baseline (Pynguin-Idee)** | Offline-Heuristik generiert Tests aus der AST-Analyse. |

## VL „Datenschutz & Verantwortung"

- Generierter Code wird **isoliert** (temporäres Verzeichnis, Timeout) ausgeführt;
  in `runner.py` dokumentiert. Hinweis auf Container-Sandbox für den Produktivbetrieb.

---

### Wo im Code?

```
testpilot/agent.py      → ReAct-Loop, Fitness-getriebene Suche (VL6/7/8/11)
testpilot/pareto.py     → NSGA-II, Pareto-Front, Crowding Distance (VL7)
testpilot/mutation.py   → Mutation Score (VL11)
testpilot/runner.py     → Coverage-Messung = Fitness-Evaluation (VL7/11)
testpilot/metrics.py    → pass@k (VL5)
testpilot/prompts.py    → Zero-Shot + Feedback/Reflection (VL5/8/11)
testpilot/heuristic.py  → SBST-Offline-Baseline (VL11)
```
