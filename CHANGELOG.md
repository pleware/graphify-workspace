# Changelog

## Unreleased

- A tree that holds source **and** Markdown is now kind `both`, and gets one
  full extract instead of `--code-only`. Before this, any checkout with a
  recognised source file lost its `README` and `CHANGELOG` from the graph —
  the functions were indexed and the file explaining them was not.
- A failed Markdown pass on a `both` tree falls back to `--code-only`, so
  losing the docs never costs the AST as well.
- `extract` returns `ExtractResult(graph, docs_failed)`. A `both` tree that
  fell back is now recorded as `docs-failed=` in `SOURCES.txt`; a deliberate
  `--skip-docs` is not, because a skip is not a failure.
- Tree classification walks once and prunes `SKIP_DIR_NAMES` during descent
  rather than filtering afterwards, so a vendored `README` no longer counts
  and a populated `node_modules` is no longer walked.
- The closing summary no longer blames a missing API key for every docs gap.
  It names the count, points at `SOURCES.txt`, and mentions the other cause:
  an incomplete extract tripping Graphify's shrink guard, which a re-run
  usually clears.

## 0.1.0

- Plan extract targets from `mani.yaml`: default is this umbrella plus
  every on-disk product; optional `graphify:` lists project keys and
  sibling registries (`workspaces[].path` + that file's keys).
- Optional `graphify.backend` / `graphify.model` are passed as `--backend`
  / `--model` on docs extract so auto-detect cannot pick another key.
  CLI `--backend` / `--model` override the file. The API key is never in
  `mani.yaml`.
- `graphify extract --code-only` per product, docs extract when a key is set,
  then `merge-graphs` into the umbrella `graphify-out/graph.json`.
- CLI `graphify-workspace` / `python -m graphify_workspace`.
