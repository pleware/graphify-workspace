import subprocess
from pathlib import Path

import pytest

from graphify_workspace.plan import Target
from graphify_workspace.run import code_extract_cmd, docs_extract_cmd, extract


def test_docs_extract_passes_backend_and_model() -> None:
    cmd = docs_extract_cmd(
        "graphify",
        Path("/tmp/docs"),
        backend="deepseek",
        model="deepseek-v4-flash",
    )
    assert cmd == [
        "graphify",
        "extract",
        str(Path("/tmp/docs")),
        "--no-cluster",
        "--backend",
        "deepseek",
        "--model",
        "deepseek-v4-flash",
    ]


def test_docs_extract_omits_llm_flags_when_unset() -> None:
    cmd = docs_extract_cmd("graphify", Path("."), backend=None, model=None)
    assert "--backend" not in cmd
    assert "--model" not in cmd


def test_code_extract_never_asks_for_a_model() -> None:
    cmd = code_extract_cmd("graphify", Path("/tmp/app"))
    assert cmd == [
        "graphify",
        "extract",
        str(Path("/tmp/app")),
        "--code-only",
        "--no-cluster",
    ]


class Recorder:
    """Stands in for the graphify CLI: records argv, returns queued exit codes."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.codes: list[int] = []

    def fail_next(self, *codes: int) -> None:
        self.codes.extend(codes)

    def __call__(self, cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(cmd)
        return subprocess.CompletedProcess(cmd, self.codes.pop(0) if self.codes else 0)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    rec = Recorder()
    monkeypatch.setattr(subprocess, "run", rec)
    return rec


def _target(tmp_path: Path, kind: str) -> Target:
    out = tmp_path / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "graph.json").write_text("{}", encoding="utf-8")
    return Target(tmp_path, kind, "mani:app")


def test_both_runs_one_full_extract(recorder: Recorder, tmp_path: Path) -> None:
    result = extract(
        _target(tmp_path, "both"),
        skip_docs=False,
        graphify="graphify",
        backend="deepseek",
        model="deepseek-v4-flash",
    )
    assert len(recorder.calls) == 1
    assert "--code-only" not in recorder.calls[0]
    assert "--backend" in recorder.calls[0]
    assert result.graph == tmp_path / "graphify-out" / "graph.json"
    assert result.docs_failed is False


def test_both_under_skip_docs_takes_the_code_only_path(recorder: Recorder, tmp_path: Path) -> None:
    result = extract(
        _target(tmp_path, "both"),
        skip_docs=True,
        graphify="graphify",
        backend="deepseek",
    )
    assert len(recorder.calls) == 1
    assert "--code-only" in recorder.calls[0]
    assert result.graph is not None
    # A deliberate skip is not a failure — it must not reach SOURCES.txt.
    assert result.docs_failed is False


def test_a_markdown_failure_still_yields_the_code_graph(recorder: Recorder, tmp_path: Path) -> None:
    recorder.fail_next(1, 0)
    result = extract(
        _target(tmp_path, "both"),
        skip_docs=False,
        graphify="graphify",
        backend="deepseek",
    )
    assert len(recorder.calls) == 2
    assert "--code-only" not in recorder.calls[0]
    assert "--code-only" in recorder.calls[1]
    assert result.graph is not None
    assert result.docs_failed is True


def test_a_docs_tree_that_fails_reports_and_yields_nothing(
    recorder: Recorder, tmp_path: Path
) -> None:
    recorder.fail_next(1)
    result = extract(
        _target(tmp_path, "docs"),
        skip_docs=False,
        graphify="graphify",
        backend="deepseek",
    )
    assert len(recorder.calls) == 1
    assert result.graph is None
    assert result.docs_failed is True


def test_a_code_tree_that_fails_is_fatal(recorder: Recorder, tmp_path: Path) -> None:
    recorder.fail_next(1)
    with pytest.raises(RuntimeError, match="--code-only failed"):
        extract(_target(tmp_path, "code"), skip_docs=False, graphify="graphify")
