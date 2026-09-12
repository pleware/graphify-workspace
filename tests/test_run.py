from pathlib import Path

from graphify_workspace.run import docs_extract_cmd


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
