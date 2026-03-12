"""
MCP client that connects to the postgres-mcp server over stdio.

Manages the subprocess lifecycle and exposes helpers for listing tools
and calling them from the OpenAI tool-calling loop.
"""

import json
import logging
import os
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.config import load_project_env


load_project_env()

logger = logging.getLogger(__name__)

_DEFAULT_DB_URL = "postgresql://appuser:apppassword@localhost:5432/app_database"
_DEFAULT_DB_SCHEMA = "public"


class McpClient:
    """Thin wrapper around an MCP ClientSession connected to postgres-mcp."""

    def __init__(self) -> None:
        self._exit_stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: list[dict] = []
        self._schema_context: str = ""

    # -- lifecycle ----------------------------------------------------------

    async def connect(self) -> None:
        """Spawn the postgres-mcp server and open a client session."""
        db_url = os.getenv(
            "DATABASE_URI",
            os.getenv("DATABASE_URL", _DEFAULT_DB_URL),
        )
        db_schema = os.getenv("DATABASE_SCHEMA", _DEFAULT_DB_SCHEMA)

        venv_bin = os.path.join(os.path.dirname(sys.executable), "postgres-mcp")

        server_params = StdioServerParameters(
            command=venv_bin,
            args=[db_url],
            env={
                **os.environ,
                "DATABASE_URI": db_url,
            },
        )

        transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params),
        )
        read_stream, write_stream = transport
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream),
        )
        await self._session.initialize()

        result = await self._session.list_tools()
        self._tools = [_mcp_tool_to_openai(t) for t in result.tools]
        logger.info(
            "MCP client connected — %d tools available: %s",
            len(self._tools),
            [t["function"]["name"] for t in self._tools],
        )

        from app.service.sql_validator import ALLOWED_TABLES

        schema_parts: list[str] = []
        for table in sorted(ALLOWED_TABLES):
            try:
                detail = await self._session.call_tool(
                    "get_object_details",
                    {"schema_name": db_schema, "object_name": table},
                )
                for block in detail.content:
                    if hasattr(block, "text") and block.text:
                        schema_parts.append(block.text)
            except Exception as exc:
                logger.warning(
                    "Could not fetch schema for table %s in schema %s: %s",
                    table,
                    db_schema,
                    exc,
                )
        self._schema_context = "\n\n".join(schema_parts)

    async def close(self) -> None:
        """Tear down the session and kill the subprocess."""
        await self._exit_stack.aclose()
        self._session = None
        self._tools = []
        self._schema_context = ""

    # -- public API ---------------------------------------------------------

    @property
    def openai_tools(self) -> list[dict]:
        """MCP tools already converted to the OpenAI *tools* array format."""
        return self._tools

    @property
    def schema_context(self) -> str:
        """Schema details for allowed tables, fetched from MCP at startup."""
        return self._schema_context

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Call an MCP tool and return its text result."""
        if self._session is None:
            raise RuntimeError("MCP client is not connected")
        result = await self._session.call_tool(name, arguments)
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts) if parts else "(no output)"


# -- helpers ----------------------------------------------------------------


def _mcp_tool_to_openai(tool) -> dict:
    """Convert an ``mcp.types.Tool`` to an OpenAI *function-tool* dict."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


# Singleton used across the app
mcp_client = McpClient()
