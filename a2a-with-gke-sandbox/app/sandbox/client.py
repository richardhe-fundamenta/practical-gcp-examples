"""Run untrusted, model-generated Python in a GKE Agent Sandbox and return stdout.

The harness never trusts `code`; containment is structural (gVisor + default-deny
networking + no credentials in the sandbox).
"""
from __future__ import annotations

import os
from typing import NamedTuple

from app.sandbox.kube_auth import KUBECONFIG_PATH, install_default_k8s_config

# MUST run before importing k8s_agent_sandbox: the kubernetes client freezes
# KUBE_CONFIG_DEFAULT_LOCATION from $KUBECONFIG at import time, so load_kube_config()
# would otherwise ignore the kubeconfig we write at request time.
os.environ.setdefault("KUBECONFIG", str(KUBECONFIG_PATH))

from k8s_agent_sandbox import SandboxClient  # noqa: E402
from k8s_agent_sandbox.models import SandboxDirectConnectionConfig  # noqa: E402


class SandboxError(Exception):
    """Raised when sandbox creation or execution fails."""


# Per-output-file cap when reading generated files back out of the sandbox.
_MAX_OUTPUT_BYTES = 5 * 1024 * 1024


class SandboxResult(NamedTuple):
    """Result of a sandbox run: stdout plus any files the code generated."""

    stdout: str
    files: list[tuple[str, bytes]]


def _read_new_files(sandbox, exclude: set[str]) -> list[tuple[str, bytes]]:
    """Read files in the working dir that weren't inputs or main.py (i.e. generated output).

    Best-effort: skips directories / unreadable entries and anything over the size cap.
    """
    out: list[tuple[str, bytes]] = []
    try:
        entries = sandbox.files.list(".")
    except Exception:  # noqa: BLE001 - no outputs if listing fails
        return out
    for entry in entries:
        name = entry.name
        if name in exclude:
            continue
        try:
            data = sandbox.files.read(name)  # raises for directories / missing
        except Exception:  # noqa: BLE001
            continue
        if data is not None and len(data) <= _MAX_OUTPUT_BYTES:
            out.append((name, bytes(data)))
    return out


def run_python(
    code: str,
    *,
    api_url: str,
    template: str,
    namespace: str,
    endpoint: str,
    ca_cert_path: str | None = None,
    files: list[tuple[str, bytes]] | None = None,
    _client=None,
) -> SandboxResult:
    """Create a fresh sandbox, run `code`, return stdout + generated files, always terminate.

    `files` is an optional list of (name, content_bytes) written into the sandbox working
    dir before the code runs, so the code can `open("<name>")` them. Any files the code
    writes (that weren't inputs or main.py) are read back and returned in the result.
    """
    if _client is None:
        install_default_k8s_config(endpoint=endpoint, ca_cert_path=ca_cert_path)
    client = _client if _client is not None else SandboxClient(
        connection_config=SandboxDirectConnectionConfig(api_url=api_url)
    )
    try:
        sandbox = client.create_sandbox(template=template, namespace=namespace)
    except Exception as exc:  # noqa: BLE001 - surface as SandboxError
        raise SandboxError(f"sandbox creation failed: {exc}") from exc
    input_names = {name for name, _ in (files or [])}
    outputs: list[tuple[str, bytes]] = []
    try:
        # Baseline the runtime image's own working-dir files (e.g. pyproject.toml) so they
        # aren't mistaken for generated output by the post-run diff.
        try:
            baseline = {e.name for e in sandbox.files.list(".")}
        except Exception:  # noqa: BLE001 - empty baseline if listing fails
            baseline = set()
        # files.write uploads only the basename to the runtime's working dir, and commands
        # run argv-style (no shell). Write any uploaded files first, then main.py, and run
        # it relative to that dir.
        for name, content in files or []:
            sandbox.files.write(name, content)
        sandbox.files.write("main.py", code)
        result = sandbox.commands.run("python3 main.py")
        # On success, read back any files the code generated (before the sandbox is torn down).
        if result.exit_code == 0:
            outputs = _read_new_files(sandbox, exclude=baseline | input_names | {"main.py"})
    except Exception as exc:  # noqa: BLE001
        raise SandboxError(f"sandbox execution failed: {exc}") from exc
    finally:
        try:
            sandbox.terminate()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
    # Never return silent empty output on failure — surface stderr/exit code.
    if result.exit_code != 0:
        raise SandboxError(
            f"sandbox exec failed (exit {result.exit_code}): "
            f"{result.stderr or result.stdout or '(no output)'}"
        )
    return SandboxResult(stdout=result.stdout, files=outputs)
