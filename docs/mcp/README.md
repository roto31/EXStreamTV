# EXStreamTV MCP Server

The project includes a **Model Context Protocol (MCP)** server so that Cursor, Claude Desktop, or any MCP client can use EXStreamTV context (docs, config, API) during development and integration.

## What it provides

- **Tools** (callable by the AI):
  - `get_project_info` – Project name, version, description, features, doc paths
  - `search_documentation` – Search `docs/`, README, etc. for a query
  - `get_doc` – Full content of a doc by path or short name (e.g. INSTALLATION, QUICK_START)
  - `list_docs` – List documentation files with path and title
  - `get_config_schema` – `config.example.yaml` and config section overview
  - `get_api_overview` – API modules and main route categories

- **Resources** (read by URI):
  - `exstreamtv://docs/README` – README content
  - `exstreamtv://config/example` – Example config YAML

## Run the server

From the **project root** (`/Users/roto1231/Documents/XCode Projects/EXStreamTV`):

```bash
# With uv (recommended)
uv run python -m mcp_server

# Or with pip-installed deps
pip install 'mcp[cli]'   # or use requirements-dev.txt
python -m mcp_server
```

The server uses **stdio** transport: it reads JSON-RPC from stdin and writes responses to stdout. Do not use `print()` in the server; logging goes to stderr.

## Add to Cursor

1. Open **Cursor Settings** → **MCP** (or edit your MCP config file).
2. Add a server entry that runs the EXStreamTV MCP server from this project.

Example config (adjust the path to your project root):

```json
{
  "mcpServers": {
    "exstreamtv": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/roto1231/Documents/XCode Projects/EXStreamTV",
        "run",
        "python",
        "-m",
        "mcp_server"
      ]
    }
  }
}
```

If you use the project’s virtualenv instead of `uv`:

```json
{
  "mcpServers": {
    "exstreamtv": {
      "command": "/Users/roto1231/Documents/XCode Projects/EXStreamTV/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "/Users/roto1231/Documents/XCode Projects/EXStreamTV"
    }
  }
}
```

3. Restart Cursor (or reload MCP) so the new server is picked up.

## Add to Claude Desktop

Edit the Claude Desktop config (e.g. `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "exstreamtv": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/roto1231/Documents/XCode Projects/EXStreamTV",
        "run",
        "python",
        "-m",
        "mcp_server"
      ]
    }
  }
}
```

Use the same path and `uv`/`python` setup as in the Cursor section. Then restart Claude Desktop.

## Dependencies

- Python 3.10+
- MCP SDK: `mcp[cli]>=1.2.0` (in `requirements-dev.txt`)

Install dev deps:

```bash
pip install -r requirements-dev.txt
# or
uv sync
```

## Troubleshooting

- **Server not listed**: Ensure the path in `args` / `cwd` is the **project root** (where `README.md`, `exstreamtv/`, `mcp_server/`, and `docs/` live).
- **Import errors**: Run from project root and install `mcp[cli]` (or full `requirements-dev.txt`).
- **No tools in client**: Restart the client after changing MCP config; ensure the server process starts (check Cursor/Claude logs for MCP errors).
