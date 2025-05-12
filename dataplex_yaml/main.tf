module "dataplex_data_quality_tasks" {
  source = "./modules/yaml_to_dataplex_dq"

  count = length(var.data_quality_configs)

  project_id             = var.project_id
  environment            = var.environment
  source_project         = var.source_project
  data_quality_spec_file = var.data_quality_configs[count.index].spec_file
  source_dataset         = var.data_quality_configs[count.index].source_dataset
  source_table           = var.data_quality_configs[count.index].source_table
}