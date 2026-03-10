"""kogni scan — auto-discover code-as-graph from a repository."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console

console = Console()
logger = logging.getLogger("cognigraph.cli.scan")

scan_app = typer.Typer(help="Scan a codebase to build a CogniGraph.")


@scan_app.command("repo")
def scan_repo(
    path: str = typer.Argument(".", help="Repository path to scan"),
    output: str = typer.Option("cognigraph.json", "--output", "-o"),
    depth: int = typer.Option(2, "--depth", "-d", help="Directory scan depth"),
) -> None:
    """Scan a code repository and build a knowledge graph.

    Discovers: services, APIs, configs, dependencies, and their relationships.
    Outputs a JSON graph file for use with `kogni run` or `kogni context`.
    """
    import networkx as nx

    repo = Path(path).resolve()
    if not repo.exists():
        console.print(f"[red]Path not found: {repo}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Scanning:[/cyan] {repo}")

    G = nx.Graph()
    node_count = 0

    # Discover Python files / Lambda handlers
    for py_file in repo.rglob("*.py"):
        if any(skip in str(py_file) for skip in [
            "__pycache__", ".git", "node_modules", ".venv", "venv"
        ]):
            continue

        rel_path = py_file.relative_to(repo)
        parts = list(rel_path.parts)

        # Add file as a node
        file_id = str(rel_path).replace("\\", "/")
        G.add_node(file_id, label=py_file.stem, type="PythonModule",
                   description=f"Python module: {rel_path}")
        node_count += 1

        # Add directory as parent node
        if len(parts) > 1:
            dir_id = "/".join(parts[:-1])
            if dir_id not in G:
                G.add_node(dir_id, label=parts[-2], type="Directory",
                           description=f"Directory: {dir_id}")
                node_count += 1
            G.add_edge(dir_id, file_id, relationship="CONTAINS")

        # Scan for imports to create edges
        try:
            content = py_file.read_text(errors="ignore")
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    # Extract module name
                    parts_line = line.split()
                    if line.startswith("from") and len(parts_line) >= 2:
                        module = parts_line[1]
                    elif len(parts_line) >= 2:
                        module = parts_line[1]
                    else:
                        continue

                    # Only track local imports
                    if module.startswith(".") or not any(
                        c in module for c in (".", "_")
                    ):
                        continue

                    # Add as dependency edge if target exists
                    target = module.replace(".", "/") + ".py"
                    if target in G:
                        G.add_edge(file_id, target, relationship="IMPORTS")
        except Exception:
            pass

    # Discover config files
    for pattern in ["*.yaml", "*.yml", "*.json", "*.toml", "*.env"]:
        for config_file in repo.glob(pattern):
            if ".git" in str(config_file):
                continue
            cfg_id = config_file.name
            G.add_node(cfg_id, label=config_file.stem, type="Config",
                       description=f"Configuration: {config_file.name}")
            node_count += 1

    # Save graph
    data = nx.node_link_data(G)
    Path(output).write_text(json.dumps(data, indent=2))

    console.print(f"[green]Scan complete:[/green] {node_count} nodes, {G.number_of_edges()} edges")
    console.print(f"[dim]Saved to: {output}[/dim]")
