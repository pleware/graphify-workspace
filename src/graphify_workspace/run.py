"""Call graphify extract / merge-graphs. Graphify stays on PATH."""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from graphify_workspace.plan import Target


class GraphifyMissingError(RuntimeError):
    pass


def require_graphify() -> str:
    exe = shutil.which("graphify")
    if exe is None:
        raise GraphifyMissingError("graphify is not on PATH")
    return exe


def docs_extract_cmd(
    graphify: str,
    path: Path,
    *,
    backend: str | None,
    model: str | None,
) -> list[str]:
    cmd = [graphify, "extract", str(path), "--no-cluster"]
    if backend:
        cmd.extend(["--backend", backend])
    if model:
        cmd.extend(["--model", model])
    return cmd


def _docs_key_hint(backend: str | None) -> str:
    names = {
        "deepseek": "DEEPSEEK_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "kimi": "KIMI_API_KEY",
        "ollama": "a running ollama",
    }
    if backend and backend in names:
        return names[backend]
    return "the API key for graphify.backend (or GEMINI_API_KEY / OPENAI_API_KEY)"


def extract(
    target: Target,
    *,
    skip_docs: bool,
    graphify: str,
    backend: str | None = None,
    model: str | None = None,
) -> Path | None:
    graph = target.path / "graphify-out" / "graph.json"
    if target.kind == "docs":
        if skip_docs:
            print(f"[graphify-workspace] skip docs {target.path} (--skip-docs)")
            return None
        print(f"[graphify-workspace] extract docs {target.path}")
        completed = subprocess.run(
            docs_extract_cmd(graphify, target.path, backend=backend, model=model),
            check=False,
        )
        if completed.returncode != 0:
            print(
                "[graphify-workspace] docs extract failed "
                f"(need {_docs_key_hint(backend)} for Markdown). Continuing."
            )
            return None
        return graph if graph.is_file() else None

    print(f"[graphify-workspace] extract code {target.path}")
    completed = subprocess.run(
        [graphify, "extract", str(target.path), "--code-only", "--no-cluster"],
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"graphify extract --code-only failed for {target.path} "
            f"(exit {completed.returncode})"
        )
    if not graph.is_file():
        raise RuntimeError(f"no graph.json after extract of {target.path}")
    return graph


def merge_graphs(graphs: list[Path], out: Path, *, graphify: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if len(graphs) == 1:
        out.write_bytes(graphs[0].read_bytes())
        print(f"[graphify-workspace] single graph copied to {out}")
        return
    print(f"[graphify-workspace] merge {len(graphs)} graphs")
    completed = subprocess.run(
        [graphify, "merge-graphs", *[str(g) for g in graphs], "--out", str(out)],
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"graphify merge-graphs failed (exit {completed.returncode})")


def write_sources(
    out_dir: Path,
    out_graph: Path,
    graphs: list[Path],
    failed_docs: list[Path],
) -> None:
    lines = [
        f"merged={datetime.now(UTC).isoformat()}",
        f"out={out_graph}",
        *[f"in={g}" for g in graphs],
        *[f"docs-failed={p}" for p in failed_docs],
    ]
    (out_dir / "SOURCES.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
