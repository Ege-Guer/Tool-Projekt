"""
Auto Code Reviewer – Streamlit Web-Oberflaeche.

Bedienung:
    streamlit run app.py

Duenne UI-Schicht ueber dem `codereviewer`-Paket: sammelt Konfiguration, startet
den agentischen Review-Lauf und visualisiert die Findings, Metriken (Precision,
Risk-Score) und optional die per Program Repair korrigierte Code-Version.
"""
from __future__ import annotations

import os
import glob

import altair as alt
import pandas as pd
import streamlit as st

from codereviewer import RunConfig, PROVIDERS, STRATEGIES, SEVERITIES, review
from codereviewer.analysis import analyze_source
from codereviewer.llm import probe_connection
from codereviewer.report import to_markdown

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "examples")
st.set_page_config(page_title="Auto Code Reviewer", page_icon="🔍", layout="wide")

SEV_COLOR = {"critical": "red", "high": "orange", "medium": "violet",
             "low": "blue", "info": "gray"}
SEV_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}


def list_examples() -> dict[str, str]:
    return {os.path.basename(p): p for p in sorted(glob.glob(os.path.join(EXAMPLES_DIR, "*.py")))}


# --------------------------------------------------------------------------- #
st.title("🔍 Auto Code Reviewer")
st.caption("Agentisches, LLM-gestütztes Code-Review für Python — "
           "Tool-Projekt · KI im Software Engineering")

with st.expander("ℹ️ Was passiert hier? (Bezug zur Vorlesung)"):
    st.markdown(
        "Der Reviewer analysiert Python-Code und meldet **Bugs, Sicherheitslücken, "
        "Performance- und Wartbarkeitsprobleme** — und verbindet dabei mehrere "
        "Vorlesungskonzepte:\n"
        "- **Statische Analyse als Grounding / Tool-Usage** (AST-Regeln, wie ein "
        "Linter) → reduziert Halluzinationen *(VL8, VL11)*\n"
        "- **Zero-Shot-Review + Self-Consistency**: mehrere LLM-Durchläufe, "
        "Mehrheit ergibt Konsens *(VL5)*\n"
        "- **Reflection / Kritiker-Agent**: jedes Finding wird adversarial "
        "verifiziert (Falsch-Positive raus) *(VL8 – Reflection & Multi-Agent)*\n"
        "- **Program Repair**: das LLM schlägt eine korrigierte Code-Version vor "
        "*(VL11 – AutoCodeRover / Dialogue-based Repair)*\n"
        "- **Metriken**: Precision (Anteil bestätigter Findings), Risk-Score"
    )


# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("⚙️ Konfiguration")
    st.subheader("LLM-Provider")
    provider_key = st.selectbox("Provider", options=list(PROVIDERS.keys()),
                                format_func=lambda k: PROVIDERS[k].label,
                                index=list(PROVIDERS.keys()).index("chatai"))
    preset = PROVIDERS[provider_key]
    if preset.note:
        st.caption(preset.note)
    base_url = st.text_input("Base URL", value=preset.base_url,
                             disabled=provider_key == "offline")
    model = st.text_input("Modell", value=preset.default_model,
                          disabled=provider_key == "offline")
    api_key = ""
    if preset.needs_key:
        api_key = st.text_input(f"API-Key (oder {preset.env_key})", type="password",
                                value=os.environ.get(preset.env_key, "") if preset.env_key else "")
    temperature = st.slider("Temperature", 0.0, 1.5, 0.3, 0.1,
                            disabled=provider_key == "offline")
    if st.button("🔌 Verbindung testen", disabled=provider_key == "offline",
                 use_container_width=True):
        ok, msg = probe_connection(RunConfig(provider=provider_key, base_url=base_url,
                                             model=model, api_key=api_key).resolve())
        (st.success if ok else st.error)(msg)

    st.divider()
    st.subheader("Strategie")
    strategy = st.selectbox("Strategie", options=list(STRATEGIES.keys()),
                            format_func=lambda k: STRATEGIES[k])
    passes = st.slider("Review-Durchläufe (Self-Consistency)", 1, 4, 2,
                       disabled=strategy == "rules")
    run_verification = st.toggle("Reflection/Verifikation (Falsch-Positive filtern)",
                                 value=True, disabled=strategy != "agentic")
    run_repair = st.toggle("Program Repair (korrigierten Code erzeugen)", value=False,
                           disabled=strategy == "rules")
    min_severity = st.select_slider("Mindest-Schweregrad (Anzeige)",
                                    options=SEVERITIES, value="info")


def build_config() -> RunConfig:
    return RunConfig(provider=provider_key, base_url=base_url, model=model, api_key=api_key,
                     temperature=temperature, strategy=strategy, passes=passes,
                     run_verification=run_verification, run_repair=run_repair,
                     min_severity=min_severity)


# --------------------------------------------------------------------------- #
st.subheader("1 · Python-Code laden")
tab_ex, tab_up, tab_paste = st.tabs(["📚 Beispiel", "📁 Datei hochladen", "✍️ Einfügen"])
source_code, module_name = "", "module"
with tab_ex:
    examples = list_examples()
    if examples:
        choice = st.selectbox("Beispielmodul", options=list(examples.keys()))
        source_code = open(examples[choice], encoding="utf-8").read()
        module_name = choice[:-3]
