"""
TestPilot – Streamlit Web-Oberflaeche.

Bedienung:
    streamlit run app.py

Die UI ist eine duenne Schicht ueber dem `testpilot`-Paket: sie sammelt die
Konfiguration, startet den agentischen Generierungslauf und visualisiert das
Ergebnis (Coverage-Verlauf, Pareto-Front, Mutation Score, beste Test-Suite).
"""
from __future__ import annotations

import os
import glob

import altair as alt
import pandas as pd
import streamlit as st

from testpilot import RunConfig, PROVIDERS, STRATEGIES, generate
from testpilot.analysis import analyze_source
from testpilot.llm import probe_connection
from testpilot import pareto as pareto_mod

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "examples")

st.set_page_config(page_title="TestPilot – Agentische Unit-Test-Generierung",
                   page_icon="🧪", layout="wide")


# --------------------------------------------------------------------------- #
# Hilfsfunktionen
# --------------------------------------------------------------------------- #
def list_examples() -> dict[str, str]:
    out = {}
    for path in sorted(glob.glob(os.path.join(EXAMPLES_DIR, "*.py"))):
        out[os.path.basename(path)] = path
    return out


def iteration_dataframe(report) -> pd.DataFrame:
    rows = []
    for step, rec in enumerate(report.iterations):
        rows.append({
            "Schritt": step,
            "Strategie": rec.strategy,
            "Branch %": rec.branch_cov,
            "Line %": rec.line_cov,
            "Fitness": rec.fitness,
            "Tests": rec.num_tests,
            "Bestanden": rec.passed,
            "Fehlgeschlagen": rec.failed,
            "Uebernommen": "✅" if rec.accepted else "",
        })
    return pd.DataFrame(rows)


