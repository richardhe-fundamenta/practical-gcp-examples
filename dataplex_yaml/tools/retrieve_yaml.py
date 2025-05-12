import os
import yaml

from google.cloud import dataplex_v1


def get_data_quality_scan(project_id, location, data_scan_id):
    client = dataplex_v1.DataScanServiceClient()
    name = f"projects/{project_id}/locations/{location}/dataScans/{data_scan_id}"
    view = 'FULL'
    scan_request = dataplex_v1.GetDataScanRequest(name=name, view=view)

    response = client.get_data_scan(request=scan_request)
    return response


def main():
    project_id = os.environ.get('PROJECT_ID', 'rocketech-de-pgcp-sandbox')
    location = os.environ.get('LOCATION', 'EU')
    data_scan_id = os.environ.get('DATA_SCAN_ID')

    data_scan = get_data_quality_scan(project_id, location, data_scan_id)

    # Access the data quality specification
    data_quality_spec = data_scan.data_quality_spec

    print(data_quality_spec)

    if data_quality_spec:
        # Extract the rules from the data quality specification
        rules = data_quality_spec.rules

        if rules:
            # Convert the rules to a list of dictionaries
            rules_list = [dataplex_v1.DataQualityRule.to_dict(rule) for rule in rules]

            # Output the rules as a YAML-formatted string
            yaml_output = yaml.dump(rules_list, default_flow_style=False)
            print(yaml_output)
        else:
            print("No data quality rules found in the scan.")
    else:
        print("No data quality specification found in the scan.")


if __name__ == "__main__":
    main()
