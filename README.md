# mcfind

Offline, agent-friendly Minecraft Java structure lookup built on local cubiomes logic.

## Install

```bash
python3 -m pip install -e .
```

The first cubiomes-backed query compiles a local native adapter with `cc`.

## Examples

```bash
mcfind nearest --seed -461418396194504394 --edition java --version 1.21.11 --from 780 874 --structure stronghold
mcfind nearest --seed -461418396194504394 --edition java --version 1.21.11 --from 780 874 --structure trial_chamber --format json
mcfind within-radius --seed -461418396194504394 --version 1.21.11 --from 780 874 --radius 5000 --structure village
mcfind route --seed -461418396194504394 --version 1.21.11 --from 780 874 --structure village,trial_chamber,stronghold --limit 5 --format json
mcfind import-save ~/Games/Minecraft/saves/MyWorld --format json
mcfind profile add home --seed -461418396194504394 --version 1.21.11 --base 780 874
```

## MCP Server

Start the remote MCP server locally:

```bash
mcfind-mcp
```

By default it serves Streamable HTTP on `http://127.0.0.1:8000/mcp` with:

- `GET /`
- `GET /healthz`
- `POST /mcp`

Available MCP tools:

- `find_nearest_structure`
- `list_structures_in_radius`
- `optimize_structure_route`
- `get_seed_info`
- `import_java_save`

Optional environment variables:

```bash
export MCFIND_MCP_HOST=0.0.0.0
export MCFIND_MCP_PORT=8000
export MCFIND_MCP_PATH=/mcp
export MCFIND_MCP_NAME=mcfind
export MCFIND_MCP_PUBLIC_BASE_URL=https://your-subdomain.ngrok-free.dev
```

If you expose the server through ngrok or another public HTTPS tunnel, set `MCFIND_MCP_PUBLIC_BASE_URL` before starting the server. Otherwise the MCP SDK's default localhost-only DNS rebinding protection will reject public `Host` headers with `421 Misdirected Request`.

For ChatGPT developer-mode testing, expose the local server over HTTPS with a tunnel such as:

```bash
ngrok http 8000
```

Then use the HTTPS URL and the `/mcp` path when connecting the app in ChatGPT.
