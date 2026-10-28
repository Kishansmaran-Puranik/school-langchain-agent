# SchoolSight AI

**A school data analyst you can talk to.** SchoolSight AI is a portfolio-ready
natural-language reporting app built with Streamlit, LangChain, Groq, and SQLite.
Ask a question about school data in plain English; a tool-calling AI agent explores
the database, runs an analytical query, and explains the results.

> **Demo data only:** every person and record is fictional. This project is not a
> student information system. Do not send real student data to a public LLM. Any
> real-world use requires your organization's privacy, security, and compliance review.

## Features

- **ChatGPT-inspired dark chat UI** with searchable recent conversations, example
  questions, and a new-chat action. Chat history and follow-up context stay in the
  current Streamlit session and are not saved to the database.
- **Natural-language reporting** across students, teachers, sections, subjects, grades,
  enrollments, attendance, assignments, families, clubs, and school events.
- **Context-aware follow-ups:** ask a question, then refine it with prompts such as
  “What about grade 7?”, “Compare that with last term,” or “Show the same for Biology.”
  The active conversation provides context for follow-up questions.
- **Groq-hosted model:** `openai/gpt-oss-120b`, connected through LangChain's Groq integration.
- **Schema-aware tools:** the agent receives the SQLite table definitions and can inspect
  the schema or request database queries.
- **Analytical SQL:** multi-table joins, filters, aggregates, `GROUP BY`, subqueries,
  CTEs (`WITH`), `CASE` expressions, and SQLite-supported window functions.
- **Local demo database:** created and populated automatically on first launch.
- **Read-only query boundary:** SQL authorizer, read-only SQLite connection, 4,000-character
  query limit, a three-second query deadline, single-statement execution, and a maximum
  of 100 returned rows.
- **SQL error recovery:** query errors are fed back to the model so it can inspect the
  schema and attempt a corrected query instead of presenting a failed query as a report.
- **School overview:** student, teacher, section, subject, club, and assignment counts
  appear in the sidebar.

Example questions:

- Which subjects have the highest average scores?
- Show attendance rates by grade level.
- Who are the top five students by average grade?
- Compare average scores across subjects and grade levels.
- Which students have attendance below 90%?
- Rank students by average exam score within each section.
- Which assignments have the highest missing-submission rate?
- Which clubs have the most members?
- When is the next school event?

Follow up to narrow a result without repeating its context:

1. “Compare average scores by grade.”
2. “What about just Biology?”
3. “Now show the top three students in grade 8.”

## Architecture

```text
┌──────────────────────────────────────────────────────────┐
│ Streamlit app (app.py)                                   │
│ Dark chat UI · searchable chat history · prompt ideas    │
└──────────────────────────┬───────────────────────────────┘
                           │ question + recent chat history
                           ▼
┌──────────────────────────────────────────────────────────┐
│ LangChain agent (sql_agent.py)                           │
│ Groq ChatGroq: openai/gpt-oss-120b                       │
│ Schema context · tool-call loop · report response       │
└──────────────────────┬───────────────────┬──────────────┘
                       │ schema tool        │ SQL query tool
                       ▼                    ▼
┌─────────────────────────────┐  ┌────────────────────────┐
│ SQLite table definitions    │  │ Read-only SQLite layer │
│ and foreign-key relations   │  │ SELECT / WITH only     │
└─────────────────────────────┘  └────────────┬───────────┘
                                               ▼
                                  ┌────────────────────────┐
                                  │ school.db              │
                                  │ Fictional school data  │
                                  └────────────────────────┘
```

### Request flow

1. `app.py` initializes or upgrades the local database, displays the chat interface,
   and collects a question. Conversations can be searched and switched during the
   current session. Up to the last eight messages in the active conversation are
   passed as context.
2. `sql_agent.py` loads the database schema and creates a LangChain `ChatGroq` client
   configured for `openai/gpt-oss-120b` with tool calling enabled.
3. The model decides whether to inspect the schema, request a SQL query, or answer
   conversationally. The agent handles tool calls for up to six model turns.
