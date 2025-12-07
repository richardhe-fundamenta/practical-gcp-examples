"""YAML configuration generator for MCP Toolbox."""

import logging
from typing import Any
from collections import defaultdict

import yaml

logger = logging.getLogger(__name__)


class ToolboxConfigGenerator:
    """Generates MCP Toolbox YAML configuration from query registry data."""

    def __init__(
        self,
        project_id: str,
        bigquery_source_name: str = "bigquery-source",
    ):
        """Initialize the config generator.

        Args:
            project_id: GCP project ID for BigQuery source
            bigquery_source_name: Name for the BigQuery source in tools.yaml
        """
        self.project_id = project_id
        self.bigquery_source_name = bigquery_source_name

    def generate_config(self, queries: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate complete toolbox configuration from queries.

        Args:
            queries: List of query dictionaries from the registry

        Returns:
            Complete toolbox configuration dictionary
        """
        logger.info(f"Generating toolbox config for {len(queries)} queries")

        config = {
            "sources": self._generate_sources(),
            "tools": {},
            "toolsets": {},
        }

        # Group queries by category for toolsets
        category_tools = defaultdict(list)

        for query in queries:
            try:
                tool_name = query["query_name"]
                category = query.get("query_category", "uncategorized")

                # Generate tool configuration
                tool_config = self._generate_tool(query)
                config["tools"][tool_name] = tool_config

                # Add to category toolset
                category_tools[category].append(tool_name)

            except Exception as e:
                logger.warning(
                    f"Failed to generate config for {query.get('query_name', 'unknown')}: {e}"
                )
                continue

        # Create toolsets from categories
        config["toolsets"] = {
            category: tools for category, tools in category_tools.items()
        }

        logger.info(
            f"Generated config with {len(config['tools'])} tools "
            f"across {len(config['toolsets'])} toolsets"
        )

        return config

    def _generate_sources(self) -> dict[str, Any]:
        """Generate the sources section of the config.

        Returns:
            Sources configuration dictionary
        """
        return {
            self.bigquery_source_name: {
                "kind": "bigquery",
                "project": self.project_id,
            }
        }

    def _generate_tool(self, query: dict[str, Any]) -> dict[str, Any]:
        """Generate a single tool configuration.

        Args:
            query: Query dictionary from registry

        Returns:
            Tool configuration dictionary
        """
        tool_config = {
            "kind": "bigquery-sql",
            "source": self.bigquery_source_name,
            "statement": query["query_sql"],
            "description": query.get("description", f"Execute {query['query_name']}"),
        }

        # Add parameters if present
        if query.get("parameters"):
            tool_config["parameters"] = self._format_parameters(query["parameters"])

        return tool_config

    def _format_parameters(self, parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Format parameters for toolbox configuration.

        Args:
            parameters: List of parameter dictionaries

        Returns:
            Formatted parameters list
        """
        # Map BigQuery types to MCP toolbox types
        type_mapping = {
            "int64": "integer",
            "float64": "number",
            "bool": "boolean",
        }

        formatted = []
        for param in parameters:
            param_type = param.get("type", "string")
            # Map BigQuery type to MCP toolbox type
            mcp_type = type_mapping.get(param_type, param_type)

            formatted_param = {
                "name": param.get("name"),
                "type": mcp_type,
                "description": param.get("description", ""),
            }

            # Add optional fields if present
            if "required" in param:
                formatted_param["required"] = param["required"]
            if "default" in param:
                formatted_param["default"] = param["default"]

            formatted.append(formatted_param)

        return formatted

    def save_config(self, config: dict[str, Any], output_path: str) -> None:
        """Save configuration to a YAML file.

        Args:
            config: Configuration dictionary
            output_path: Path to save the YAML file

        Raises:
            IOError: If file cannot be written
        """
        logger.info(f"Saving configuration to {output_path}")

        try:
            with open(output_path, "w") as f:
                yaml.safe_dump(
                    config,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    width=100,
                )
            logger.info(f"Successfully saved configuration to {output_path}")

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Validate the generated configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check required top-level keys
            required_keys = ["sources", "tools"]
            for key in required_keys:
                if key not in config:
                    logger.error(f"Missing required key: {key}")
                    return False

            # Validate sources
            if not config["sources"]:
                logger.error("No sources defined")
                return False

            # Validate each tool
            for tool_name, tool_config in config["tools"].items():
                if not self._validate_tool(tool_name, tool_config):
                    return False

            # Validate toolsets reference existing tools
            if "toolsets" in config:
                all_tool_names = set(config["tools"].keys())
                for toolset_name, tool_list in config["toolsets"].items():
                    for tool_name in tool_list:
                        if tool_name not in all_tool_names:
                            logger.error(
                                f"Toolset '{toolset_name}' references "
                                f"non-existent tool '{tool_name}'"
                            )
                            return False

            logger.info("Configuration validation passed")
            return True

        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False

    def _validate_tool(self, tool_name: str, tool_config: dict[str, Any]) -> bool:
        """Validate a single tool configuration.

        Args:
            tool_name: Name of the tool
            tool_config: Tool configuration dictionary

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["kind", "source", "statement", "description"]

        for field in required_fields:
            if field not in tool_config:
                logger.error(f"Tool '{tool_name}' missing required field: {field}")
                return False

        # Validate kind
        if tool_config["kind"] not in ["bigquery-sql", "bigquery-execute-sql"]:
            logger.error(f"Tool '{tool_name}' has invalid kind: {tool_config['kind']}")
            return False

        # Validate source exists
        # Note: This assumes sources have been validated already
        if not tool_config["source"]:
            logger.error(f"Tool '{tool_name}' has empty source")
            return False

        return True

    def print_stats(self, config: dict[str, Any]) -> None:
        """Print statistics about the generated configuration.

        Args:
            config: Configuration dictionary
        """
        num_sources = len(config.get("sources", {}))
        num_tools = len(config.get("tools", {}))
        num_toolsets = len(config.get("toolsets", {}))

        print("\n" + "=" * 60)
        print("Configuration Statistics")
        print("=" * 60)
        print(f"Sources:  {num_sources}")
        print(f"Tools:    {num_tools}")
        print(f"Toolsets: {num_toolsets}")

        if config.get("toolsets"):
            print("\nToolsets breakdown:")
            for toolset_name, tools in config["toolsets"].items():
                print(f"  - {toolset_name}: {len(tools)} tools")

        print("=" * 60 + "\n")
