# Tests

| Path | What | Notes |
|---|---|---|
| `sandbox/` | Unit tests for the sandbox client, kube-auth, `run_code`, the skill toolset, A2UI support, and part-metadata stripping. | Fast; the sandbox SDK / GKE auth / A2UI are **mocked** — no cluster needed. |
| `unit/`, `integration/` | Scaffolded agent/server tests. | `integration/` exercises the agent/server wiring. |
| `eval/datasets/` | Eval scenarios for `agents-cli eval`. | See that folder's README. |

## Run

```bash
uv run pytest tests/sandbox          # the main, always-runnable suite (no cloud access)
uv run pytest tests/unit tests/integration
```

The sandbox **execution path can't be tested locally** (the in-cluster router isn't reachable from
a laptop), which is why those tests mock the SDK; real end-to-end verification is against the
deployed Cloud Run service — see the repo-root [`README.md`](../README.md).
