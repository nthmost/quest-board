"""Build docs/index.json: a {nodes, edges} graph from doc frontmatter.

Walks the repo's Markdown design docs (root + docs/**), extracts YAML
frontmatter, and emits a machine-readable graph for humans, LLMs, and graph
viewers (Cytoscape/D3, or Obsidian via wikilinks). See docs/README.md for the
schema. Run from the repo root:

    python -m scripts.build_docs_index
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
OUTPUT = DOCS_DIR / "index.json"
OVERVIEW = DOCS_DIR / "OVERVIEW.md"

# Public repo, for "read in the source document" links out of the graph/text views.
REPO_BLOB = "https://github.com/nthmost/quest-board/blob/main/"
# Chars of a doc's body kept inline in the index as a preview (full text via the link).
BODY_CAP = 1400

# Order + headings for the textual OVERVIEW.md, grouped by node type.
TYPE_SECTIONS = (
    ("feature", "Shipped features"),
    ("decision", "Decisions"),
    ("proposal", "Proposals"),
    ("idea", "Ideas"),
    ("spec", "Specs"),
    ("reference", "Reference docs"),
    ("note", "Notes"),
    ("status", "Status docs"),
    ("runbook", "Runbooks"),
)
# Lifecycle order, used to sort/subgroup nodes within a section.
STATUS_ORDER = (
    "shipped", "accepted", "building", "proposed", "exploring",
    "idea", "deferred", "rejected", "superseded", "unknown",
)

# Frontmatter fields that declare typed edges, mapped to the edge relation.
EDGE_FIELDS = {
    "supersedes": "supersedes",
    "superseded_by": "superseded_by",
    "depends_on": "depends_on",
    "blocks": "blocks",
    "relates_to": "relates_to",
    "realizes": "realizes",
}

# Where indexable docs live, relative to the repo root.
SCAN_GLOBS = ("*.md", "docs/**/*.md")

# Registry tables ingested as lightweight nodes: (path, node type, default status).
# Each file's first Markdown pipe-table becomes a set of nodes keyed by an `id`
# column. Detailed nodes still live as their own frontmatter files (which win on
# id collision); these tables are the home for shipped-feature and raw-idea rows.
REGISTRIES = (
    ("docs/features/FEATURES.md", "feature", "shipped"),
    ("docs/ideas/BACKLOG.md", "idea", "idea"),
)

# Table columns that declare edges (comma-separated node ids in the cell).
TABLE_EDGE_FIELDS = (
    "supersedes", "superseded_by", "depends_on", "blocks", "relates_to", "realizes",
)


def find_markdown() -> list[Path]:
    """Every indexable Markdown file, de-duplicated and sorted."""
    seen: set[Path] = set()
    for pattern in SCAN_GLOBS:
        seen.update(REPO_ROOT.glob(pattern))
    return sorted(seen)


def read_doc(path: Path) -> tuple[dict | None, str]:
    """Return (frontmatter dict | None, body markdown after the fence)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None, ""
    end = text.find("\n---", 4)
    if end == -1:
        return None, ""
    fm = yaml.safe_load(text[4:end])
    rest = text[end + 4:]
    body = rest.split("\n", 1)[1] if "\n" in rest else ""
    return (fm if isinstance(fm, dict) else None), body.strip()