4. The SQL tool runs the model-generated query on a read-only SQLite connection.
   Queries exceeding the three-second execution deadline are interrupted; results are
   serialized as JSON and capped at 100 rows. SQL errors are returned to the model so
   it can make a limited correction attempt within the agent's six-turn budget.
5. The model uses the query result to write a response, which is shown in the chat.
   When a follow-up changes the grade, subject, comparison, or time scope, the agent is
   instructed to carry over the prior metric and filters and query the database again.
   If context is still ambiguous, it should ask a brief clarifying question.

The agent can write complex **read queries**, including joins across related tables,
aggregations, subqueries, CTEs, `CASE` expressions, and window functions supported by
SQLite. It does not execute data or schema changes: `INSERT`, `UPDATE`, `DELETE`,
`CREATE`, `DROP`, `ALTER`, and other non-read actions are rejected by the database
authorizer. A query must be one `SELECT` or `WITH` statement, and it cannot exceed
4,000 characters.

LLMs can make mistakes. Check important reports, especially where a question could
have multiple valid business definitions (for example, the date range or denominator
for an attendance rate). This demo's guardrails are not a substitute for production
authentication, authorization, auditing, rate limiting, or privacy controls.

## Database

`school_db.py` creates or upgrades the schema and seeds fictional records in `school.db`.
It contains these 15 related tables:

| Table | Contents |
|---|---|
| `teachers` | Fictional faculty, departments, email addresses, and hire dates |
| `sections` | Grade level, section name, room number, and homeroom teacher |
| `students` | Fictional student profile and section enrollment |
| `subjects` | School subjects and departments |
| `enrollments` | Student, subject, teacher, and school-year assignments |
| `grades` | Quiz, project, and exam scores by term |
| `attendance` | Daily present, absent, late, and excused records |
| `guardians` | Fictional parent/guardian names and demo-only contact details |
| `student_guardians` | Student-to-guardian relationships and primary contact flag |
| `school_terms` | School years and Fall, Spring, and Summer term date ranges |
| `assignments` | Course assignments, term, due date, and maximum score |
| `assignment_submissions` | Submission status, submitted date, and score |
| `clubs` | Extracurricular clubs, faculty advisors, meeting days, and rooms |
| `club_memberships` | Student club participation and roles |
| `school_events` | School calendar events with dates and categories |

The demo contains 120 students across grades 6–12, 16 teachers, 14 sections, 10 subjects,
1,200 student-subject enrollments, 7,200 assessment grades, 2,400 assignments and
submissions, 120 fictional guardians, 6 clubs, 240 club memberships, and 10 school
events. Attendance covers recent weekdays and typically contains more than 10,000
records. The seeded records and scores are deterministic; school-year dates and
attendance dates are based on the date the database is initialized.

Initialization is idempotent: running the app again does not duplicate seeded
enrollments, grades, assignments, submissions, attendance, or memberships. If an older
demo `school.db` already exists, startup creates the new tables and adds the additional
records while preserving existing rows. `school.db` is generated locally and excluded
from Git. To start over, stop the app and remove the generated database; the next launch
will create and seed a fresh copy.

All people and contact details are fake sample data. The agent is instructed not to
return email addresses, phone numbers, or dates of birth.

## Requirements

- Python 3.10 or newer
- Internet access when asking the LLM (Groq API requests are made online)
- A Groq API key

## Get a Groq API key

