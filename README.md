# graphify-workspace

Merge [Graphify](https://github.com/Graphify-Labs/graphify) graphs for a
`mani.yaml` umbrella.

Docs live in the umbrella git. Product code lives in sibling remotes. A
whitelist `.gitignore` hides those checkouts, so one `graphify` run at the
umbrella root indexes Markdown and misses the code.

This kit extracts **the trees `mani.yaml` names**, then `merge-graphs` into
that umbrella's `graphify-out/graph.json`.

```sh
uv tool install git+https://github.com/pleware/graphify-workspace.git
graphify-workspace --root .
graphify-workspace --root . --dry-run
graphify-workspace --root . --skip-docs
```

`--root` may be the umbrella or a path under it; the CLI walks up to
`mani.yaml`. `--backend` / `--model` override `graphify.backend` /
`graphify.model` for one run.

## Membership is `mani.yaml`

Extra key — the [mani](https://github.com/alajmo/mani) CLI ignores it.
`products` are project keys in **this** file. `workspaces` cite another
registry and keys in **that** file. Do not flatten a sibling umbrella into
`projects:`.

```yaml
graphify:
  backend: deepseek
  model: deepseek-v4-flash
  products:
    - workspace
    - some_product
  workspaces:
    - path: ../other-workspace
      products:
        - workspace
        - product
```

`backend` / `model` are the portable LLM pin. The kit passes `--backend` and
`--model` on docs extract so a second key on the machine (Gemini, OpenAI)
does not steal the run. The API key is **not** in this file — each laptop
sets `DEEPSEEK_API_KEY` in the user environment or in a gitignored
`mise.local.toml` (copy the umbrella's `mise.local.toml.example`).

Omit the whole `graphify:` block to mean this umbrella's docs plus every
on-disk product row. Omit `backend` / `model` to let Graphify auto-detect
from whichever key is set (Gemini wins if both exist).

Markdown extract needs the key for that backend. Without a key,
`--skip-docs` still merges product AST graphs.

## Who plants this

**ignite** owns Graphify on the machine (`graphifyy` + postpass in the same
`uv` env). Once this kit is tagged, ignite adds it as a second
`TOOL_GRAPHIFYY_WITH` so `graphify-workspace` lands next to `graphify`.

**agentize** only serves the merge (`graphify-mcp graphify-out/graph.json`
with `--directory .` rewritten from the consuming `agentize.yaml`). It does
not choose trees.

`graphify global` is a machine-wide mix. Do not use it as an umbrella default.

## License

Apache License 2.0. Graphify itself is Apache-2.0; this companion matches it.
