# Dataplex Auto DQ with Yaml

Use the YAML standard to manage data quality scan with Dataplex. 

## Generate fake data
See [fake_data_gen.py](fake_data_gen.py), this script generates 5000 rows of fake customer data with various issues.  
The data structure generated here specifically takes STRUCT into account. 

## YAML rules
See the rule YAML file [validate__customer_with_issues.yaml](rules/dataplex_dq_demo/validate__customer_with_issues.yaml) for an example what a YAML rule file looks like.

## Create scan

```
export PROJECT_ID=rocketech-de-pgcp-sandbox
export REGION=europe-west2
export DQ_DATASET=dataplex_dq_demo
export DQ_TABLE=customer_with_issues

gcloud dataplex datascans create data-quality validate--${DQ_DATASET//_/-}--${DQ_TABLE//_/-} \
    --location=${REGION} \
    --data-quality-spec-file=rules/dataplex_dq_demo/validate__${DQ_TABLE}.yaml \
    --data-source-resource="//bigquery.googleapis.com/projects/${PROJECT_ID}/datasets/${DQ_DATASET}/tables/${DQ_TABLE}"
```