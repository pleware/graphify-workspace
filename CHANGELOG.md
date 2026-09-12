# Changelog

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
