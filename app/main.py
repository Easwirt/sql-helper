"""FastAPI app for the AI Data Analyst PoC."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.chat import router
from app.service.mcp_client import mcp_client

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop MCP client with the app."""
    await mcp_client.connect()
    yield
    await mcp_client.close()


app = FastAPI(title="AI Data Analyst", lifespan=lifespan)
app.include_router(router)