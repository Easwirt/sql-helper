"""
Postgres MCP server runner for the sql-agent project.

Starts the postgres-mcp server pointed at the project's PostgreSQL database.
Can be run directly or via the `sql-agent-mcp` script entry point.

Usage:
    # Via entry point (after `uv sync`)
    sql-agent-mcp

    # Direct
    uv run python -m app.service.postgres_mcp

    # With options
    sql-agent-mcp --access-mode restricted
    sql-agent-mcp --transport sse --sse-port 8080
"""

import os
import sys

from app.config import load_project_env


load_project_env()

_DEFAULT_DB_URL = "postgresql://appuser:apppassword@localhost:5432/app_database"

if "DATABASE_URI" not in os.environ:
    os.environ["DATABASE_URI"] = os.getenv("DATABASE_URL", _DEFAULT_DB_URL)


def main() -> None:
    """Entry point that delegates to postgres_mcp.main()."""
    from postgres_mcp import main as _run

    _run()


if __name__ == "__main__":
    main()
