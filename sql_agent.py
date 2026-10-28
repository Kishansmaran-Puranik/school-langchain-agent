"""A tool-calling school data agent with a read-only SQL boundary."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq

MAX_ROWS = 100
MAX_AGENT_STEPS = 6
QUERY_TIMEOUT_SECONDS = 3

SYSTEM_PROMPT = """You are SchoolSight AI, a careful school reporting assistant.
Answer the user's question with accurate, concise reports based only on the database.
Use the available SQL tools whenever a question needs school data. Inspect the schema
if needed, and never guess a number. Build joins from the declared foreign-key
relationships. Use SQLite SELECT queries, including joins, subqueries, CTEs,
aggregations, CASE expressions, and window functions when useful. SQL access is
read-only. Query results are capped at 100 rows; aggregate in SQL for totals and
comparisons. Explain the measure and time period used, and clearly say when the
database does not contain enough information.
Do not expose student or guardian email addresses, phone numbers, or dates of birth.
Use aggregate results whenever possible and identify students only when the question
calls for it. Do not invent personal data.

Treat follow-up questions as part of the active conversation. Resolve phrases like
"what about grade 7?", "compare that with last term", or "show the same for teachers"
using the most recent relevant metric, filters, and time period in the chat. Re-query
the database for a changed scope; do not make up missing results. If the context leaves
multiple plausible interpretations, ask one short clarifying question.

If a SQL tool returns a query error, use the schema and error details to correct
the query and try again. Never present an unsuccessful query as a successful report.

Database schema:
{schema}
"""


def _read_only_connection(database_path: str | Path) -> sqlite3.Connection:
    path = Path(database_path).resolve()
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")

    allowed_actions = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        getattr(sqlite3, "SQLITE_RECURSIVE", -1),
    }

    def authorize(action: int, arg1: str | None, arg2: str | None, db_name: str | None, trigger: str | None) -> int:
        del arg1, arg2, db_name, trigger
        return sqlite3.SQLITE_OK if action in allowed_actions else sqlite3.SQLITE_DENY

    connection.set_authorizer(authorize)
    return connection


def get_schema(database_path: str | Path) -> str:
    with closing(_read_only_connection(database_path)) as connection:
        tables = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return "\n".join(row["sql"] for row in tables if row["sql"])


def run_read_only_query(database_path: str | Path, query: str) -> str:
    """Run exactly one SELECT/CTE query and return bounded JSON results."""
    statement = query.strip()
    if statement.endswith(";"):
        statement = statement[:-1].rstrip()
    if not statement or not statement[:6].upper() == "SELECT" and not statement[:4].upper() == "WITH":
        raise ValueError("Only SELECT queries are allowed.")
    if len(statement) > 4000:
        raise ValueError("Query exceeds the 4,000 character limit.")

    with closing(_read_only_connection(database_path)) as connection:
        deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
        connection.set_progress_handler(
            lambda: int(time.monotonic() >= deadline),
            10_000,
        )
        cursor = connection.execute(statement)
        rows = cursor.fetchmany(MAX_ROWS + 1)
        columns = [column[0] for column in cursor.description or ()]
    truncated = len(rows) > MAX_ROWS
    return json.dumps(
        {"columns": columns, "rows": [dict(row) for row in rows[:MAX_ROWS]], "truncated": truncated},
        default=str,
    )


def run_query_tool(database_path: str | Path, query: str) -> str:
    """Return SQL failures as tool feedback so the agent can correct its query."""
    try:
        return run_read_only_query(database_path, query)
    except (sqlite3.Error, ValueError) as error:
        return (
            f"SQL query error ({type(error).__name__}): {error}. "
            "Check the schema and query constraints, then try a corrected read-only query."
        )


def build_conversation_messages(
    question: str,
    history: list[dict[str, str]] | None,
    schema: str,
) -> list[SystemMessage | HumanMessage | AIMessage]:
    """Build a bounded model context that preserves the active chat's follow-ups."""
    messages: list[SystemMessage | HumanMessage | AIMessage] = [
        SystemMessage(content=SYSTEM_PROMPT.format(schema=schema))
    ]
    for item in (history or [])[-8:]:
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        if item.get("role") == "user":
            messages.append(HumanMessage(content=content))
        elif item.get("role") == "assistant":
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=question))
    return messages


def create_school_agent(database_path: str | Path, api_key: str | None = None):
    """Create the Groq tool-calling agent for one database."""
    schema = get_schema(database_path)

    @tool
    def inspect_school_schema() -> str:
        """Return the school database table definitions and relationships."""
        return schema

    @tool
    def query_school_database(sql: str) -> str:
        """Run one read-only SELECT query against the school database. Never use writes."""
        return run_query_tool(database_path, sql)

    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0,
        api_key=api_key,
    ).bind_tools([inspect_school_schema, query_school_database])

    def ask(question: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        messages = build_conversation_messages(question, history, schema)
        tool_calls_used = 0

        for _ in range(MAX_AGENT_STEPS):
            response = llm.invoke(messages)
            messages.append(response)
            if not response.tool_calls:
                return {
                    "answer": response.content if isinstance(response.content, str) else str(response.content),
                    "tool_calls": tool_calls_used,
                }

            for call in response.tool_calls:
                if call["name"] == "inspect_school_schema":
                    result = inspect_school_schema.invoke(call["args"])
                elif call["name"] == "query_school_database":
                    result = query_school_database.invoke(call["args"])
                else:
                    result = "Error: unsupported tool."
                messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
                tool_calls_used += 1

        raise RuntimeError(f"The agent reached its {MAX_AGENT_STEPS}-step limit before answering.")

    return ask