def to_node(path: Path, fm: dict, body: str = "") -> dict:
    """Project frontmatter + body into a graph node."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    return {
        "id": fm.get("id") or path.stem,
        "title": fm.get("title") or path.stem,
        "type": fm.get("type", "note"),
        "status": fm.get("status", "unknown"),
        "path": rel,
        "tags": fm.get("tags") or [],
        "owners": fm.get("owners") or [],
        "updated": str(fm.get("updated", "")),
        "reason": fm.get("reason", ""),
        "origin": "doc",
        "body": _cap(body),
        "source": _source_link(fm.get("source"), rel, fm.get("reason", ""), infer=False),
    }


def _cap(body: str) -> str:
    """Trim a long body to a preview; the full text lives behind the source link."""
    if len(body) <= BODY_CAP:
        return body
    return body[:BODY_CAP].rstrip() + "\n\n… *(truncated — open the source document for the full text)*"


def _source_link(explicit: str | None, own_path: str, reason: str, infer: bool) -> dict:
    """Resolve the 'source document' for a node: a GitHub blob URL (+ optional anchor)."""
    spec = explicit or (_infer_source(reason) if infer else None) or own_path
    doc_path, _, anchor = spec.partition("#")
    url = REPO_BLOB + doc_path + (f"#{anchor}" if anchor else "")
    return {"label": doc_path.split("/")[-1], "url": url, "anchor": anchor}


def _infer_source(reason: str) -> str | None:
    """Guess a source doc + section anchor from a reason like 'SPEC §3: ...'."""
    doc = "SPEC" if "SPEC" in reason else ("DEMO" if "DEMO" in reason else None)
    if not doc:
        return None
    section = re.search(r"§\s*(\d+)", reason)
    slugs = _section_slugs(f"{doc}.md")
    if section and section.group(1) in slugs:
        return f"{doc}.md#{slugs[section.group(1)]}"
    return f"{doc}.md"


_SLUG_CACHE: dict = {}


def _section_slugs(doc: str) -> dict:
    """Map numbered-section → GitHub heading anchor for a doc (cached)."""
    if doc not in _SLUG_CACHE:
        path, mapping = REPO_ROOT / doc, {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                match = re.match(r"^#{2,3}\s+(\d+)\.\s", line)
                if match:
                    mapping[match.group(1)] = _slug(line.lstrip("#").strip())
        _SLUG_CACHE[doc] = mapping
    return _SLUG_CACHE[doc]


def _slug(text: str) -> str:
    """GitHub-style heading slug."""
    s = re.sub(r"[^a-z0-9 \-]", "", text.lower())
    return re.sub(r"\s+", "-", s).strip("-")


def to_edges(node_id: str, fm: dict) -> list[dict]:
    """Extract typed edges from one node's frontmatter."""
    edges = []
    for field, relation in EDGE_FIELDS.items():
        for target in _as_list(fm.get(field)):
            edges.append({"from": node_id, "to": target, "rel": relation})
    return edges


def _as_list(value) -> list[str]:
    """Coerce a scalar / list / None frontmatter value into a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def parse_table(path: Path) -> list[dict]:
    """Parse the first Markdown pipe-table into a list of {header: cell} dicts."""
    header, rows = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if header is not None:
                break  # table ended
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
        elif set("".join(cells)) <= set("-: "):
            continue  # separator row
        else:
            rows.append(dict(zip(header, cells)))
    return rows


def registry_nodes(path: Path, node_type: str, default_status: str) -> tuple[list, list]:
    """Turn a registry table's rows into lightweight nodes + their edges."""
    nodes, edges = [], []
    rel = path.relative_to(REPO_ROOT).as_posix()
    for row in parse_table(path):
        node_id = row.get("id")
        if not node_id:
            continue
        nodes.append({
            "id": node_id, "title": row.get("title") or node_id,
            "type": row.get("type") or node_type,
            "status": row.get("status") or default_status,
            "path": rel, "tags": [], "owners": [], "updated": "",
            "reason": row.get("reason", ""), "origin": "registry", "body": "",
            "source": _source_link(row.get("source"), rel, row.get("reason", ""), infer=True),
        })
        for field in TABLE_EDGE_FIELDS:
            for target in _split_ids(row.get(field)):
                edges.append({"from": node_id, "to": target, "rel": field})
    return nodes, edges


def _split_ids(cell: str | None) -> list[str]:
    """Split a table cell of comma-separated node ids, dropping backticks/blanks."""
    if not cell:
        return []
    return [t.strip().strip("`") for t in cell.split(",") if t.strip()]


