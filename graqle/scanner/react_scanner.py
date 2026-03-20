# ── graqle:intelligence ──
# module: graqle.scanner.react_scanner
# risk: LOW (impact radius: 1 modules)
# consumers: scan._scan_repo_impl
# dependencies: re, pathlib, networkx
# constraints: none
# ── /graqle:intelligence ──

"""React/JSX/TSX component scanner for Graqle.

Discovers React components, their render relationships (which components
render which), route definitions, and hook usage. Produces nodes and edges
that integrate into the existing knowledge graph.

Scans .tsx, .jsx, .ts, and .js files for:
- Component definitions (function/const with PascalCase + JSX return)
- Route-to-component mappings (React Router patterns)
- Component render relationships (<Component /> usage)
- Hook usage (useState, useEffect, custom hooks)
"""

import logging
import re
from pathlib import Path

import networkx as nx

logger = logging.getLogger("graqle.scanner.react")

# ── Regex patterns ────────────────────────────────────────────────────────

# Match: export default function MyComponent, export const MyComponent, function MyComponent
_COMPONENT_DEF_RE = re.compile(
    r"(?:export\s+(?:default\s+)?)?(?:function|const)\s+([A-Z][A-Za-z0-9]+)"
)

# Match: <MyComponent or <MyComponent> or <MyComponent />
_JSX_RENDER_RE = re.compile(r"<([A-Z][A-Za-z0-9.]+)[\s/>]")

# Match: React Router route definitions
# <Route path="/foo" element={<MyPage />} />
# { path: "/foo", element: <MyPage /> }
_ROUTE_RE = re.compile(
    r'(?:path[=:]\s*["\'])([^"\']+)["\'].*?(?:element[=:]\s*[{<]\s*<?([A-Z][A-Za-z0-9]+))',
    re.DOTALL,
)

# Match: useXxx hook calls
_HOOK_RE = re.compile(r"\buse([A-Z][A-Za-z0-9]+)\s*\(")

# File extensions to scan
_REACT_EXTENSIONS = frozenset({".tsx", ".jsx"})
_JS_EXTENSIONS = frozenset({".ts", ".js", ".tsx", ".jsx"})

# HTML elements to ignore in JSX render detection
_HTML_ELEMENTS = frozenset({
    "A", "B", "I", "P", "S", "U",  # Single-letter HTML tags (uppercase)
    "Br", "Hr", "Tr", "Td", "Th",  # Short HTML elements
    "Div", "Span", "Main", "Nav", "Header", "Footer", "Section", "Article",
    "Form", "Input", "Button", "Select", "Option", "Textarea",
    "Table", "Thead", "Tbody", "Tfoot",
    "Ul", "Ol", "Li", "Dl", "Dt", "Dd",
    "H1", "H2", "H3", "H4", "H5", "H6",
    "Img", "Video", "Audio", "Canvas", "Svg", "Path",
    "Label", "Fieldset", "Legend", "Details", "Summary",
    "Dialog", "Pre", "Code", "Blockquote", "Figure", "Figcaption",
})


def scan_react_components(
    repo_path: str | Path,
    *,
    exclude_patterns: list[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Scan a repository for React components and their relationships.

    Returns:
        Tuple of (nodes_list, edges_list) ready for graph integration.
    """
    repo = Path(repo_path).resolve()
    if not repo.exists():
        return [], []

    exclude = set(exclude_patterns or [])
    exclude.update({"node_modules", "dist", "build", ".next", "__pycache__", ".git"})

    nodes: list[dict] = []
    edges: list[dict] = []
    component_registry: dict[str, str] = {}  # component_name -> node_id
    routes: list[dict] = []

    # Find all JSX/TSX files
    react_files = []
    for ext in _REACT_EXTENSIONS:
        for f in repo.rglob(f"*{ext}"):
            if any(excl in f.parts for excl in exclude):
                continue
            react_files.append(f)

    if not react_files:
        return [], []

    logger.info("Scanning %d React files in %s", len(react_files), repo)

    for fpath in react_files:
        try:
            src = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        rel_path = str(fpath.relative_to(repo)).replace("\\", "/")

        # Detect component definitions
        components = _COMPONENT_DEF_RE.findall(src)
        file_components: list[str] = []

        for comp_name in components:
            node_id = f"{rel_path}::{comp_name}"
            file_components.append(comp_name)
            component_registry[comp_name] = node_id

            # Extract first line of component for description
            comp_match = re.search(
                rf"(?:function|const)\s+{re.escape(comp_name)}[^{{]*\{{",
                src,
            )
            desc = f"React component {comp_name} in {rel_path}"

            nodes.append({
                "id": node_id,
                "label": comp_name,
                "type": "ReactComponent",
                "description": desc,
                "file_path": rel_path,
            })

        # Detect JSX render relationships
        rendered = _JSX_RENDER_RE.findall(src)
        for rendered_comp in rendered:
            # Skip HTML elements and self-references
            base_name = rendered_comp.split(".")[0]
            if base_name in _HTML_ELEMENTS:
                continue
            for comp_name in file_components:
                if rendered_comp != comp_name:
                    source_id = f"{rel_path}::{comp_name}"
                    edges.append({
                        "source": source_id,
                        "target": rendered_comp,  # Resolved later
                        "relationship": "RENDERS",
                        "type": "RENDERS",
                    })

        # Detect route definitions
        for route_match in _ROUTE_RE.finditer(src):
            route_path, route_component = route_match.groups()
            routes.append({
                "path": route_path,
                "component": route_component,
                "file": rel_path,
            })

        # Detect hook usage
        hooks = _HOOK_RE.findall(src)
        custom_hooks = [h for h in hooks if h not in ("State", "Effect", "Memo", "Callback", "Ref", "Context", "Reducer")]
        for comp_name in file_components:
            for hook_name in custom_hooks:
                hook_id = f"use{hook_name}"
                edges.append({
                    "source": f"{rel_path}::{comp_name}",
                    "target": hook_id,
                    "relationship": "USES_HOOK",
                    "type": "USES_HOOK",
                })

    # Resolve render edge targets to actual node IDs
    for edge in edges:
        if edge["relationship"] == "RENDERS":
            target_name = edge["target"]
            if target_name in component_registry:
                edge["target"] = component_registry[target_name]
            # If not found, leave as-is — may reference external/library component

    # Add route nodes
    for route in routes:
        route_id = f"route:{route['path']}"
        nodes.append({
            "id": route_id,
            "label": f"Route {route['path']}",
            "type": "Route",
            "description": f"React route {route['path']} → {route['component']} in {route['file']}",
            "file_path": route["file"],
        })
        if route["component"] in component_registry:
            edges.append({
                "source": route_id,
                "target": component_registry[route["component"]],
                "relationship": "ROUTES_TO",
                "type": "ROUTES_TO",
            })

    logger.info(
        "React scan: %d components, %d routes, %d edges from %d files",
        len([n for n in nodes if n["type"] == "ReactComponent"]),
        len(routes),
        len(edges),
        len(react_files),
    )

    return nodes, edges