with tab_up:
    up = st.file_uploader("Python-Datei (.py)", type=["py"])
    if up is not None:
        source_code = up.getvalue().decode("utf-8")
        module_name = up.name[:-3]
with tab_paste:
    pasted = st.text_area("Code einfügen", height=220,
                          placeholder="def foo(x=[]):\n    x.append(1)\n    return x")
    if pasted.strip():
        source_code = pasted

if source_code:
    struct = analyze_source(source_code, module_name)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Funktionen/Methoden", len(struct.functions))
    c2.metric("Klassen", len(struct.classes))
    c3.metric("LOC", struct.loc)
    c4.metric("Verzweigungen", struct.num_branches)
    if not struct.syntax_ok:
        st.error(f"Syntaxfehler: {struct.syntax_error}")
    with st.expander("Quellcode ansehen"):
        st.code(source_code, language="python")


# --------------------------------------------------------------------------- #
st.subheader("2 · Review starten")
run = st.button("🔍 Code reviewen", type="primary", disabled=not source_code,
                use_container_width=True)

if run and source_code:
    cfg = build_config()
    logs, log_box, phase_box = [], st.empty(), st.empty()

    def on_event(e):
        if e["type"] == "log":
            logs.append(e["msg"]); log_box.code("\n".join(logs[-16:]))
        elif e["type"] == "phase":
            phase_box.info(f"Phase: **{e['msg']}**")

    with st.spinner("Agent reviewt den Code …"):
        try:
            st.session_state["review"] = review(source_code, cfg, on_event=on_event,
                                                module_name=module_name)
            phase_box.success("Fertig ✔")
        except Exception as exc:
            st.error(f"Fehler beim Review: {exc}")


# --------------------------------------------------------------------------- #
rep = st.session_state.get("review")
if rep is not None:
    st.subheader("3 · Ergebnis")
    s = rep.summary()
    m = st.columns(6)
    m[0].metric("Findings", s["total"])
    m[1].metric("🔴 Critical", s["critical"])
    m[2].metric("🟠 High", s["high"])
    m[3].metric("Risk-Score", s["risk_score"])
    m[4].metric("Precision", f"{s['precision']:.0f}%" if s["precision"] is not None else "–",
                help="Anteil der LLM-Findings, die die Verifikation bestätigt hat.")
    m[5].metric("Dauer", f"{s['elapsed']:.0f}s")

    left, right = st.columns([2, 1])
    with right:
        st.markdown("**Verteilung nach Schweregrad**")
        cs = rep.counts_by_severity()
        df = pd.DataFrame({"Schwere": list(cs.keys()), "Anzahl": list(cs.values())})
        chart = (alt.Chart(df).mark_bar().encode(
            x=alt.X("Anzahl:Q"),
            y=alt.Y("Schwere:N", sort=SEVERITIES),
            color=alt.Color("Schwere:N", scale=alt.Scale(
                domain=SEVERITIES, range=["#d62728", "#ff7f0e", "#e6c200", "#1f77b4", "#999999"]),
                legend=None),
            tooltip=["Schwere", "Anzahl"]).properties(height=220))
        st.altair_chart(chart, use_container_width=True)
        cats = rep.counts_by_category()
        if cats:
            st.markdown("**Nach Kategorie**")
            st.dataframe(pd.DataFrame({"Kategorie": list(cats.keys()),
                                       "Anzahl": list(cats.values())}),
                         hide_index=True, use_container_width=True)

    with left:
        st.markdown(f"**{len(rep.findings)} Findings** (sortiert nach Schweregrad)")
        if not rep.findings:
            st.success("Keine Findings – der Code sieht gut aus. 🎉")
        for i, f in enumerate(rep.findings, start=1):
            color = SEV_COLOR.get(f.severity, "gray")
            src = {"static": "Regel", "consensus": "LLM-Konsens", "llm": "LLM"}.get(f.source, f.source)
            with st.container(border=True):
                st.markdown(
                    f"{SEV_EMOJI.get(f.severity,'•')} :{color}[**{f.severity.upper()}**] · "
                    f"`{f.category}` · **Zeile {f.line}** · _{src}_"
                    + (f" · {f.votes}× gefunden" if f.votes > 1 else "")
                    + f"  \n**{f.title}**")
                if f.code_snippet:
                    st.code(f.code_snippet, language="python")
                st.markdown(f"**Problem:** {f.explanation}")
                if f.suggestion:
                    st.markdown(f"💡 **Vorschlag:** {f.suggestion}")
                if f.verify_reason:
                    st.caption(f"Verifikation: {f.verify_reason}")

    # Downloads + Repair
    st.divider()
    dl1, dl2 = st.columns(2)
    dl1.download_button("📄 Bericht als Markdown", data=to_markdown(rep),
                        file_name=f"review_{module_name}.md", mime="text/markdown",
                        use_container_width=True)
    if rep.repaired_code:
        dl2.download_button("💾 Korrigierten Code herunterladen", data=rep.repaired_code,
                            file_name=f"{module_name}_fixed.py", mime="text/x-python",
                            use_container_width=True)
        with st.expander("🛠️ Vorgeschlagene korrigierte Version (Program Repair)"):
            st.code(rep.repaired_code, language="python")

    with st.expander("📄 Ausführungs-Log"):
        st.code("\n".join(rep.log))
else:
    st.info("Lade oben Code und klicke auf **Code reviewen**.")
