"""CLI: plan an umbrella, extract each tree, merge into graphify-out/graph.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from graphify_workspace.plan import find_umbrella_root, parse_graphify_spec, plan
from graphify_workspace.run import (
    GraphifyMissingError,
    extract,
    merge_graphs,
    require_graphify,
    write_sources,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="graphify-workspace",
        description=(
            "Extract each mani.yaml checkout, then merge. "
            "Do not scan an umbrella root — the whitelist .gitignore hides products."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="umbrella root, or a path under one (default: cwd; walks up to mani.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print targets only",
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="skip Markdown extract (no API key needed)",
    )
    parser.add_argument(
        "--backend",
        default=None,
        help="LLM for Markdown (overrides mani.yaml graphify.backend)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="model for Markdown (overrides mani.yaml graphify.model)",
    )
    args = parser.parse_args(argv)

    start = (args.root or Path.cwd()).resolve()
    try:
        root = start if (start / "mani.yaml").is_file() else find_umbrella_root(start)
    except FileNotFoundError as exc:
        print(f"[graphify-workspace] {exc}", file=sys.stderr)
        return 2

    spec = parse_graphify_spec(root / "mani.yaml")
    backend = args.backend or spec.backend
    model = args.model or spec.model
    targets, skipped = plan(root)
    print(f"[graphify-workspace] root {root}")
    if backend or model:
        print(f"[graphify-workspace] llm {backend or 'auto'} / {model or 'backend-default'}")
    for note in skipped:
        print(f"[graphify-workspace] skip {note}")
    for target in targets:
        print(f"  {target.kind:<6} {target.path}  ({target.source})")

    if args.dry_run:
        print("[graphify-workspace] dry run — no extract, no merge")
        return 0

    try:
        graphify = require_graphify()
    except GraphifyMissingError as exc:
        print(f"[graphify-workspace] {exc}", file=sys.stderr)
        return 2

    graphs: list[Path] = []
    failed_docs: list[Path] = []
    for target in targets:
        result = extract(
            target,
            skip_docs=args.skip_docs,
            graphify=graphify,
            backend=backend,
            model=model,
        )
        if result.graph is not None:
            graphs.append(result.graph)
        if result.docs_failed:
            failed_docs.append(target.path)

    if not graphs:
        print("[graphify-workspace] no graph.json produced — nothing to merge", file=sys.stderr)
        return 1

    out_dir = root / "graphify-out"
    out_graph = out_dir / "graph.json"
    merge_graphs(graphs, out_graph, graphify=graphify)
    write_sources(out_dir, out_graph, graphs, failed_docs)
    print(f"[graphify-workspace] wrote {out_graph}")
    if failed_docs:
        hint = "DEEPSEEK_API_KEY" if backend == "deepseek" else "the configured API key"
        print(
            f"[graphify-workspace] Markdown missing for {len(failed_docs)} tree(s) — "
            "the merge holds their code only. Listed as docs-failed= in "
            "graphify-out/SOURCES.txt.",
            file=sys.stderr,
        )
        print(
            f"[graphify-workspace] causes: no {hint}; or an incomplete extract that "
            "tripped graphify's shrink guard, which a re-run usually clears.",
            file=sys.stderr,
        )
    return 0
