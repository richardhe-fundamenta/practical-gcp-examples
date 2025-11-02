# Dlt Examples

Examples to run and deploy Dlt jobs for Slack & Github. 

## Get started
In fact, majority of this repository is auto generated. Let's break it down

### Initialise the source code

Let's use slack as an example here (Github or any other sources would be very similar)

```
uvx dlt init slack bigquery
```
This creates the `slack` folder with `verified code`, meaning, you should not modify the content under this folder. 

The `.dlt/.sources` file is automatically generated to track these verified code, and it these are changed the `is_dirty: false` will be updated. 

`slack_pipeline.py` is also generated and containing some basic examples on how to invoke the slack source. This file is designed to be modified to match what you need to ingest. 

`secrets.toml` is an important credentials file, it's ignored by version control but it is not good practice to use this for production. For deploying to production such as Cloud Run, see [Setting up enviornment variables in Cloud Run](https://dlthub.com/docs/walkthroughs/deploy-a-pipeline/deploy-with-google-cloud-run#3-setting-up-environment-variables-in-cloud-run)

### Run locally

Use `uv run slack_pipeline.py` to execute the pipeline. This will automatically load data from the source into the destination. 

Under `~/.dlt/pipelines` it will generate a folder matching the name of the pipeline. This contains important information about the pipeline such as a state file `state.json` for each pipeline. This isn't the source of truth, but a temporary file generated and will automatically get syned from the destination (i.e. bigquery). All states will always be tracked in the destination (i.e. bigquery) not in the local file system. 

This state tracking mechanism allows Dlt to perform incremental data loading and only loads what's necessary to the target system.
