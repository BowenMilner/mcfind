from __future__ import annotations

import json
import os
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from mcfind.errors import McfindError
from mcfind.mcp_bridge import (
    import_save_payload,
    make_error_payload,
    nearest_biome_payload,
    nearest_payload,
    route_payload,
    seed_info_payload,
    within_radius_payload,
)


_JSON_MIME = "application/json"
_SSE_MIME = "text/event-stream"


def _split_media_types(accept_header: str) -> list[str]:
    return [media_type.strip() for media_type in accept_header.split(",") if media_type.strip()]


def _ensure_media_types(accept_header: str, required_media_types: Iterable[str]) -> str:
    media_types = _split_media_types(accept_header)
    if not media_types:
        return ", ".join(required_media_types)

    has_wildcard = any(media_type.startswith("*/*") for media_type in media_types)
    if not has_wildcard:
        return accept_header

    for required_media_type in required_media_types:
        if not any(media_type.startswith(required_media_type) for media_type in media_types):
            media_types.append(required_media_type)
    return ", ".join(media_types)


def _normalize_accept_header(method: str, accept_header: str) -> str:
    if method == "POST":
        return _ensure_media_types(accept_header, (_JSON_MIME,))
    if method == "GET":
        return _ensure_media_types(accept_header, (_SSE_MIME,))
    return accept_header


class _McpAcceptHeaderMiddleware:
    def __init__(self, app: ASGIApp, streamable_http_path: str) -> None:
        self.app = app
        self.streamable_http_path = streamable_http_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != self.streamable_http_path:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        normalized_headers: list[tuple[bytes, bytes]] = []
        accept_seen = False

        for key, value in scope.get("headers", []):
            if key.lower() == b"accept":
                accept_seen = True
                normalized_value = _normalize_accept_header(method, value.decode("latin-1"))
                normalized_headers.append((key, normalized_value.encode("latin-1")))
            else:
                normalized_headers.append((key, value))

        if not accept_seen and method in {"GET", "POST"}:
            normalized_value = _normalize_accept_header(method, "")
            normalized_headers.append((b"accept", normalized_value.encode("latin-1")))

        if normalized_headers:
            scope = dict(scope)
            scope["headers"] = normalized_headers

        await self.app(scope, receive, send)


def _json_result(payload: dict[str, Any]) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, indent=2, sort_keys=False))],
        structuredContent=payload,
        isError=False,
    )


def _tool_call(fn, **kwargs: Any) -> CallToolResult:
    try:
        return _json_result(fn(**kwargs))
    except McfindError as exc:
        payload = make_error_payload(exc)
    return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload, indent=2, sort_keys=False))],
            structuredContent=payload,
            isError=True,
        )


