from pathlib import Path

from graphify_workspace.plan import (
    classify_tree,
    has_code,
    kind_for,
    mani_projects,
    parse_flow_or_block_list,
    parse_graphify_block,
    parse_graphify_spec,
    plan,
)

LOCAL_MANI = """
projects:
  workspace:
    path: .
  lib:
    path: lib
  ghost:
    path: not-here
"""


def test_mani_projects_includes_workspace_dot(tmp_path: Path) -> None:
    (tmp_path / "mani.yaml").write_text(LOCAL_MANI, encoding="utf-8")
    assert mani_projects(tmp_path / "mani.yaml") == {
        "workspace": ".",
        "lib": "lib",
        "ghost": "not-here",
    }


def test_flow_list() -> None:
    assert parse_flow_or_block_list(["[workspace, lib]"]) == ["workspace", "lib"]


def test_default_plan_skips_missing_product(tmp_path: Path) -> None:
    (tmp_path / "mani.yaml").write_text(LOCAL_MANI, encoding="utf-8")
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "main.go").write_text("package lib\n", encoding="utf-8")

    targets, skipped = plan(tmp_path)
    sources = {t.source for t in targets}
    assert "workspace" in sources
    assert "mani:lib" in sources
    assert "mani:workspace" not in sources
    assert any("ghost" in note or "not-here" in note for note in skipped)


def test_graphify_include_and_depends(tmp_path: Path) -> None:
    other = tmp_path / "other-workspace"
    other.mkdir()
    (other / "mani.yaml").write_text(
        """
projects:
  workspace:
    path: .
  product:
    path: app
""",
        encoding="utf-8",
    )
    (other / "app").mkdir()
    (other / "app" / "main.go").write_text("package app\n", encoding="utf-8")

    (tmp_path / "mani.yaml").write_text(
        LOCAL_MANI
        + """
graphify:
  products:
    - workspace
    - lib
  workspaces:
    - path: other-workspace
      products:
        - workspace
        - product
""",
        encoding="utf-8",
    )
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "main.go").write_text("package lib\n", encoding="utf-8")

    spec = parse_graphify_spec(tmp_path / "mani.yaml")
    assert spec.explicit is True
    assert spec.backend is None
    assert spec.model is None
    local_keys, depends = parse_graphify_block(tmp_path / "mani.yaml")
    assert local_keys == ["workspace", "lib"]
    assert depends == [("other-workspace", ["workspace", "product"])]

    targets, skipped = plan(tmp_path)
    by_source = {t.source: t for t in targets}
    assert by_source["mani:workspace"].kind == "docs"
    assert by_source["mani:lib"].kind == "code"
    assert by_source["dep:other-workspace:workspace"].kind == "docs"
    assert by_source["dep:other-workspace:product"].kind == "code"
    assert "ghost" not in "".join(skipped)


def test_graphify_backend_and_model(tmp_path: Path) -> None:
    (tmp_path / "mani.yaml").write_text(
        LOCAL_MANI
        + """
graphify:
  backend: deepseek
  model: deepseek-v4-flash
  products:
    - workspace
""",
        encoding="utf-8",
    )
    spec = parse_graphify_spec(tmp_path / "mani.yaml")
    assert spec.explicit is True
    assert spec.backend == "deepseek"
    assert spec.model == "deepseek-v4-flash"
    assert spec.local_keys == ["workspace"]


def test_has_code_ignores_node_modules(tmp_path: Path) -> None:
    nested = tmp_path / "node_modules" / "pkg"
    nested.mkdir(parents=True)
    (nested / "index.js").write_text("module.exports = {}\n", encoding="utf-8")
    assert has_code(tmp_path) is False
    (tmp_path / "app.ts").write_text("export {}\n", encoding="utf-8")
    assert has_code(tmp_path) is True


def test_a_vendored_readme_does_not_make_a_tree_documented(tmp_path: Path) -> None:
    nested = tmp_path / "node_modules" / "pkg"
    nested.mkdir(parents=True)
    (nested / "README.md").write_text("# vendored\n", encoding="utf-8")
    (tmp_path / "app.ts").write_text("export {}\n", encoding="utf-8")
    assert classify_tree(tmp_path) == (True, False)
    assert kind_for(tmp_path, "app") == "code"


def test_source_beside_a_readme_is_both(tmp_path: Path) -> None:
    (tmp_path / "app.ts").write_text("export {}\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# what this is for\n", encoding="utf-8")
    assert classify_tree(tmp_path) == (True, True)
    assert kind_for(tmp_path, "app") == "both"


def test_markdown_with_no_source_stays_docs(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# recipes\n", encoding="utf-8")
    (tmp_path / "build.sh").write_text("echo hi\n", encoding="utf-8")
    assert classify_tree(tmp_path) == (False, True)
    assert kind_for(tmp_path, "contrib") == "docs"


def test_the_umbrella_root_is_docs_whatever_it_holds(tmp_path: Path) -> None:
    (tmp_path / "app.ts").write_text("export {}\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# umbrella\n", encoding="utf-8")
    assert kind_for(tmp_path, ".") == "docs"


def test_plan_marks_a_documented_product_both(tmp_path: Path) -> None:
    (tmp_path / "mani.yaml").write_text(LOCAL_MANI, encoding="utf-8")
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "main.go").write_text("package lib\n", encoding="utf-8")
    (lib / "README.md").write_text("# lib\n", encoding="utf-8")

    targets, _ = plan(tmp_path)
    by_source = {t.source: t for t in targets}
    assert by_source["mani:lib"].kind == "both"