def build() -> dict:
    """Assemble the graph: frontmatter-file nodes (authoritative) + registry rows."""
    nodes, edges, ids, dupes = [], [], set(), []
    for path in find_markdown():
        fm, body = read_doc(path)
        if fm is None:
            continue
        node = to_node(path, fm, body)
        nodes.append(node)
        ids.add(node["id"])
        edges.extend(to_edges(node["id"], fm))
    for rel, node_type, default_status in REGISTRIES:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        rnodes, redges = registry_nodes(path, node_type, default_status)
        for node in rnodes:
            if node["id"] in ids:
                dupes.append(node["id"])  # a detailed file already owns this id
                continue
            nodes.append(node)
            ids.add(node["id"])
        edges.extend(redges)
    dangling = sorted({e["to"] for e in edges if e["to"] not in ids})
    return {
        "generated_by": "scripts/build_docs_index.py",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "dangling_edges": dangling,
        "duplicate_ids": sorted(set(dupes)),
        "nodes": sorted(nodes, key=lambda n: n["id"]),
        "edges": edges,
    }


def _status_rank(status: str) -> int:
    return STATUS_ORDER.index(status) if status in STATUS_ORDER else len(STATUS_ORDER)


def _outgoing(graph: dict) -> dict:
    """Map node id -> list of 'rel target' strings, for inline display."""
    out: dict = {}
    for edge in graph["edges"]:
        out.setdefault(edge["from"], []).append(f"{edge['rel']} {edge['to']}")
    return out


def write_overview(graph: dict) -> None:
    """Render the graph as a readable, grouped Markdown outline."""
    by_type: dict = {}
    for node in graph["nodes"]:
        by_type.setdefault(node["type"], []).append(node)
    out = _outgoing(graph)

    lines = [
        "# Actropolis — design map (text)",
        "",
        f"_Generated from `docs/index.json` by `scripts/build_docs_index.py`. "
        f"{graph['node_count']} nodes, {graph['edge_count']} edges. A textual "
        f"companion to the feature graph — same data, grouped as an outline._",
    ]
    for node_type, heading in TYPE_SECTIONS:
        items = sorted(by_type.get(node_type, []),
                       key=lambda n: (_status_rank(n["status"]), n["id"]))
        if not items:
            continue
        lines += ["", f"## {heading} ({len(items)})"]
        statuses = [s for s in STATUS_ORDER if any(n["status"] == s for n in items)]
        subgroup = len(statuses) > 1
        for status in statuses:
            group = [n for n in items if n["status"] == status]
            if subgroup:
                lines += ["", f"### {status} ({len(group)})", ""]
            else:
                lines += [""]
            for node in group:
                lines.append(_overview_line(node, out, inline_status=not subgroup))
    OVERVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _overview_line(node: dict, out: dict, inline_status: bool) -> str:
    """One bullet: title, id, status (when not subgrouped), reason, edges."""
    parts = [f"- **{node['title']}** (`{node['id']}`)"]
    if inline_status:
        parts.append(f" · _{node['status']}_")
    if node.get("reason"):
        parts.append(f" — {node['reason']}")
    src = node.get("source") or {}
    if src.get("url"):
        parts.append(f"  · [{src['label']}]({src['url']})")
    if out.get(node["id"]):
        parts.append(f"  ↳ {'; '.join(out[node['id']])}")
    return "".join(parts)


def main() -> int:
    """Write index.json + OVERVIEW.md; warn (but don't fail) on dangling edges."""
    graph = build()
    OUTPUT.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    write_overview(graph)
    print(
        f"Wrote {OUTPUT.relative_to(REPO_ROOT)} + {OVERVIEW.relative_to(REPO_ROOT)}: "
        f"{graph['node_count']} nodes, {graph['edge_count']} edges"
    )
    if graph["dangling_edges"]:
        print(f"WARNING: edges point at unknown node ids: {graph['dangling_edges']}")
    if graph["duplicate_ids"]:
        print(f"NOTE: registry rows shadowed by detail files: {graph['duplicate_ids']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
