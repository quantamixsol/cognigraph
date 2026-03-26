"""Tests for GET /projects Studio API route (P6 cross-project federation)."""

# ── graqle:intelligence ──
# module: tests.test_studio.test_api_projects_route
# risk: LOW (impact radius: 0 modules)
# dependencies: pytest, fastapi, unittest.mock
# constraints: none
# ── /graqle:intelligence ──

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from graqle.studio.routes.api import router


def _make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.studio_state = {"graph": None}
    return app


def _mock_s3_paginator(project_names: list[str]):
    """Build a mock S3 paginator that returns the given project names."""
    prefix = "graphs/somehash/"
    common_prefixes = [{"Prefix": f"{prefix}{name}/"} for name in project_names]
    mock_page = {"CommonPrefixes": common_prefixes}

    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [mock_page]
    return mock_paginator


class TestProjectsRoute:

    def test_no_auth_returns_401(self):
        client = TestClient(_make_app())
        resp = client.get("/api/projects")
        assert resp.status_code == 401
        data = resp.json()
        assert data["projects"] == []

    def test_returns_sorted_project_list(self):
        client = TestClient(_make_app())
        paginator = _mock_s3_paginator(["graqle-studio", "graqle-sdk", "crawlq"])

        mock_s3 = MagicMock()
        mock_s3.get_paginator.return_value = paginator

        with patch("boto3.client", return_value=mock_s3):
            resp = client.get(
                "/api/projects",
                headers={"x-user-email": "test@example.com"},
            )

        assert resp.status_code == 200
        data = resp.json()
        names = [p["name"] for p in data["projects"]]
        assert names == sorted(names)
        assert "graqle-sdk" in names
        assert "graqle-studio" in names

    def test_count_matches_project_list(self):
        client = TestClient(_make_app())
        paginator = _mock_s3_paginator(["proj-a", "proj-b", "proj-c"])

        mock_s3 = MagicMock()
        mock_s3.get_paginator.return_value = paginator

        with patch("boto3.client", return_value=mock_s3):
            resp = client.get(
                "/api/projects",
                headers={"x-user-email": "test@example.com"},
            )

        data = resp.json()
        assert data["count"] == len(data["projects"])
        assert data["count"] == 3

    def test_s3_error_returns_empty_gracefully(self):
        """S3 failure must not raise — return empty list with error message."""
        client = TestClient(_make_app())

        mock_s3 = MagicMock()
        mock_s3.get_paginator.side_effect = Exception("S3 access denied")

        with patch("boto3.client", return_value=mock_s3):
            resp = client.get(
                "/api/projects",
                headers={"x-user-email": "test@example.com"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["projects"] == []
        assert "error" in data

    def test_empty_bucket_returns_empty_list(self):
        client = TestClient(_make_app())
        paginator = _mock_s3_paginator([])

        mock_s3 = MagicMock()
        mock_s3.get_paginator.return_value = paginator

        with patch("boto3.client", return_value=mock_s3):
            resp = client.get(
                "/api/projects",
                headers={"x-user-email": "test@example.com"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["projects"] == []
        assert data["count"] == 0
