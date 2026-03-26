"""Tests for v0.37.1 hotfixes: graq serve env var forwarding + from_json graph key guard."""

# ── graqle:intelligence ──
# module: tests.test_cli.test_serve
# risk: LOW (impact radius: 0 modules)
# dependencies: __future__, testing, main, graph
# constraints: none
# ── /graqle:intelligence ──

from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from graqle.cli.main import app
from graqle.core.graph import Graqle

runner = CliRunner()


class TestServeEnvVarForwarding:
    """Fix 1: graq serve must forward GRAQLE_CONFIG_PATH + GRAQLE_SERVE_CWD to uvicorn factory."""

    def test_serve_sets_config_path_env(self, tmp_path):
        """GRAQLE_CONFIG_PATH is set to absolute path before uvicorn.run is called."""
        config_file = tmp_path / "graqle.yaml"
        config_file.write_text("graph:\n  path: test.json\n")

        captured_env = {}

        def fake_uvicorn_run(*args, **kwargs):
            captured_env["GRAQLE_CONFIG_PATH"] = os.environ.get("GRAQLE_CONFIG_PATH")
            captured_env["GRAQLE_SERVE_CWD"] = os.environ.get("GRAQLE_SERVE_CWD")

        with patch("uvicorn.run", side_effect=fake_uvicorn_run):
            runner.invoke(app, ["serve", "--config", str(config_file), "--port", "19999"])

        assert captured_env.get("GRAQLE_CONFIG_PATH") is not None
        assert Path(captured_env["GRAQLE_CONFIG_PATH"]).is_absolute()
        assert captured_env["GRAQLE_CONFIG_PATH"] == str(config_file.resolve())

    def test_serve_sets_cwd_env(self, tmp_path):
        """GRAQLE_SERVE_CWD is set to the process CWD before uvicorn.run is called."""
        config_file = tmp_path / "graqle.yaml"
        config_file.write_text("graph:\n  path: test.json\n")

        captured_cwd = {}

        def fake_uvicorn_run(*args, **kwargs):
            captured_cwd["val"] = os.environ.get("GRAQLE_SERVE_CWD")

        with patch("uvicorn.run", side_effect=fake_uvicorn_run):
            runner.invoke(app, ["serve", "--config", str(config_file), "--port", "19999"])

        assert captured_cwd.get("val") is not None
        assert Path(captured_cwd["val"]).is_absolute()

    def test_serve_relative_config_resolves_absolute(self, tmp_path, monkeypatch):
        """A relative --config arg is stored as an absolute path in GRAQLE_CONFIG_PATH."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "graqle.yaml"
        config_file.write_text("graph:\n  path: test.json\n")

        captured = {}

        def fake_uvicorn_run(*args, **kwargs):
            captured["path"] = os.environ.get("GRAQLE_CONFIG_PATH")

        with patch("uvicorn.run", side_effect=fake_uvicorn_run):
            runner.invoke(app, ["serve", "--config", "graqle.yaml", "--port", "19999"])

        assert captured.get("path") is not None
        assert Path(captured["path"]).is_absolute()


class TestFromJsonGraphKeyGuard:
    """Fix 2: Graqle.from_json must not crash when data['graph'] is not a dict."""

    def _write_kg(self, path: Path, graph_val) -> None:
        """Write a minimal NetworkX-format KG JSON with the given graph key value."""
        data = {
            "directed": True,
            "multigraph": False,
            "graph": graph_val,
            "nodes": [],
            "links": [],
        }
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_from_json_with_string_graph_key(self, tmp_path):
        """from_json does not crash when data['graph'] is a string (mock artifact)."""
        kg = tmp_path / "test.json"
        self._write_kg(kg, "<MagicMock name='mock.to_networkx().graph' id='12345'>")
        g = Graqle.from_json(str(kg))
        assert isinstance(g, Graqle)

    def test_from_json_with_none_graph_key(self, tmp_path):
        """from_json does not crash when data['graph'] is None."""
        kg = tmp_path / "test.json"
        self._write_kg(kg, None)
        g = Graqle.from_json(str(kg))
        assert isinstance(g, Graqle)

    def test_from_json_with_list_graph_key(self, tmp_path):
        """from_json does not crash when data['graph'] is a list."""
        kg = tmp_path / "test.json"
        self._write_kg(kg, [])
        g = Graqle.from_json(str(kg))
        assert isinstance(g, Graqle)

    def test_from_json_with_dict_graph_key_still_works(self, tmp_path):
        """from_json still reads _meta correctly when data['graph'] is a proper dict."""
        kg = tmp_path / "test.json"
        self._write_kg(kg, {"_meta": {"embedding_model": "test", "embedding_dim": 0}})
        g = Graqle.from_json(str(kg))
        assert isinstance(g, Graqle)

    def test_from_json_with_empty_dict_graph_key(self, tmp_path):
        """from_json handles empty dict graph key (no _meta)."""
        kg = tmp_path / "test.json"
        self._write_kg(kg, {})
        g = Graqle.from_json(str(kg))
        assert isinstance(g, Graqle)
