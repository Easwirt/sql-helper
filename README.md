# Accruals SQL Helper — PoC

A chat tool that lets finance users ask plain-English questions about accrual transactions. No SQL knowledge needed.

---

## 1. How to Run

### Requirements

- Docker and Docker Compose
- An OpenAI API key

### Steps

```bash
# 1. Clone the repo
git clone git@github.com:Easwirt/sql-helper.git
cd sql-helper

# 2. Add your API key
cp .env.example .env
# Open .env and set OPENAI_API_KEY=your-key-here

# 3. Start everything
docker compose up --build

# 4. Load the data (first time only)
docker compose exec api python scripts/ingest.py

# 5. Open the app
# Streamlit UI → http://localhost:8501
# FastAPI docs → http://localhost:8000/docs
```

### Run tests

```bash
docker compose exec api pytest tests/
```

---

## 2. What I Built and Why

### What it does

- Users type a question in a chat window (for example: _"How many rows have a missing clearing date?"_)
- The app sends the question to GPT-4o-mini
- The model decides what SQL to run, runs it, and returns a plain-English answer
- The UI shows the answer and the SQL that was used

### Main parts

| Layer           | Tool                       |
| --------------- | -------------------------- |
| UI              | Streamlit                  |
| API             | FastAPI                    |
| AI model        | GPT-4o-mini (tool calling) |
| SQL safety      | Custom validator           |
| Database bridge | MCP + postgres-mcp         |
| Database        | PostgreSQL 16              |

### Why these choices

**Tool calling instead of free-form SQL generation.** Asking the model to just "write SQL" is unpredictable. With tool calling, the model can run queries, check results, and ask more questions before it answers. This gives better results on follow-up questions.

**Code-level security, not prompt-level.** I did not rely on the prompt to keep data safe. Before any SQL reaches the database, a validator rewrites the query to add the correct `WHERE` filter based on the user's role. The model cannot bypass this.

**Role-based data scoping.** Finance users should not see operations data, and vice versa. The access rules are simple but they work:

- `operations` → authorization group 40
- `finance` → authorization group 60
- `controller` → both 40 and 60

**Transparent UI.** The app shows the SQL it ran. This is important for finance users who need to trust the answer.

**MCP for database access.** Using an MCP server keeps the database layer separate from the model layer. The model can only call two tools: run a query, or explain a query. It cannot call admin tools.

---

## 3. What I Did Not Do

### Left out intentionally

- **Real authentication.** The role selector in the sidebar is for demo purposes only. A real system would need login tokens and server-side role assignment.
- **Full SQL parsing.** The validator uses pattern matching, not a proper SQL parser. It works for this dataset, but it is not bulletproof for complex queries.
- **Cross-table queries.** The agent only works on `accrual_transactions`. Adding more tables would need more work on the system prompt and the validator.
- **Persistent sessions.** Conversation history lives in memory. If the server restarts, it is gone.

### Would add next

- Replace the pattern-matching validator with a real SQL parser (for example, `sqlglot`)
- Move session storage to a database (Redis or Postgres)
- Add proper login and server-side role control
- Write more unit tests for the validator and the agent loop
- Move row-level security into the database itself (Postgres RLS policies)
- Support more tables as the schema grows

---

## 4. How My Approach Evolved

I started with a simple idea: send the user's question to GPT-4o-mini and ask it to return SQL. That worked for easy questions, but the results were not reliable. The model sometimes forgot to filter by authorization group. It also sometimes returned SQL that was hard to read.

The first big change was switching to tool calling. Instead of generating SQL in one step, the model now calls a tool, checks the result, and can ask more questions if needed. This made the answers much better, especially for follow-up questions.

The second big change was moving security out of the prompt and into code. At first, I put the access rules in the system prompt and asked the model to follow them. This was fragile — a slightly different question could make the model forget the rule. The `apply_authorization_scope()` function solved this. It rewrites the SQL after the model generates it, so the filter is always there.

The third change was adding **MCP** instead of connecting to Postgres directly. At first, the agent ran SQL directly through SQLAlchemy. Switching to MCP gave a cleaner boundary between the model layer and the database layer, and made it easier to control which tools the model could use.

By the end, the architecture was more complex than I planned, but each layer has a clear job:

- The model decides what to ask
- The validator decides what is safe to run
- The MCP server decides how to run it

---

## Look at the demo

link