1. Open [Groq Console](https://console.groq.com/) and sign in or create an account.
2. Open the **API Keys** page: [console.groq.com/keys](https://console.groq.com/keys).
3. Create a key, give it a recognizable label, and copy it when it is displayed.
   Treat it like a password; do not share it or commit it to GitHub.
4. Put the key in the project's `.env` file for local development, or in your hosting
   provider's private secrets settings when deploying.

Groq's service, model availability, rate limits, and free usage terms can change.
Check the current details in the Groq Console.

## Run locally

Open a terminal in the project directory.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` in a text editor and replace the placeholder with your Groq key:

```text
GROQ_API_KEY=gsk_your_actual_key_here
```

Then launch the app:

```powershell
python -m streamlit run app.py
```

If PowerShell prevents virtual-environment activation, use a terminal where activation
is permitted, or run the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Using `python -m streamlit` also works when the standalone `streamlit` command is not
on `PATH`.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Add your Groq key to `.env`, then run:

```bash
python -m streamlit run app.py
```

Streamlit prints a local URL (usually `http://localhost:8501`) when the app is running.
Open that URL in your browser. The SQLite database is initialized automatically.

The app reads the key from the `GROQ_API_KEY` environment variable or Streamlit
secrets. `python-dotenv` loads the local `.env` file into the environment.

### Protect your API key

- Keep the actual key in `.env`, not in Python source code or README examples.
- `.env` and `school.db` are listed in `.gitignore`; do not force-add either file.
- If a key is accidentally exposed, revoke it in Groq Console and create a replacement.
- Do not use real student information with this public-model demo.

If you launch the app without a key, the interface still opens, but asking questions
requires `GROQ_API_KEY`. After changing `.env`, restart the Streamlit process.

## Run the tests

The unit tests do not need a Groq key:

```powershell
python -m unittest discover -s tests -v
```

They verify the expanded schema and record counts, idempotent seeding and table
recreation, result truncation, query rejection, recoverable SQL errors, follow-up
context, database integrity, and an analytical query combining joins, aggregation,
a CTE, and a window function.

## Deploy (optional)

For a simple public demo, push the project to GitHub and deploy the repository with
[Streamlit Community Cloud](https://share.streamlit.io/):

1. Sign in to Streamlit Community Cloud and connect your GitHub account.
2. Create an app from your repository, select the branch, and set the main file to
   `app.py`.
3. In the app's **Settings → Secrets**, add:

   ```toml
   GROQ_API_KEY = "gsk_your_actual_key_here"
   ```

4. Deploy and wait for the app to finish building.

The app reads the key from Streamlit secrets, so no code changes are needed for hosting.
Do not put the key into a committed `.env` file. The SQLite database is generated when
the app starts; files on hosted app instances may be ephemeral, so this demo database
should be treated as disposable and reproducible.

## Publish the project on GitHub

Create a new repository on GitHub (for example, `schoolsight-ai`), then run these
commands from the project directory. Replace the URL with your own repository URL.

```powershell
git init
git add .
git status
git commit -m "Build SchoolSight AI school reporting agent"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/schoolsight-ai.git
git push -u origin main
```

Before committing, use `git status` to check that `.env`, `.venv`, and `school.db` are
not staged. The project `.gitignore` excludes them by default.

## Troubleshooting

| Issue | What to try |
|---|---|
| `streamlit` is not recognized | Run `python -m streamlit run app.py` instead. |
| `No module named streamlit` | Activate `.venv`, then run `python -m pip install -r requirements.txt`. |
| Groq API key is missing | Check that `.env` is in the project directory and contains `GROQ_API_KEY=...`; restart the app. |
| Authentication or API error | Check the key in Groq Console, account/model availability, and network access. |
| Port 8501 is already in use | Start on another port: `python -m streamlit run app.py --server.port 8502`. |
| Need to reset the demo data | Stop the app, remove `school.db`, then restart the app. |

## Project structure

```text
.
├── app.py                  # Streamlit dark chat UI and app flow
├── school_db.py            # SQLite schema, upgrade path, and fictional seed data
├── sql_agent.py            # Groq / LangChain agent, follow-up context, safe SQL tools
├── requirements.txt        # Python dependencies
├── .env.example            # Safe template for the Groq API key
├── .gitignore              # Excludes secrets, generated database, and Python artifacts
├── .streamlit/
│   └── config.toml         # Dark Streamlit theme defaults
└── tests/
    └── test_sql_agent.py   # Database, SQL boundary, and analytical query tests
```
## Screenshots

<img width="1917" height="866" alt="image" src="https://github.com/user-attachments/assets/57a75451-1a95-41ff-a673-c834962a04f9" />

<img width="1917" height="865" alt="image" src="https://github.com/user-attachments/assets/3e95e1a5-7780-44f2-be7e-8bd0e47e08c6" />

<img width="1917" height="858" alt="image" src="https://github.com/user-attachments/assets/b4e22d26-2c8c-4c99-970c-75dec640d550" />
