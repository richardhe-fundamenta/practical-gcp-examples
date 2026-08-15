# Dataplex Auto DQ with Yaml

[![Subscribe on YouTube](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.socialcounts.org%2Fyoutube-live-subscriber-count%2FUC3XbEkSbPOzHvqNBrjNIu7A&query=%24.counters.api.subscriberCount&label=Subscribe&suffix=%20subscribers&color=FF0000&logo=youtube&logoColor=white&style=for-the-badge)](https://www.youtube.com/@practicalgcp2780?sub_confirmation=1)
[![Videos](https://img.shields.io/badge/90%2B_videos-Watch_all-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://www.youtube.com/playlist?list=UU3XbEkSbPOzHvqNBrjNIu7A)

_Code from the [PracticalGCP](https://www.youtube.com/@practicalgcp2780) YouTube channel._


Use the YAML standard to manage data quality scan with Dataplex. 

## Generate fake data
See 
- [fake_data_gen.py](tools/data_gen/fake_data_gen_issues.py), this script generates 5000 rows of fake customer data with various issues.
- [fake_data_gen_no_issues.py](tools/data_gen/fake_data_gen_no_issues.py), this script generates 5000 rows of fake customer data with various issues.

The data structure generated here specifically takes STRUCT into account. 

## YAML rules
See the rule YAML file [customer_with_issues.yaml](rules/dataplex_dq_demo/customer_with_issues.yaml) for an example what a YAML rule file looks like.

## Create scan via CLI

```
export PROJECT_ID=rocketech-de-pgcp-sandbox
export REGION=europe-west2
export DQ_DATASET=dataplex_dq_demo
export DQ_TABLE=customer_with_issues

gcloud dataplex datascans create data-quality ${DQ_DATASET//_/-}--${DQ_TABLE//_/-} \
    --location=${REGION} \
    --data-quality-spec-file=rules/dataplex_dq_demo/${DQ_TABLE}.yaml \
    --data-source-resource="//bigquery.googleapis.com/projects/${PROJECT_ID}/datasets/${DQ_DATASET}/tables/${DQ_TABLE}"
```

## Terraform
> Inspired by [Manage data quality rules as code with Terraform](https://cloud.google.com/dataplex/docs/manage-data-quality-rules-as-code)

- [modules/yaml_to_dataplex_dq](modules/yaml_to_dataplex_dq) is a local module created to allow multiple YAML files to be used to create Auto DQ Scans.
- [main.tf](main.tf) is an example of how the module can be used with multiple YAML files.

### To run 
```
terraform init
terraform plan
terraform apply
```

## Remote Models
To use the Vertex AI remote models in BigQuery, you'll have to do the following

### Create the remote connection
```
export PROJECT_ID=rocketech-de-pgcp-sandbox
export REGION=europe-west2

bq mk --connection \
    --connection_type=CLOUD_RESOURCE \
    --project_id="${PROJECT_ID}" \
    --location="${REGION}" \
    'vertex_ai_remote_models'
```

## Data Quality Spec
> hard to find, bookmark it 

This is the spec you'll need to understand exactly what kind of rules & configuration options can be used for the scan. 
See details [here](https://cloud.google.com/dataplex/docs/reference/rest/v1/DataQualitySpec)

## Additional to-read

- Dataplex Auto DQ: https://cloud.google.com/dataplex/docs/use-auto-data-quality#gcloud
- Dataplex Auto DQ Terraform: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dataplex_datascan#example-usage---dataplex-datascan-basic-quality
- AI.GENERATE(): https://cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-ai-generate
