import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    project: str
    bq_data_region: str
    max_bytes_billed: int
    dataset_allowlist: frozenset[str]
    sandbox_region: str = "us-central1"  # Agent Runtime code-exec is us-central1-only
    # Durable host Agent Engine under which per-session sandboxes are lazily created.
    agent_engine_name: str = ""


def get_settings() -> Settings:
    allowlist = os.getenv("BQ_DATASET_ALLOWLIST", "")
    return Settings(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        bq_data_region=os.getenv("BQ_DATA_REGION", "US"),
        max_bytes_billed=int(os.getenv("BQ_MAX_BYTES_BILLED", str(1 << 30))),  # 1 GiB
        dataset_allowlist=frozenset(d.strip() for d in allowlist.split(",") if d.strip()),
        agent_engine_name=os.getenv("AGENT_ENGINE_NAME", ""),
    )
