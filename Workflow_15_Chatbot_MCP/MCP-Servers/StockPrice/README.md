# MCP Server Setup Guide

A step-by-step guide to set up and run a Model Context Protocol (MCP) server using FastMCP.

## Installation Steps

- UV is a fast Python package manager. Install it using pip:
```bash
pip install uv
```
- Verify installation:
```bash
uv --version
```
- Create a new directory for your MCP server and initialize it:
```bash
mkdir mcp-server
cd mcp-server
uv init .
```
- This creates the necessary project structure with:
    - `pyproject.toml` - Project configuration
    - `.python-version` - Python version specification
    - `README.md` - Project documentation
- Add FastMCP to your project dependencies:
```bash
uv add fastmcp
```
- Create a file named `main.py` with your server code:
- Use the `MCP Inspector` to test your server interactively:
```bash
uv run fastmcp dev main.py
```
- To run your server normally:
```bash
uv run fastmcp run main.py
```
or
```bash
uv run fastmcp run main.py --transport http --host 0.0.0.0 --port 8000
```
- Automatically configure Claude Desktop to use your MCP server:

```bash
uv run fastmcp install claude-desktop main.py
```

## License

This project is licensed under the MIT License.