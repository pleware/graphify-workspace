# Agents

This repository is the **graphify-workspace** product
(`https://github.com/pleware/graphify-workspace`).

Public and company-agnostic. A consumer or host name inside this kit is
contamination, not configuration. Which trees to fold in belongs in the
consuming umbrella's `mani.yaml` (`graphify:`).

Drafts and backlog do not live here.

Do not vendor Graphify. Call the `graphify` CLI that is already on PATH.

After a behaviour change:

```sh
uv run pytest
uv run ruff check src tests
```
