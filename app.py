import os
import json
import re
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from engine import analyze_migration, load_project_data, validate_ai_response

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"

st.set_page_config(page_title="Migration Rehearsal", page_icon="🧭", layout="wide")

# Calm, compact styling
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1200px;}
.hero {padding: 1.35rem 1.5rem; border-radius: 16px; background: linear-gradient(120deg,#14253d,#234d6d); color: white; margin-bottom: 1rem;}
.hero h1 {color:white; margin:0; font-size:2.1rem;}
.hero p {color:#e2edf6; margin:.45rem 0 0 0; font-size:1rem;}
.small-muted {color:#65758b; font-size:.85rem;}
.finding {padding: .8rem 1rem; border:1px solid #dbe3ec; border-radius:12px; margin:.5rem 0;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
<h1>🧭 Migration Rehearsal</h1>
<p>Review database schema changes before deployment. Trace each warning to dependencies and historical evidence.</p>
</div>
""", unsafe_allow_html=True)

data = load_project_data(DATA_DIR)
if "analysis_history" not in st.session_state:
    st.session_state.analysis_history = []

with st.sidebar:
    st.header("Migration proposal")
    st.caption("This demo analyses a defined set of migration operations. It does not execute SQL.")
    operation = st.selectbox("Operation", ["Rename column", "Drop column", "Change column type"])
    table = st.selectbox("Table", sorted(data["schema"]["tables"].keys()))
    columns = data["schema"]["tables"][table]["columns"]
    column = st.selectbox("Column", columns)
    new_name = ""
    new_type = ""
    if operation == "Rename column":
        new_name = st.text_input("New column name", value=f"{column}_new")
    elif operation == "Change column type":
        new_type = st.selectbox("New type", ["VARCHAR", "INTEGER", "BIGINT", "BOOLEAN", "DATE", "TIMESTAMP", "DECIMAL"])
    target_env = st.selectbox("Target environment", ["Development", "Staging", "Production (review only)"])
    use_history = st.toggle("Include historical migration memory", value=True)
    analyze = st.button("Analyze migration", type="primary", use_container_width=True)
    st.divider()
    st.caption("Evidence-first: deterministic checks identify evidence; AI explains it. AI output is not proof.")

st.subheader("How this review works")
c1,c2,c3 = st.columns(3)
c1.metric("Schema tables", len(data["schema"]["tables"]))
c2.metric("Dependency records", len(data["dependencies"]))
c3.metric("Historical cases", len(data["history"]))

if analyze:
    result = analyze_migration(
        operation=operation, table=table, column=column,
        new_name=new_name.strip(), new_type=new_type,
        data=data, use_history=use_history
    )
    st.session_state.current_result = result
    st.session_state.analysis_history.insert(0, {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "operation": operation, "target": f"{table}.{column}",
        "findings": len(result["findings"]), "env": target_env
    })

result = st.session_state.get("current_result")
if not result:
    st.info("Choose a migration on the left and select **Analyze migration** to see an evidence-backed review.")
    st.markdown("#### Example scenario")
    st.write("Renaming `customers.customer_id` may affect billing, reporting, or service queries that still reference the old name.")
else:
    st.divider()
    st.subheader("Review results")
    st.caption(f"Proposed operation: {result['operation']} · Target: {result['target']} · Environment: {target_env}")
    if result["findings"]:
        sev_counts = {s: sum(1 for f in result["findings"] if f["severity"] == s) for s in ["High", "Medium", "Low"]}
        m1,m2,m3 = st.columns(3)
        m1.metric("High", sev_counts["High"])
        m2.metric("Medium", sev_counts["Medium"])
        m3.metric("Low", sev_counts["Low"])
    else:
        st.success("No findings were triggered by the current sample rules. This does not prove the migration is safe.")

    tab1,tab2,tab3,tab4 = st.tabs(["Findings", "Baseline vs enhanced", "Validation checklist", "AI explanation"])
    with tab1:
        if not result["findings"]:
            st.info("No findings. Confirm that schema and dependency data are complete.")
        for idx, f in enumerate(result["findings"], start=1):
            with st.container(border=True):
                st.markdown(f"**{idx}. {f['title']}** · `{f['severity']}`")
                st.write(f["explanation"])
                st.caption(f"Evidence: {f['evidence']}")
                st.write(f"Suggested check: {f['test']}")
                st.caption(f"Source: {f['source']}")
    with tab2:
        baseline = pd.DataFrame(result["baseline"])
        enhanced = pd.DataFrame(result["enhanced"])
        left,right = st.columns(2)
        with left:
            st.markdown("**Baseline: schema + explicit rules**")
            if baseline.empty: st.info("No baseline findings.")
            else: st.dataframe(baseline, use_container_width=True, hide_index=True)
        with right:
            st.markdown("**Enhanced: baseline + historical memory**")
            if enhanced.empty: st.info("No enhanced findings.")
            else: st.dataframe(enhanced, use_container_width=True, hide_index=True)
        st.caption("A difference between these outputs demonstrates this prototype's logic, not proven real-world accuracy.")
    with tab3:
        st.markdown("Use these checks as a starting point; adapt them to your actual database and deployment process.")
        for item in result["checklist"]:
            st.checkbox(item, value=False, key="check_"+re.sub(r"\W+","_",item))
        st.download_button("Download review as JSON", data=json.dumps(result, indent=2), file_name="migration_review.json", mime="application/json")
    with tab4:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            st.warning("Gemini is not configured. Set GEMINI_API_KEY as an environment variable, restart the app, and rerun the review.")
            st.code("GEMINI_API_KEY=your_key_here")
            st.markdown("[Get a Gemini API key in Google AI Studio](https://aistudio.google.com/apikey)")
        else:
            if st.button("Generate evidence-grounded explanation"):
                with st.spinner("Asking Gemini to explain the structured findings…"):
                    try:
                        from google import genai
                        client = genai.Client(api_key=api_key)
                        prompt = f"""
You are assisting with a pre-deployment database migration review.
Use only the evidence in the JSON below. Do not invent dependencies, incidents, outcomes, probabilities, or claim causation.
Clearly separate observed evidence from hypotheses. Give: (1) concise summary, (2) top risks, (3) targeted validation tests, (4) limitations.
If evidence is insufficient, say so.
JSON:
{json.dumps(result, ensure_ascii=False)}
"""
                        response = client.models.generate_content(
                            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                            contents=prompt
                        )
                        text_out = getattr(response, "text", None) or "Gemini returned no text."
                        st.markdown(text_out)
                    except Exception as e:
                        st.error(f"Gemini request failed: {e}")
                        st.caption("Check API key, model availability, network access, and the installed google-genai package.")

st.divider()
st.subheader("Recent analyses in this session")
if st.session_state.analysis_history:
    st.dataframe(pd.DataFrame(st.session_state.analysis_history), use_container_width=True, hide_index=True)
else:
    st.caption("Your recent analyses will appear here after you run one.")

st.caption("Prototype limitations: bundled data is synthetic; dependency coverage is incomplete; no SQL is executed; no automated production changes are made. Review findings with your database owner before acting.")
