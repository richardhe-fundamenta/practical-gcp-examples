"""Bootstrap script: create an Agent Runtime Code Execution sandbox (preview).

Creates a Python code-execution sandbox under a Vertex AI Agent Engine
(reasoningEngine) resource in us-central1.

IMPORTANT NOTES:
  - Location: us-central1 ONLY (the sandbox API is regional, preview).
  - No network access from inside the sandbox.
  - This is a billable preview resource — delete it when no longer needed.
  - The sandbox lives under a reasoningEngines parent resource; you must supply
    an existing reasoningEngine resource name (or create a stub engine first).

The harness no longer pins a single sandbox: it lazily creates a per-session sandbox
under a durable host Agent Engine and recreates it on expiry. So the env var the app
needs is the *engine* it creates sandboxes under:
  AGENT_ENGINE_NAME=<the --engine-name you pass below>

This script just creates one sandbox under that engine as a smoke test (it will expire);
use --list to confirm sandboxes can be created/listed under the engine.

Run with:
  uv run python bootstrap/create_sandbox.py --engine-name <reasoningEngine resource name>

  e.g.:
  uv run python bootstrap/create_sandbox.py \\
      --engine-name projects/my-project/locations/us-central1/reasoningEngines/123456789

Optional flags:
  --list     List existing sandboxes under the given engine instead of creating.
  --project  GCP project (default: ADC project).
  --location Location (default: us-central1).
"""

import argparse
import os

import google.auth
import vertexai
from vertexai._genai.types.common import (
    Language,
    SandboxEnvironmentSpec,
    SandboxEnvironmentSpecCodeExecutionEnvironment,
)

LOCATION = "us-central1"


def get_project() -> str:
    """Return project from env override or ADC."""
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project:
        return project
    _, adc_project = google.auth.default()
    if not adc_project:
        raise RuntimeError(
            "Could not determine GCP project. "
            "Set GOOGLE_CLOUD_PROJECT or configure ADC."
        )
    return adc_project


def create_sandbox(
    client: vertexai.Client,
    engine_name: str,
    display_name: str = "analyst-harness-sandbox",
) -> str:
    """Create a Python code-execution sandbox and return its resource name.

    The `create()` signature (from vertexai._genai.sandboxes.Sandboxes.create):

        create(
            *,
            name: str,                      # required: parent reasoningEngine resource name
            poll_interval_seconds: float = 0.1,
            spec: Optional[SandboxEnvironmentSpecOrDict] = None,
            config: Optional[CreateAgentEngineSandboxConfigOrDict] = None,
        ) -> AgentEngineSandboxOperation

    The `spec` field uses:
        SandboxEnvironmentSpec(
            code_execution_environment=SandboxEnvironmentSpecCodeExecutionEnvironment(
                code_language=Language.LANGUAGE_PYTHON,   # "LANGUAGE_PYTHON"
                machine_config=MachineConfig.MACHINE_CONFIG_UNSPECIFIED,  # default
            )
        )

    The `config` field (CreateAgentEngineSandboxConfig) supports:
        display_name, description, ttl (str, e.g. "3600s"), wait_for_completion (bool).

    Returns:
        AgentEngineSandboxOperation; when wait_for_completion=True (default),
        operation.response is a SandboxEnvironment with .name set to the full
        resource path:
            projects/{project}/locations/us-central1/reasoningEngines/{id}/sandboxEnvironments/{sid}
    """
    spec = SandboxEnvironmentSpec(
        code_execution_environment=SandboxEnvironmentSpecCodeExecutionEnvironment(
            # Python sandbox — the only language we need for the analyst agent.
            code_language=Language.LANGUAGE_PYTHON,
            # Use default machine config: ~2000 milliGCU, 1.5 GiB RAM.
            # Set machine_config=MachineConfig.MACHINE_CONFIG_VCPU4_RAM4GIB
            # for 4 vCPU / 4 GiB if heavier computation is needed.
            machine_config=None,
        )
    )

    # NOTE: CreateAgentEngineSandboxConfig exposes a `description` field, but the
    # underlying SandboxEnvironment resource has no such field and the API rejects
    # it (400 "Unknown name description at sandbox_environment"). So omit it.
    config = {
        "display_name": display_name,
        # wait_for_completion defaults to True — block until sandbox is RUNNING.
        "wait_for_completion": True,
        # ttl: sandbox auto-deletes after this duration (e.g. "86400s" = 24h).
        # Omit for the API default TTL.
        # "ttl": "86400s",
    }

    print(f"Creating sandbox under: {engine_name}")
    print("This may take 1-3 minutes while the sandbox starts up...")

    operation = client.agent_engines.sandboxes.create(
        name=engine_name,
        spec=spec,
        config=config,
    )

    # When wait_for_completion=True, operation.response is a SandboxEnvironment.
    sandbox = operation.response
    if sandbox is None:
        raise RuntimeError(
            "Sandbox creation completed but response is None. "
            "Check the GCP console for the sandbox state."
        )

    resource_name = sandbox.name
    print(f"\nSandbox created successfully (smoke test — this sandbox will expire).")
    print(f"  Display name : {sandbox.display_name}")
    print(f"  Resource name: {resource_name}")
    print(f"\nThe app creates sandboxes on demand; set the HOST ENGINE in your .env:")
    print(f"  AGENT_ENGINE_NAME={engine_name}")
    return resource_name


def list_sandboxes(client: vertexai.Client, engine_name: str) -> None:
    """List existing sandboxes under an agent engine."""
    print(f"Listing sandboxes under: {engine_name}")
    sandboxes = list(client.agent_engines.sandboxes.list(name=engine_name))
    if not sandboxes:
        print("  No sandboxes found.")
        return
    for sb in sandboxes:
        print(f"  {sb.name}  (display_name={sb.display_name})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--engine-name",
        required=False,
        help=(
            "Full resource name of the parent Vertex AI Agent Engine, e.g. "
            "projects/my-project/locations/us-central1/reasoningEngines/123456789"
        ),
    )
    parser.add_argument(
        "--project",
        default=None,
        help="GCP project ID (default: ADC project).",
    )
    parser.add_argument(
        "--location",
        default=LOCATION,
        help=f"GCP location (default: {LOCATION}).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_only",
        help="List existing sandboxes instead of creating a new one.",
    )
    args = parser.parse_args()

    project = args.project or get_project()
    location = args.location

    print(f"Project : {project}")
    print(f"Location: {location}")

    # Build the vertexai client — sandbox API requires vertexai=True (Vertex AI).
    client = vertexai.Client(project=project, location=location)

    if args.list_only:
        if not args.engine_name:
            parser.error("--engine-name is required with --list")
        list_sandboxes(client, args.engine_name)
    else:
        if not args.engine_name:
            parser.error(
                "--engine-name is required. Provide the resource name of an "
                "existing Vertex AI Agent Engine (reasoningEngine)."
            )
        create_sandbox(client, args.engine_name)


if __name__ == "__main__":
    main()
