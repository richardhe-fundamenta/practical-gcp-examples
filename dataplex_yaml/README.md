# Dataplex Auto DQ with Yaml

Use the YAML standard to manage data quality scan with Dataplex. 

## Generate fake data
See [fake_data_gen.py](tools/data_gen/fake_data_gen_issues.py), this script generates 5000 rows of fake customer data with various issues.  
The data structure generated here specifically takes STRUCT into account. 

## YAML rules
See the rule YAML file [validate__customer_with_issues.yaml](rules/dataplex_dq_demo/customer_with_issues.yaml) for an example what a YAML rule file looks like.

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

## Data Quality Spec
> hard to find, bookmark it 

This is the spec you'll need to understand exactly what kind of rules & configuration options can be used for the scan. 
See details [here](https://cloud.google.com/dataplex/docs/reference/rest/v1/DataQualitySpec)

## Terraform
> Original [Terraform implementation](https://github.com/GoogleCloudPlatform/terraform-google-dataplex-auto-data-quality)

- [modules/yaml_to_dataplex_dq](modules/yaml_to_dataplex_dq) is a local module created to allow multiple YAML files to be used to create Auto DQ Scans.
- [main.tf](main.tf) is an example of how the module can be used with multiple YAML files.

## Remote Models
To use the Vertex AI remote models in BigQuery, you'll have to do the following

### Create the remote connection
```
export PROJECT_ID=rocketech-de-pgcp-sandbox
export REGION=europe-west4 # gemini flash 2.0 is currently not available in London

bq mk --connection \
    --connection_type=CLOUD_RESOURCE \
    --project_id="${PROJECT_ID}" \
    --location="${REGION}" \
    'vertex_ai_remote_models'
```

