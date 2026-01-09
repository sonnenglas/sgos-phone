"""
MCP Server for Placetel Voicemail API

This exposes the API as MCP tools that can be used by
Claude and other LLM clients via the Model Context Protocol.

The MCP server connects to the running HTTP API, so make sure
the API is running first (docker compose up).

Usage:
    # Set the API URL (defaults to http://localhost:9000)
    export VOICEMAIL_API_URL=http://localhost:9000

    # Run the MCP server
    python -m app.mcp_server

Claude Code config (~/.claude/claude_desktop_config.json):
    {
        "mcpServers": {
            "voicemail": {
                "command": "python",
                "args": ["-m", "app.mcp_server"],
                "cwd": "/path/to/placetel-api",
                "env": {
                    "VOICEMAIL_API_URL": "http://localhost:9000"
                }
            }
        }
    }
"""

import os
import json
import httpx
from fastmcp import FastMCP

# API URL - defaults to local Docker setup
API_URL = os.environ.get("VOICEMAIL_API_URL", "http://localhost:9000")

# Load OpenAPI spec from file (committed to repo)
SPEC_PATH = os.path.join(os.path.dirname(__file__), "..", "openapi.json")

def create_mcp_server():
    """Create MCP server from OpenAPI spec."""

    # Load OpenAPI spec
    with open(SPEC_PATH, "r") as f:
        openapi_spec = json.load(f)

    # Create HTTP client for API requests
    client = httpx.AsyncClient(
        base_url=API_URL,
        timeout=60.0  # Longer timeout for transcription
    )

    # Create MCP server from OpenAPI spec
    mcp = FastMCP.from_openapi(
        openapi_spec=openapi_spec,
        client=client,
        name="voicemail"
    )

    return mcp

mcp = create_mcp_server()

if __name__ == "__main__":
    mcp.run()
