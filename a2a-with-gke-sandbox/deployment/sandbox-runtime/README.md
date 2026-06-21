# Sandbox runtime image

The container the **GKE Agent Sandbox runs untrusted code in**. We build our own (rather than use
the stock runtime) for two reasons: private cluster nodes can't pull from `registry.k8s.io`, and we
want a fat **analytics** stack (pandas, matplotlib, …) preinstalled so `run_code` is useful.

```
Dockerfile      python:3.12-slim + libgomp1, `uv pip install` the deps, run as non-root (UID 1000)
pyproject.toml  the dependency set available inside the sandbox  ← edit this to add packages
main.py         the FastAPI server the sandbox exposes (/execute, /upload, /download, /list)
```

The image is pushed to Artifact Registry and referenced by the `SandboxTemplate`
(`SANDBOX_IMAGE`); the `SandboxTemplate` runs it with `automountServiceAccountToken: false` and no
network.

## Change the packages / rebuild

1. Edit `pyproject.toml` (add/remove dependencies).
2. Rebuild + push via the bootstrap script (bump the tag so the cluster pulls the new image):

   ```bash
   SANDBOX_RUNTIME_TAG=v2 bash deployment/bootstrap/bootstrap.sh
   ```

   (See [`../bootstrap/`](../bootstrap/) — step 4 builds this image.)

## Runtime contract (how `run_code` uses it)

`app/sandbox/client.py` writes uploaded files + a `main.py` into the working dir, runs
`python3 main.py` (argv-style — **the runtime is shell-less**, no pipes/`&&`), then reads back any
new files (charts/reports) by diffing the working dir against a pre-run baseline. So: write a file,
don't print bytes; expect no network access.
