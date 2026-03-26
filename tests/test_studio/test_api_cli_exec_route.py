"""Tests for POST /cli/exec Studio API route (P3 MCP bridge)."""

# ── graqle:intelligence ──
# module: tests.test_studio.test_api_cli_exec_route
# risk: LOW (impact radius: 0 modules)
# dependencies: pytest, fastapi, unittest.mock
# constraints: none
# ── /graqle:intelligence ──

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from graqle.studio.routes.api import router


def _make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.studio_state = {"graph": None}
    return app


class TestCliExecRoute:

    def test_missing_tool_returns_400(self):
        client = TestClient(_make_app())
        resp = client.post("/api/cli/exec", json={"arguments": {}})
        assert resp.status_code == 400
        assert "tool" in resp.json()["error"].lower()

    def test_disallowed_tool_returns_400(self):
        client = TestClient(_make_app())
        resp = client.post("/api/cli/exec", json={"tool": "rm_rf", "arguments": {}})
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["error"].lower()

    def test_allowed_tool_streams_done_event(self):
        client = TestClient(_make_app())
        mock_result = '{"answer": "FooService is a service node."}'

        with patch(
            "graqle.plugins.mcp_dev_server.KogniDevServer.handle_tool",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client.post(
                "/api/cli/exec",
                json={"tool": "graq_context", "arguments": {"name": "FooService"}},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert "done" in body
        assert "FooService" in body

    def test_tool_error_streams_error_event(self):
        client = TestClient(_make_app())

        async def _boom(name, arguments):
            raise RuntimeError("Graph not loaded")

        with patch(
            "graqle.plugins.mcp_dev_server.KogniDevServer.handle_tool",
            side_effect=_boom,
        ):
            resp = client.post(
                "/api/cli/exec",
                json={"tool": "graq_reason", "arguments": {"query": "test"}},
            )

        assert resp.status_code == 200
        body = resp.text
        assert "error" in body
        assert "Graph not loaded" in body

    def test_invalid_json_returns_400(self):
        client = TestClient(_make_app())
        resp = client.post(
            "/api/cli/exec",
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    def test_both_graq_and_kogni_aliases_allowed(self):
        """graq_ and kogni_ are both valid tool prefixes."""
        client = TestClient(_make_app())

        with patch(
            "graqle.plugins.mcp_dev_server.KogniDevServer.handle_tool",
            new_callable=AsyncMock,
            return_value="ok",
        ):
            for tool in ("graq_context", "kogni_context", "graq_reason", "kogni_reason"):
                resp = client.post(
                    "/api/cli/exec",
                    json={"tool": tool, "arguments": {}},
                )
                assert resp.status_code == 200, f"Expected 200 for tool={tool}, got {resp.status_code}"
