"""Tests for POST /chat Studio chat route (P7 slash commands + NLP routing)."""

# ── graqle:intelligence ──
# module: tests.test_studio.test_api_chat_route
# risk: LOW (impact radius: 0 modules)
# dependencies: pytest, fastapi, unittest.mock
# constraints: none
# ── /graqle:intelligence ──

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from graqle.studio.routes.api import router, _route_chat_message


def _make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.studio_state = {"graph": None}
    return app


# ── _route_chat_message unit tests ────────────────────────────────────────────


class TestRouteChatMessage:

    def test_slash_reason_routes_to_graq_reason(self):
        tool, args = _route_chat_message("/reason how does AuthService work?")
        assert tool == "graq_reason"
        assert "how does AuthService work?" in args["question"]

    def test_slash_context_routes_to_graq_context(self):
        tool, args = _route_chat_message("/context JwtModule")
        assert tool == "graq_context"
        assert args["name"] == "JwtModule"

    def test_slash_lessons_routes_to_graq_lessons(self):
        tool, args = _route_chat_message("/lessons CORS")
        assert tool == "graq_lessons"
        assert args["topic"] == "CORS"

    def test_slash_impact_routes_to_graq_impact(self):
        tool, args = _route_chat_message("/impact AuthService")
        assert tool == "graq_impact"
        assert args["node_name"] == "AuthService"

    def test_slash_preflight_routes_to_graq_preflight(self):
        tool, args = _route_chat_message("/preflight removing the rate limiter")
        assert tool == "graq_preflight"
        assert "rate limiter" in args["change_description"]

    def test_shorthand_r_routes_to_graq_reason(self):
        tool, args = _route_chat_message("/r what is the architecture?")
        assert tool == "graq_reason"

    def test_shorthand_ctx_routes_to_graq_context(self):
        tool, args = _route_chat_message("/ctx AuthService")
        assert tool == "graq_context"

    def test_plain_lesson_keyword_routes_to_graq_lessons(self):
        tool, args = _route_chat_message("show me lessons about database connections")
        assert tool == "graq_lessons"

    def test_plain_impact_keyword_routes_to_graq_impact(self):
        tool, args = _route_chat_message("what does AuthService affect downstream?")
        assert tool == "graq_impact"

    def test_plain_preflight_keyword_routes_to_graq_preflight(self):
        tool, args = _route_chat_message("is it safe to remove the CORS middleware?")
        assert tool == "graq_preflight"

    def test_generic_question_defaults_to_graq_reason(self):
        tool, args = _route_chat_message("how does the sync engine work?")
        assert tool == "graq_reason"
        assert "sync engine" in args["question"]

    def test_unknown_slash_command_falls_through_to_routing(self):
        """Unknown /cmd should fall through to plain-language routing."""
        tool, args = _route_chat_message("/unknowncmd how does the sync engine work?")
        # Falls through — routed by plain language; no keyword match → graq_reason
        assert tool == "graq_reason"


# ── HTTP route tests ──────────────────────────────────────────────────────────


class TestChatRoute:

    def test_missing_message_returns_400(self):
        client = TestClient(_make_app())
        resp = client.post("/api/chat", json={})
        assert resp.status_code == 400

    def test_empty_message_returns_400(self):
        client = TestClient(_make_app())
        resp = client.post("/api/chat", json={"message": "  "})
        assert resp.status_code == 400

    def test_valid_message_streams_routing_and_done(self):
        client = TestClient(_make_app())

        with patch(
            "graqle.plugins.mcp_dev_server.KogniDevServer.handle_tool",
            new_callable=AsyncMock,
            return_value='{"answer": "AuthService handles JWT tokens."}',
        ):
            resp = client.post("/api/chat", json={"message": "/context AuthService"})

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert "routing" in body
        assert "graq_context" in body
        assert "done" in body

    def test_tool_error_returns_error_event_not_500(self):
        client = TestClient(_make_app())

        with patch(
            "graqle.plugins.mcp_dev_server.KogniDevServer.handle_tool",
            side_effect=RuntimeError("graph not loaded"),
        ):
            resp = client.post("/api/chat", json={"message": "how does auth work?"})

        assert resp.status_code == 200  # SSE stream — never 500
        assert "error" in resp.text

    def test_slash_reason_calls_graq_reason(self):
        """Slash /reason must invoke graq_reason, not the default."""
        client = TestClient(_make_app())
        call_log = []

        async def _mock_handle_tool(name, arguments):
            call_log.append(name)
            return '{"answer": "ok"}'

        with patch(
            "graqle.plugins.mcp_dev_server.KogniDevServer.handle_tool",
            side_effect=_mock_handle_tool,
        ):
            client.post("/api/chat", json={"message": "/reason what is FooService?"})

        assert call_log == ["graq_reason"]
