"""SchoolSight AI Streamlit application."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError

from school_db import DATABASE_PATH, initialize_database
from sql_agent import create_school_agent

load_dotenv()


def get_groq_api_key() -> str | None:
    """Read the Groq key from the environment, local .env, or Streamlit secrets."""
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        return api_key
    try:
        return st.secrets.get("GROQ_API_KEY")
    except StreamlitSecretNotFoundError:
        return None


st.set_page_config(
    page_title="SchoolSight AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)
GROQ_API_KEY = get_groq_api_key()

st.markdown(
    """
    <style>
    :root {
      color-scheme: dark;
      --app-bg: #212121;
      --sidebar-bg: #171717;
      --surface: #2f2f2f;
      --surface-hover: #383838;
      --border: #3a3a3a;
      --text: #ececec;
      --muted: #a0a0a0;
      --accent: #c4b5fd;
    }
    html, body, [class*="css"] {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
    }
    .stApp { background: var(--app-bg); color: var(--text); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
      background: var(--sidebar-bg);
      border-right: 1px solid #2a2a2a;
    }
    [data-testid="stSidebar"] > div:first-child { padding: 1.15rem .8rem; }
    [data-testid="stMain"] .block-container {
      max-width: 900px;
      padding: 1.1rem 2rem 7rem;
    }
    h1, h2, h3 { color: var(--text) !important; letter-spacing: -.035em; }
    p, label, li { color: var(--text); }
    [data-testid="stCaptionContainer"] p,
    .stCaption { color: var(--muted) !important; }
    .brand {
      display: flex; align-items: center; gap: .65rem;
      padding: .2rem .35rem .8rem; color: var(--text);
      font-weight: 650; font-size: 1.02rem; letter-spacing: -.02em;
    }
    .brand-mark {
      display: grid; place-items: center; width: 30px; height: 30px;
      border-radius: 10px; background: #2c2938; color: #d7ccff; font-size: 1rem;
    }
    .topbar {
      min-height: 42px; display:flex; align-items:center;
      justify-content:space-between; margin-bottom: 1.8rem;
      color: #d7d7d7; font-size: .9rem;
    }
    .model-pill {
      padding: .32rem .62rem; border: 1px solid #414141;
      border-radius: 999px; color: #bebebe; font-size: .72rem;
      letter-spacing: .01em; background: #282828;
    }
    .welcome { text-align:center; margin: 15vh auto 2rem; max-width: 650px; }
    .welcome-mark {
      display:grid; place-items:center; width:48px; height:48px;
      margin: 0 auto 1.2rem; border:1px solid #48434f;
      border-radius:16px; background:#302c37; color:#d7ccff; font-size:1.35rem;
    }
    .welcome h1 { font-size: 2rem; font-weight: 600; margin: 0 0 .45rem; }
    .welcome p { color: #a8a8a8; font-size: .96rem; margin: 0; }
    .suggestion-heading {
      margin: 2.2rem 0 .7rem; color:#929292;
      font-size:.72rem; text-transform:uppercase; letter-spacing:.12em;
      text-align:left; font-weight:650;
    }
    .stButton > button {
      border: 1px solid var(--border); background: transparent; color: #dedede;
      border-radius: 12px; min-height: 2.7rem; font-size: .83rem;
      font-weight: 450; text-align:left; transition: background .15s, border-color .15s;
    }
    .stButton > button:hover {
      border-color: #5a5367; background: var(--surface-hover); color: #fff;
    }
    [data-testid="stSidebar"] .stButton > button {
      border: 0; min-height: 2.45rem; padding-left: .7rem;
      color: #c7c7c7; font-size: .83rem;
    }
    [data-testid="stSidebar"] .stButton > button:hover { background:#272727; }
    [data-testid="stSidebar"] [data-testid="stTextInput"] input {
      background:#242424; border:1px solid #383838; border-radius:10px;
      color:#ededed; font-size:.84rem;
    }
    [data-testid="stSidebar"] [data-testid="stTextInput"] input::placeholder {
      color:#858585;
    }
    [data-testid="stChatMessage"] {
      border: 0; background: transparent; padding: 1rem .35rem; gap: .9rem;
    }
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
      line-height: 1.7; color: #e6e6e6;
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
      margin-left: auto; width: fit-content; max-width: 82%;
      padding: .1rem .95rem; border: 1px solid #3c3c3c;
      border-radius: 20px; background: #303030;
    }
    [data-testid="stChatInput"] {
      border: 1px solid #484848; border-radius: 18px;
      background: #2f2f2f; box-shadow: 0 8px 32px #00000024;
    }
    [data-testid="stChatInput"]:focus-within {
      border-color: #666; box-shadow: 0 0 0 1px #666;
    }
    [data-testid="stChatInput"] textarea {
      color: #f0f0f0; caret-color: var(--accent);
    }
    [data-testid="stChatInput"] textarea::placeholder { color: #929292; }
    [data-testid="stChatInput"] button {
      background: #e8e8e8; color: #202020; border-radius: 11px;
    }
    [data-testid="stChatInput"] button:hover { background: #fff; }
    [data-testid="stAlert"] { border-radius: 12px; }
    hr { border-color: #303030; }
    @media (max-width: 640px) {
      [data-testid="stMain"] .block-container { padding: .8rem 1rem 6rem; }
      .welcome { margin-top: 9vh; }
      .welcome h1 { font-size: 1.65rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

initialize_database()
with closing(sqlite3.connect(DATABASE_PATH)) as connection:
    student_count = connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    teacher_count = connection.execute("SELECT COUNT(*) FROM teachers").fetchone()[0]
    section_count = connection.execute("SELECT COUNT(*) FROM sections").fetchone()[0]

suggestions = [
    "Which subjects have the highest average scores?",
    "Show attendance rates by grade level.",
    "Who are the top 5 students by average grade?",
    "Which students have attendance below 90%?",
]

if "chats" not in st.session_state:
    initial_chat_id = uuid4().hex
    old_messages = st.session_state.pop("messages", [])
    first_question = next(
        (message["content"] for message in old_messages if message.get("role") == "user"),
        "",
    )
    st.session_state.chats = {
        initial_chat_id: {
            "title": first_question[:42] or "New chat",
            "messages": old_messages,
        }
    }
    st.session_state.active_chat_id = initial_chat_id

if st.session_state.active_chat_id not in st.session_state.chats:
    st.session_state.active_chat_id = next(iter(st.session_state.chats))

with st.sidebar:
    st.markdown(
        '<div class="brand"><span class="brand-mark">✦</span>SchoolSight AI</div>',
        unsafe_allow_html=True,
    )
    if st.button("＋  New chat", key="new_chat", use_container_width=True):
        chat_id = uuid4().hex
        st.session_state.chats[chat_id] = {"title": "New chat", "messages": []}
        st.session_state.active_chat_id = chat_id
        st.rerun()

    st.text_input(
        "Search chats",
        key="chat_search",
        placeholder="⌕  Search conversations",
        label_visibility="collapsed",
    )
    search_term = st.session_state.chat_search.strip().casefold()
    filtered_chats = []
    for chat_id, chat in reversed(list(st.session_state.chats.items())):
        searchable_text = " ".join(
            [chat["title"]]
            + [message["content"] for message in chat["messages"] if message["role"] == "user"]
        ).casefold()
        if not search_term or search_term in searchable_text:
            filtered_chats.append((chat_id, chat))

    st.caption("RECENT")
    if not filtered_chats:
        st.caption("No conversations match your search.")
    for chat_id, chat in filtered_chats:
        label = chat["title"].replace("\n", " ").strip() or "New chat"
        if len(label) > 36:
            label = f"{label[:35]}…"
        if chat_id == st.session_state.active_chat_id:
            label = f"●  {label}"
        if st.button(label, key=f"open_chat_{chat_id}", use_container_width=True):
            st.session_state.active_chat_id = chat_id
            st.rerun()

    st.markdown("---")
    st.caption("YOUR SCHOOL")
    st.markdown(
        f"<div style='font-size:.84rem;color:#c5c5c5;line-height:1.9'>"
        f"{student_count} students · {teacher_count} teachers<br>"
        f"{section_count} sections · Fictional demo data</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.caption("Powered by Groq · GPT-OSS 120B")
    st.caption("Local SQLite · Read-only queries")

st.markdown(
    """
    <div class="topbar">
      <span>School reports</span>
      <span class="model-pill">openai/gpt-oss-120b</span>
    </div>
    """,
    unsafe_allow_html=True,
)

active_chat = st.session_state.chats[st.session_state.active_chat_id]
messages = active_chat["messages"]
for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if not messages:
    st.markdown(
        """
        <div class="welcome">
          <div class="welcome-mark">✦</div>
          <h1>What would you like to know?</h1>
          <p>Ask a question about your school. I’ll look up the data and summarize what I find.</p>
        </div>
        <div class="suggestion-heading">A few ideas to get started</div>
        """,
        unsafe_allow_html=True,
    )
    suggestion_columns = st.columns(2)
    for index, suggestion in enumerate(suggestions):
        with suggestion_columns[index % 2]:
            if st.button(suggestion, key=f"welcome_suggestion_{index}", use_container_width=True):
                st.session_state["suggested_question"] = suggestion

if not GROQ_API_KEY:
    st.caption("Add `GROQ_API_KEY` to `.env` to start a conversation.")

question = st.chat_input("Message SchoolSight AI…")
if "suggested_question" in st.session_state:
    question = st.session_state.pop("suggested_question")

if question:
    if not GROQ_API_KEY:
        st.error("Groq API key is missing. Add `GROQ_API_KEY` to your `.env` file and restart the app.")
        st.stop()
    messages.append({"role": "user", "content": question})
    if active_chat["title"] == "New chat":
        active_chat["title"] = question[:42]
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Looking through the school data…"):
            try:
                agent = create_school_agent(DATABASE_PATH, api_key=GROQ_API_KEY)
                previous = messages[:-1][-8:]
                result = agent(question, previous)
                answer = result["answer"]
                st.markdown(answer)
                if result["tool_calls"]:
                    st.caption(f"Used {result['tool_calls']} database tool call(s)")
            except Exception as error:
                st.error(f"Could not generate the report: {error}")
                st.stop()
    messages.append({"role": "assistant", "content": answer})