def archive_dataframe(report) -> pd.DataFrame:
    pareto_ids = {c.id for c in report.pareto_front}
    knee = pareto_mod.knee_point(report.pareto_front)
    rows = []
    for c in report.archive:
        rows.append({
            "id": c.id,
            "Strategie": c.strategy,
            "Anzahl Tests": c.num_tests,
            "Branch Coverage %": c.branch_cov,
            "Line Coverage %": c.line_cov,
            "Bestanden": c.passing_tests,
            "Typ": ("Knie-Punkt" if (knee and c.id == knee.id)
                    else "Pareto-Front" if c.id in pareto_ids else "dominiert"),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Kopfbereich
# --------------------------------------------------------------------------- #
st.title("🧪 TestPilot")
st.caption("Agentische, Coverage-gesteuerte Unit-Test-Generierung für Python — "
           "Tool-Projekt · KI im Software Engineering")

with st.expander("ℹ️ Was passiert hier? (Bezug zur Vorlesung)"):
    st.markdown(
        "TestPilot erzeugt automatisch **pytest**-Unit-Tests für Python-Code und "
        "verbindet mehrere Vorlesungs­konzepte:\n"
        "- **Zero-Shot-Prompting** mit reichem Kontext → erster Test-Entwurf *(VL11)*\n"
        "- **Agentischer Feedback-Loop** (Observe → Reason → Act, ReAct/Reflection): "
        "Coverage & Fehler werden gemessen und an das LLM zurückgespielt, bis das "
        "Ziel erreicht ist *(VL8, VL11 – TestForge/CoverUp)*\n"
        "- **Coverage als Fitness-Funktion** einer such­basierten Optimierung *(SBSE, VL6/7)*\n"
        "- **Multi-Objective-Optimierung / Pareto-Front (NSGA-II)**: Branch-Coverage "
        "maximieren vs. Anzahl Tests minimieren *(VL7)*\n"
        "- **Mutation Score & pass@k** als strenge Gütemaße *(VL11, VL5)*"
    )


# --------------------------------------------------------------------------- #
# Sidebar: Konfiguration
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("⚙️ Konfiguration")

    st.subheader("LLM-Provider")
    provider_key = st.selectbox(
        "Provider", options=list(PROVIDERS.keys()),
        format_func=lambda k: PROVIDERS[k].label,
        index=list(PROVIDERS.keys()).index("chatai"),
    )
    preset = PROVIDERS[provider_key]
    if preset.note:
        st.caption(preset.note)

    base_url = st.text_input("Base URL", value=preset.base_url,
                             disabled=provider_key == "offline")
    model = st.text_input("Modell", value=preset.default_model,
                          disabled=provider_key == "offline")
    api_key = ""
    if preset.needs_key:
        env_hint = f" (oder Umgebungsvariable {preset.env_key})" if preset.env_key else ""
        api_key = st.text_input(f"API-Key{env_hint}", type="password",
                                value=os.environ.get(preset.env_key, "") if preset.env_key else "")
    temperature = st.slider("Temperature", 0.0, 1.5, 0.4, 0.1,
                            disabled=provider_key == "offline")

    if st.button("🔌 Verbindung testen", disabled=provider_key == "offline",
                 use_container_width=True):
        probe_cfg = RunConfig(provider=provider_key, base_url=base_url,
                              model=model, api_key=api_key).resolve()
        ok, msg = probe_connection(probe_cfg)
        (st.success if ok else st.error)(msg)

    st.divider()
    st.subheader("Strategie & Suche")
    strategy = st.selectbox("Strategie", options=list(STRATEGIES.keys()),
                            format_func=lambda k: STRATEGIES[k])
    max_iterations = st.slider("Max. Iterationen (Budget T)", 0, 10, 4)
    target_coverage = st.slider("Ziel-Branch-Coverage %", 50, 100, 100, 5)
    samples = st.slider("Stichproben für pass@k (Zero-Shot)", 1, 5, 1)

    st.divider()
    st.subheader("Metriken")
    run_pareto = st.toggle("Pareto-Front (NSGA-II)", value=True)
    run_mutation = st.toggle("Mutation Testing", value=True)
    pytest_timeout = st.number_input("pytest-Timeout (s)", 10, 300, 60, 10)


def build_config() -> RunConfig:
    return RunConfig(
        provider=provider_key, base_url=base_url, model=model, api_key=api_key,
        temperature=temperature, strategy=strategy, max_iterations=max_iterations,
        target_coverage=float(target_coverage), samples_per_step=samples,
        run_mutation=run_mutation, run_pareto=run_pareto,
        pytest_timeout=int(pytest_timeout),
    )


# --------------------------------------------------------------------------- #
# Code-Eingabe
# --------------------------------------------------------------------------- #
st.subheader("1 · Zu testenden Python-Code laden")
tab_ex, tab_up, tab_paste = st.tabs(["📚 Beispiel", "📁 Datei hochladen", "✍️ Einfügen"])

source_code = ""
module_name = "module_under_test"

with tab_ex:
    examples = list_examples()
    if examples:
        choice = st.selectbox("Beispielmodul", options=list(examples.keys()))
        source_code = open(examples[choice], encoding="utf-8").read()
        module_name = choice[:-3]
    else:
        st.info("Keine Beispiele im examples/-Ordner gefunden.")

with tab_up:
    up = st.file_uploader("Python-Datei (.py)", type=["py"])
    if up is not None:
        source_code = up.getvalue().decode("utf-8")
        module_name = up.name[:-3]

with tab_paste:
    pasted = st.text_area("Code einfügen", height=220,
                          placeholder="def add(a, b):\n    return a + b")
    if pasted.strip():
        source_code = pasted

if source_code:
    analysis = analyze_source(source_code, module_name)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Callables", len(analysis.units))
    c2.metric("Klassen", len(analysis.classes))
    c3.metric("Verzweigungen (geschätzt)", analysis.num_branches)
    c4.metric("Statements", analysis.num_statements)
    if not analysis.syntax_ok:
        st.error(f"Syntaxfehler: {analysis.syntax_error}")
    with st.expander("Quellcode ansehen"):
        st.code(source_code, language="python")


# --------------------------------------------------------------------------- #
# Lauf starten
# --------------------------------------------------------------------------- #
st.subheader("2 · Tests generieren")
run = st.button("🚀 Tests generieren", type="primary", disabled=not source_code,
                use_container_width=True)

if run and source_code:
    cfg = build_config()
    logs: list[str] = []
    log_box = st.empty()
    phase_box = st.empty()

    def on_event(e):
        t = e["type"]
        if t == "log":
            logs.append(e["msg"])
            log_box.code("\n".join(logs[-18:]))
        elif t == "phase":
            phase_box.info(f"Phase: **{e['msg']}**")
        elif t == "iteration":
            r = e["record"]
            logs.append(f"   ▸ Schritt [{r.strategy}] Branch={r.branch_cov:.0f}% "
                        f"Line={r.line_cov:.0f}% Tests={r.num_tests} "
                        f"Fitness={r.fitness:.2f}")
            log_box.code("\n".join(logs[-18:]))

    with st.spinner("Agent generiert und verbessert Tests …"):
        try:
            report = generate(source_code, cfg, on_event=on_event, module_name=module_name)
            st.session_state["report"] = report
            phase_box.success("Fertig ✔")
        except Exception as exc:
            st.error(f"Fehler beim Generieren: {exc}")


# --------------------------------------------------------------------------- #
# Ergebnisse (aus session_state, damit sie Downloads/Reruns überleben)
# --------------------------------------------------------------------------- #
report = st.session_state.get("report")
if report is not None and report.best is not None:
    st.subheader("3 · Ergebnis")
    s = report.summary()
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Branch Coverage", f"{s['branch_cov']:.0f}%")
    m2.metric("Line Coverage", f"{s['line_cov']:.0f}%")
    m3.metric("Tests", s["num_tests"])
    m4.metric("Bestanden", s["passing"])
    m5.metric("Mutation Score",
              f"{s['mutation_score']:.0f}%" if s["mutation_score"] is not None else "–")
    m6.metric("Dauer", f"{s['elapsed']:.0f}s")

    if report.pass_at_k and report.pass_at_k["values"]:
        pk = report.pass_at_k
        st.caption("pass@k (Zero-Shot-Stichproben, n=%d, korrekt=%d): "
                   % (pk["n"], pk["c"]) +
                   " · ".join(f"{k}={v:.2f}" for k, v in pk["values"].items()))

    left, right = st.columns(2)

    # --- Coverage-Verlauf über die Iterationen ---
    with left:
        st.markdown("**Coverage-Verlauf (agentischer Loop)**")
        df_it = iteration_dataframe(report)
        if not df_it.empty:
            long = df_it.melt(id_vars=["Schritt"], value_vars=["Branch %", "Line %", "Fitness"],
                              var_name="Metrik", value_name="Wert")
            chart = (alt.Chart(long).mark_line(point=True)
                     .encode(x=alt.X("Schritt:O", title="Schritt"),
                             y=alt.Y("Wert:Q"),
                             color="Metrik:N",
                             tooltip=["Schritt", "Metrik", "Wert"])
                     .properties(height=300))
            st.altair_chart(chart, use_container_width=True)

    # --- Pareto-Front ---
    with right:
        st.markdown("**Pareto-Front (Branch-Coverage ↑ vs. Anzahl Tests ↓)**")
        df_arc = archive_dataframe(report)
        if not df_arc.empty:
            base = alt.Chart(df_arc).encode(
                x=alt.X("Anzahl Tests:Q", title="Anzahl Tests (min)"),
                y=alt.Y("Branch Coverage %:Q", title="Branch Coverage % (max)"),
                tooltip=["id", "Strategie", "Anzahl Tests", "Branch Coverage %",
                         "Line Coverage %"],
            )
            points = base.mark_circle(size=140).encode(
                color=alt.Color("Typ:N", scale=alt.Scale(
                    domain=["Pareto-Front", "Knie-Punkt", "dominiert"],
                    range=["#2c7fb8", "#e6550d", "#bbbbbb"])))
            front_line = (alt.Chart(df_arc[df_arc["Typ"] != "dominiert"])
                          .mark_line(color="#2c7fb8", strokeDash=[4, 3])
                          .encode(x="Anzahl Tests:Q", y="Branch Coverage %:Q"))
            st.altair_chart((front_line + points).properties(height=300),
                            use_container_width=True)
            st.caption("Der **Knie-Punkt** (orange) ist der beste Kompromiss auf der Front.")

    # --- Iterationstabelle ---
    with st.expander("📋 Iterationsprotokoll"):
        st.dataframe(iteration_dataframe(report), use_container_width=True, hide_index=True)

    # --- Beste Test-Suite ---
    st.markdown("**Beste generierte Test-Suite** "
                f"(Strategie: `{report.best.strategy}`)")
    st.download_button("💾 test_module_under_test.py herunterladen",
                       data=report.best.code,
                       file_name=f"test_{module_name}.py",
                       mime="text/x-python")
    st.code(report.best.code, language="python")

    # --- Details ---
    col_a, col_b = st.columns(2)
    with col_a:
        with st.expander("🧬 Mutation-Details"):
            if report.mutation:
                mr = report.mutation
                st.write(f"Getötet: **{mr.killed}** · Überlebt: **{mr.survived}** "
                         f"· Gesamt: **{mr.total}** → Score **{mr.score:.0f}%**")
                st.caption("Überlebende Mutanten zeigen, wo die Assertions noch zu "
                           "schwach sind (strenger als reine Coverage).")
                if mr.details:
                    st.dataframe(pd.DataFrame(mr.details), use_container_width=True,
                                 hide_index=True)
            else:
                st.info("Mutation Testing war deaktiviert.")
    with col_b:
        with st.expander("📄 Ausführungs-Log"):
            st.code("\n".join(report.log))

else:
    st.info("Lade oben Code und klicke auf **Tests generieren**.")
