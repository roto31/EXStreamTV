"""
EXStreamTV MCP Server package.

Model Context Protocol server exposing project documentation, config schema,
and API overview for use in Cursor, Claude Desktop, and other MCP clients.

Run: python -m mcp_server
"""

from mcp_server.server import mcp

__all__ = ["mcp"]
