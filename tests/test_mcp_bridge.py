from __future__ import annotations

import unittest

from starlette.testclient import TestClient

from mcfind.mcp_bridge import nearest_payload
from mcfind.mcp_server import create_http_app, create_server


class McpBridgeTests(unittest.TestCase):
    def test_nearest_payload_returns_cli_shape(self) -> None:
        payload = nearest_payload(seed=12345, structures=["stronghold"], top=1)
        self.assertEqual(payload["command"], "nearest")
        self.assertEqual(payload["results"][0]["structure"], "stronghold")

    def test_server_registers_expected_tools_and_routes(self) -> None:
        server = create_server()
        app = create_http_app(server)
        tool_names = [tool.name for tool in server._tool_manager.list_tools()]
        self.assertEqual(
            tool_names,
            [
                "find_nearest_structure",
                "list_structures_in_radius",
                "optimize_structure_route",
                "get_seed_info",
                "import_java_save",
            ],
        )
        route_paths = {route.path for route in app.routes}
        self.assertIn("/mcp", route_paths)
        self.assertIn("/", route_paths)
        self.assertIn("/health", route_paths)
        self.assertIn("/healthz", route_paths)

    def test_streamable_http_post_accepts_wildcard_accept_header(self) -> None:
        app = create_http_app()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.1.0"},
            },
        }

        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            response = client.post("/mcp", headers={"accept": "*/*"}, json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"]["serverInfo"]["name"], "mcfind")

    def test_streamable_http_options_supports_cors_preflight(self) -> None:
        app = create_http_app()

        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            response = client.options(
                "/mcp",
                headers={
                    "origin": "https://chatgpt.com",
                    "access-control-request-method": "POST",
                    "access-control-request-headers": "content-type",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "*")
