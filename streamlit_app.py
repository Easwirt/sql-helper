"""
Streamlit UI for the SQL Agent PoC.

A simple chat interface that lets non-technical users ask data quality
questions and see how the AI queries the database on their behalf.
"""

import json
import os
import urllib.error
import urllib.request
import uuid

import streamlit as st

from app.config import load_project_env


load_project_env()

API_URL = os.getenv("STREAMLIT_API_URL", "http://localhost:8000/chat")

# Data quality dimensions mapped to starter questions
SAMPLE_INSIGHTS = {
    "Completeness": "How many rows have NULL or empty clearing_date?",
    "Validity": "What distinct currency and country values exist?",
    "Outliers": "Are there any unusually large or small transaction_value amounts?",
    "Distribution": "Show count of transactions by fiscal_year and posting_period.",
    "Summary": "Give me a quick data quality overview of the accrual_transactions table.",
}


def _init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "pending" not in st.session_state:
        st.session_state.pending = None


def _call_api(message: str, role: str, session_id: str) -> dict:
    payload = json.dumps({"message": message, "role": role, "session_id": session_id}).encode()
    req = urllib.request.Request(API_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())


def _send(message: str, role: str) -> None:
    if not message.strip():
        return
    st.session_state.messages.append({"role": "user", "content": message})
    try:
        data = _call_api(message, role, st.session_state.session_id)
        st.session_state.messages.append({
            "role": "assistant",
            "content": data.get("reply", ""),
            "tool_calls": data.get("tool_calls", []),
        })
    except urllib.error.HTTPError as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"API error {e.code}: {e.read().decode('utf-8', errors='replace')}",
            "tool_calls": [],
        })
    except urllib.error.URLError as e:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Cannot reach API at {API_URL}. Is the server running? ({e.reason})",
            "tool_calls": [],
        })


def main() -> None:
    st.set_page_config(
        page_title="AI Data Analyst",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _init_state()

    # Custom CSS for cleaner look
    st.markdown("""
    <style>
    .block-container { padding-top: 2rem; }
    .stChatMessage { border-radius: 0.5rem; }
    div[data-testid="stExpander"] { font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

    # --- Sidebar ---
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/combo-chart.png", width=64)
        st.title("AI Data Analyst")
        st.caption("PoC for Jäppinen Ltd.")

        st.divider()

        role = st.selectbox("Access role", ["controller", "operations", "finance"], index=0)

        if st.button("🔄 New conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.pending = None
            st.rerun()

        st.divider()

        # Sample Insights panel
        st.subheader("📋 Sample Insights")
        st.caption("Click a data quality dimension to ask about it:")
        for label, question in SAMPLE_INSIGHTS.items():
            if st.button(f"▸ {label}", key=label, use_container_width=True, help=question):
                st.session_state.pending = question

        st.divider()
        st.markdown(
            "<small>Powered by GPT-4o-mini + MCP</small>",
            unsafe_allow_html=True,
        )

    # --- Main chat area ---
    st.header("💬 Chat")

    # Display message history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tool_calls"):
                with st.expander("🔧 SQL queries executed"):
                    for tc in msg["tool_calls"]:
                        st.code(tc.get("arguments", {}).get("sql", str(tc)), language="sql")

    # Chat input
    prompt = st.chat_input("Ask about empty fields, outliers, or data quality...")
    if st.session_state.pending:
        prompt = st.session_state.pending
        st.session_state.pending = None

    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Querying the database..."):
                _send(prompt, role)
            latest = st.session_state.messages[-1]
            st.markdown(latest["content"])
            if latest.get("tool_calls"):
                with st.expander("🔧 SQL queries executed"):
                    for tc in latest["tool_calls"]:
                        st.code(tc.get("arguments", {}).get("sql", str(tc)), language="sql")


if __name__ == "__main__":
    main()