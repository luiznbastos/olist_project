import json
import os

import requests
import streamlit as st

st.set_page_config(page_title="Olist Data Assistant", page_icon="🛒", layout="centered")
st.title("🛒 Olist Data Assistant")

AGENT_URL = os.environ.get("AGENT_URL", "http://localhost:8001/ask")


def _stringify(value):
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def render_tool_calls(sources):
    if not sources:
        return
    with st.expander(f"🔧 Tool calls ({len(sources)})", expanded=False):
        for i, source in enumerate(sources, start=1):
            tool = source.get("tool", "unknown")
            st.markdown(f"**{i}. `{tool}`**")

            st.caption("Input")
            st.code(_stringify(source.get("input", {})), language="json")

            st.caption("Output")
            st.code(_stringify(source.get("content", "")), language="markdown")

            if i < len(sources):
                st.divider()


if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            render_tool_calls(msg.get("sources", []))

if prompt := st.chat_input("Ask a question about the Olist dataset..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        sources = []
        with st.spinner("Thinking..."):
            try:
                resp = requests.post(AGENT_URL, json={"query": prompt}, timeout=120)
                resp.raise_for_status()
                payload = resp.json()
                answer = payload.get("response", "")
                sources = payload.get("sources", []) or []
            except requests.exceptions.ConnectionError:
                answer = f"Cannot reach the agent at `{AGENT_URL}`. Is olist_agent running?"
            except Exception as e:
                answer = f"Error contacting agent: {e}"
        st.markdown(answer)
        render_tool_calls(sources)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )
