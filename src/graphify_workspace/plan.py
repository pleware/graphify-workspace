"""Collect extract targets from ``mani.yaml``.

Membership is an extra key the mani CLI ignores::

    graphify:
      backend: deepseek
      model: deepseek-v4-flash
      products: [workspace, input_vision]
      workspaces:
        - path: ../other-workspace
          products: [workspace, product]

``products`` are project keys in that file. ``workspace`` (path ``.``) is
docs. Omit the whole ``graphify:`` block to mean this umbrella's docs plus
every on-disk product row.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

CODE_SUFFIXES = {".go", ".py", ".ts", ".tsx", ".js", ".jsx", ".rs"}
DOC_SUFFIXES = {".md"}
SKIP_DIR_NAMES = frozenset(
    {"node_modules", "graphify-out", ".git", "__pycache__", ".venv", "dist", "build"}
)

_FLOW_LIST = re.compile(r"^\[(.*)\]$")
_KEY_LINE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
_PATH_LINE = re.compile(r"^    path:\s+(\S+)\s*$")


@dataclass(frozen=True)
class Target:
    path: Path
    kind: str
    source: str


@dataclass(frozen=True)
class GraphifyRef:
    """One registry to fold in: a mani.yaml and the project keys to take."""

    mani: Path
    keys: tuple[str, ...] | None  # None = all keys in that file


@dataclass(frozen=True)
class GraphifySpec:
    """Membership plus the LLM used for Markdown. Never holds an API key."""

    local_keys: list[str] | None
    depends: list[tuple[str, list[str] | None]]
    backend: str | None
    model: str | None
    explicit: bool


def find_umbrella_root(start: Path) -> Path:
    directory = start.resolve()
    while True:
        if (directory / "mani.yaml").is_file():
            return directory
        parent = directory.parent
        if parent == directory:
            raise FileNotFoundError(f"No mani.yaml above {start}")
        directory = parent


def mani_projects(mani: Path) -> dict[str, str]:
    """Project key → relative path, including ``workspace: path: .``."""
    mapping: dict[str, str] = {}
    current: str | None = None
    in_projects = False
    for raw in mani.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if line == "projects:":
            in_projects = True
            current = None
            continue
        if in_projects and line and not line.startswith(" ") and line.endswith(":"):
            break
        if not in_projects:
            continue
        key_match = _KEY_LINE.match(line)
        if key_match:
            current = key_match.group(1)
            continue
        path_match = _PATH_LINE.match(line)
        if path_match and current is not None:
            mapping[current] = path_match.group(1).strip("\"'")
            current = None
    return mapping


def parse_flow_or_block_list(values: list[str]) -> list[str]:
    out: list[str] = []
    for item in values:
        stripped = item.strip().strip("\"'")
        flow = _FLOW_LIST.match(stripped)
        if flow:
            inner = flow.group(1).strip()
            if inner:
                out.extend(part.strip().strip("\"'") for part in inner.split(","))
            continue
        out.append(stripped)
    return [x for x in out if x]


def parse_graphify_spec(mani: Path) -> GraphifySpec:
    """Read ``graphify:`` from a mani.yaml. Keys and backend/model only — no secrets."""
    saw_graphify = False
    saw_local_products = False
    local_acc: list[str] = []
    depends: list[tuple[str, list[str] | None]] = []
    backend: str | None = None
    model: str | None = None
    in_graphify = False
    in_local_products = False
    in_workspaces = False
    current_ws: str | None = None
    current_keys: list[str] | None = None
    in_ws_products = False

    def flush_ws() -> None:
        nonlocal current_ws, current_keys, in_ws_products
        if current_ws is not None:
            depends.append((current_ws, None if current_keys is None else list(current_keys)))
        current_ws = None
        current_keys = None
        in_ws_products = False

    for raw in mani.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not saw_graphify and line == "graphify:":
            saw_graphify = True
            in_graphify = True
            continue
        if not in_graphify:
            continue
        if line and not line.startswith(" ") and line.endswith(":"):
            flush_ws()
            break
        stripped = line.strip()
        if not in_workspaces and stripped.startswith("backend:"):
            backend = stripped.split(":", 1)[1].strip().strip("\"'") or None
            continue
        if not in_workspaces and stripped.startswith("model:"):
            model = stripped.split(":", 1)[1].strip().strip("\"'") or None
            continue
        if stripped == "products:" or stripped.startswith("products:"):
            if in_workspaces and current_ws is not None:
                in_ws_products = True
                current_keys = []
                rest = stripped.split(":", 1)[1].strip()
                if rest:
                    current_keys.extend(parse_flow_or_block_list([rest]))
                    in_ws_products = False
            elif not in_workspaces:
                saw_local_products = True
                in_local_products = True
                in_workspaces = False
                rest = stripped.split(":", 1)[1].strip()
                local_acc = []
                if rest:
                    local_acc.extend(parse_flow_or_block_list([rest]))
                    in_local_products = False
            continue
        if stripped == "workspaces:":
            if in_local_products:
                in_local_products = False
            in_workspaces = True
            continue
        if in_workspaces and stripped.startswith("- path:"):
            flush_ws()
            current_ws = stripped.split(":", 1)[1].strip().strip("\"'")
            current_keys = None
            in_ws_products = False
            continue
        if in_ws_products and stripped.startswith("- "):
            if current_keys is not None:
                current_keys.append(stripped[2:].strip().strip("\"'"))
            continue
        if in_local_products and stripped.startswith("- "):
            local_acc.append(stripped[2:].strip().strip("\"'"))
            continue

    flush_ws()
    if not saw_graphify:
        return GraphifySpec(None, [], None, None, explicit=False)
    local = local_acc if saw_local_products else None
    return GraphifySpec(local, depends, backend, model, explicit=True)


def parse_graphify_block(
    mani: Path,
) -> tuple[list[str] | None, list[tuple[str, list[str] | None]]]:
    spec = parse_graphify_spec(mani)
    if not spec.explicit:
        return None, []
    return spec.local_keys, spec.depends


def classify_tree(directory: Path) -> tuple[bool, bool]:
    """``(has_code, has_markdown)``, from one walk that prunes ``SKIP_DIR_NAMES``.

    Pruning is what keeps this cheap on a tree with a populated
    ``node_modules``: the skipped names are dropped from the descent, not
    filtered out of the results afterwards.
    """
    code = False
    markdown = False
    for _current, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            suffix = Path(name).suffix.lower()
            if suffix in CODE_SUFFIXES:
                code = True
            elif suffix in DOC_SUFFIXES:
                markdown = True
            if code and markdown:
                return True, True
    return code, markdown


def has_code(directory: Path) -> bool:
    return classify_tree(directory)[0]


def kind_for(abs_path: Path, rel: str) -> str:
    """``docs``, ``code``, or ``both``.

    ``both`` exists because a product checkout usually carries a README beside
    its source, and a code-only extract drops it — the graph then holds the
    functions but not the file that says what they are for.
    """
    if rel == ".":
        return "docs"
    code, markdown = classify_tree(abs_path)
    if code and markdown:
        return "both"
    return "code" if code else "docs"


def targets_from_registry(
    mani: Path,
    keys: list[str] | None,
    *,
    source_prefix: str,
) -> tuple[list[Target], list[str]]:
    root = mani.parent.resolve()
    projects = mani_projects(mani)
    if not projects:
        return [], [f"no projects in {mani}"]
    chosen = list(projects.keys()) if keys is None else keys
    targets: list[Target] = []
    skipped: list[str] = []
    for key in chosen:
        if key not in projects:
            skipped.append(f"unknown project {key} in {mani.name}")
            continue
        rel = projects[key]
        abs_path = (root / rel).resolve()
        if not abs_path.is_dir():
            skipped.append(f"missing {source_prefix}:{key} ({rel})")
            continue
        targets.append(Target(abs_path, kind_for(abs_path, rel), f"{source_prefix}:{key}"))
    return targets, skipped


def plan(root: Path) -> tuple[list[Target], list[str]]:
    root = root.resolve()
    mani = root / "mani.yaml"
    if not mani.is_file():
        raise FileNotFoundError(f"No mani.yaml in {root}")

    spec = parse_graphify_spec(mani)
    targets: list[Target] = []
    skipped: list[str] = []

    if not spec.explicit:
        # No graphify: block — this umbrella's docs + every on-disk product.
        targets.append(Target(root, "docs", "workspace"))
        more, notes = targets_from_registry(mani, None, source_prefix="mani")
        targets.extend(t for t in more if t.source != "mani:workspace")
        skipped.extend(notes)
        return targets, skipped

    more, notes = targets_from_registry(mani, spec.local_keys, source_prefix="mani")
    targets.extend(more)
    skipped.extend(notes)

    for rel, keys in spec.depends:
        other_root = (root / rel).resolve()
        other_mani = other_root / "mani.yaml"
        if not other_mani.is_file():
            skipped.append(f"missing workspace mani {rel}/mani.yaml")
            continue
        more, notes = targets_from_registry(other_mani, keys, source_prefix=f"dep:{rel}")
        targets.extend(more)
        skipped.extend(notes)

    return targets, skipped
