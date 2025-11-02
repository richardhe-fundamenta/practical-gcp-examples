import dlt

from github import github_reactions, github_repo_events, github_stargazers

def load_agent_starter_pack_issues() -> None:
    """Loads all agent starter pack issues for bigquery"""
    pipeline = dlt.pipeline(
        "github_agent_starter_pack",
        destination='bigquery',
        dataset_name="dlt_examples"
    )
    owner = "GoogleCloudPlatform"
    repo = "agent-starter-pack"

    data = github_reactions(owner, repo)
    print(pipeline.run(data))

    data = github_repo_events(owner, repo)
    print(pipeline.run(data))

    data = github_stargazers(owner, repo)
    print(pipeline.run(data))


if __name__ == "__main__":
    load_agent_starter_pack_issues()