def _transport_security_from_env(host: str, port: int) -> TransportSecuritySettings | None:
    public_base_url = os.environ.get("MCFIND_MCP_PUBLIC_BASE_URL")
    disable_protection = os.environ.get("MCFIND_MCP_DISABLE_DNS_REBINDING_PROTECTION") == "1"
    if disable_protection:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    if not public_base_url:
        return None
    parsed = urlparse(public_base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("MCFIND_MCP_PUBLIC_BASE_URL must be a full URL such as https://example.ngrok-free.dev")
    allowed_hosts = [f"{parsed.netloc}", f"127.0.0.1:{port}", f"localhost:{port}", "[::1]:*"]
    allowed_origins = [f"{parsed.scheme}://{parsed.netloc}", f"http://127.0.0.1:{port}", f"http://localhost:{port}", "http://[::1]:*"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def create_server() -> FastMCP:
    host = os.environ.get("MCFIND_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCFIND_MCP_PORT", "8000"))
    server = FastMCP(
        name=os.environ.get("MCFIND_MCP_NAME", "mcfind"),
        instructions=(
            "Read-only Minecraft Java worldgen tools backed by local cubiomes logic. "
            "Use these tools for structure and biome lookups, radius searches, route planning, "
            "seed metadata, and Java save imports."
        ),
        host=host,
        port=port,
        streamable_http_path=os.environ.get("MCFIND_MCP_PATH", "/mcp"),
        json_response=True,
        stateless_http=True,
        transport_security=_transport_security_from_env(host, port),
    )

    readonly = ToolAnnotations(
        title="Read-only mcfind lookup",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @server.custom_route("/", methods=["GET"], name="root")
    async def root(_request):
        return PlainTextResponse("mcfind MCP server")

    @server.custom_route("/healthz", methods=["GET"], name="healthz")
    async def healthz(_request):
        return JSONResponse({"status": "ok"})

    @server.custom_route("/health", methods=["GET"], name="health")
    async def health(_request):
        return JSONResponse({"status": "ok"})

    @server.tool(
        name="find_nearest_structure",
        title="Find nearest structures",
        annotations=readonly,
        description="Find the nearest Minecraft Java structure or structures to a coordinate using local worldgen logic.",
    )
    def find_nearest_structure(
        seed: int,
        structures: list[str],
        version: str = "1.21.11",
        from_x: int = 0,
        from_z: int = 0,
        top: int = 1,
        dimension: str | None = None,
        chunk_version: str | None = None,
        explain: bool = False,
        ) -> CallToolResult:
        return _tool_call(
            nearest_payload,
            seed=seed,
            structures=structures,
            version=version,
            from_x=from_x,
            from_z=from_z,
            top=top,
            dimension=dimension,
            chunk_version=chunk_version,
            explain=explain,
        )

    @server.tool(
        name="find_nearest_biome",
        title="Find nearest biomes",
        annotations=readonly,
        description="Find the nearest Minecraft Java biome or biomes to a coordinate using local worldgen logic.",
    )
    def find_nearest_biome(
        seed: int,
        biomes: list[str],
        version: str = "1.21.11",
        from_x: int = 0,
        from_z: int = 0,
        top: int = 1,
        dimension: str | None = None,
        chunk_version: str | None = None,
        explain: bool = False,
    ) -> CallToolResult:
        return _tool_call(
            nearest_biome_payload,
            seed=seed,
            biomes=biomes,
            version=version,
            from_x=from_x,
            from_z=from_z,
            top=top,
            dimension=dimension,
            chunk_version=chunk_version,
            explain=explain,
        )

    @server.tool(
        name="list_structures_in_radius",
        title="List structures in radius",
        annotations=readonly,
        description="List Minecraft Java structures within a radius of a coordinate using local worldgen logic.",
    )
    def list_structures_in_radius(
        seed: int,
        structures: list[str],
        radius: int,
        version: str = "1.21.11",
        from_x: int = 0,
        from_z: int = 0,
        limit: int = 10,
        sort: str = "distance",
        dimension: str | None = None,
        chunk_version: str | None = None,
        explain: bool = False,
    ) -> CallToolResult:
        return _tool_call(
            within_radius_payload,
            seed=seed,
            structures=structures,
            radius=radius,
            version=version,
            from_x=from_x,
            from_z=from_z,
            limit=limit,
            sort=sort,
            dimension=dimension,
            chunk_version=chunk_version,
            explain=explain,
        )

    @server.tool(
        name="optimize_structure_route",
        title="Optimize route",
        annotations=readonly,
        description="Compute a greedy route order for visiting multiple Minecraft Java structures.",
    )
    def optimize_structure_route(
        seed: int,
        structures: list[str],
        version: str = "1.21.11",
        from_x: int = 0,
        from_z: int = 0,
        radius: int = 20000,
        limit: int = 5,
        chunk_version: str | None = None,
        explain: bool = False,
    ) -> CallToolResult:
        return _tool_call(
            route_payload,
            seed=seed,
            structures=structures,
            version=version,
            from_x=from_x,
            from_z=from_z,
            radius=radius,
            limit=limit,
            chunk_version=chunk_version,
            explain=explain,
        )

    @server.tool(
        name="get_seed_info",
        title="Get seed info",
        annotations=readonly,
        description="Return version normalization and supported structure information for a Minecraft Java seed.",
    )
    def get_seed_info(
        seed: int,
        version: str = "1.21.11",
        structures: list[str] | None = None,
        explain: bool = False,
    ) -> CallToolResult:
        return _tool_call(
            seed_info_payload,
            seed=seed,
            version=version,
            structures=structures,
            explain=explain,
        )

    @server.tool(
        name="import_java_save",
        title="Import Java save",
        annotations=readonly,
        description="Read a local Minecraft Java save folder and extract seed, spawn, and version metadata.",
    )
    def import_java_save(path: str) -> CallToolResult:
        return _tool_call(import_save_payload, path=path)

    return server


def create_http_app(server: FastMCP | None = None) -> Starlette:
    server = server or create_server()
    app = server.streamable_http_app()
    streamable_http_path = server.settings.streamable_http_path
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id", "mcp-protocol-version"],
    )
    app.add_middleware(_McpAcceptHeaderMiddleware, streamable_http_path=streamable_http_path)
    return app


def main() -> int:
    server = create_server()
    transport = os.environ.get("MCFIND_MCP_TRANSPORT", "streamable-http")
    try:
        if transport == "streamable-http":
            app = create_http_app(server)
            config = uvicorn.Config(
                app,
                host=server.settings.host,
                port=server.settings.port,
                log_level=server.settings.log_level.lower(),
            )
            uvicorn.Server(config).run()
        else:
            server.run(transport=transport)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
