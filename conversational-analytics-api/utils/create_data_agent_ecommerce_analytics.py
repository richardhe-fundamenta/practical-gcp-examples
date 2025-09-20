import os
import logging

from google.cloud import geminidataanalytics

# System instructions, add key information to fill the gap in metadata that otherwise is not obvious.
SYSTEM_INSTRUCTION = """
- system_instruction: >-
    You are an expert sales analyst for a ecommerce store. You will answer questions about sales, orders, and customer data. Your responses should be concise and data-driven.
    You should always prioritise join all required tables togather and does aggregation in one step if possible.
    TIMESTAMP_SUB() does not support week or month, if subtraction is required for week or month, always use DATE_SUB() instead, i.e. SELECT TIMESTAMP(DATE_SUB(DATE(my_timestamp_column), INTERVAL 1 MONTH)) FROM my_table;
- tables:
    - table:
        - name: ecommerce_analytics.orders
        - description: All the ordres placed by customers
        - synonyms: orders
        - fields:
            - field:
                - name: order_date
                - description: Do not use this column, it contains incorrect data
            - field:
                - name: order_date_1
                - description: Do not use this column, it contains incorrect data
            - field:
                - name: order_date_2
                - description: This is the only correct order_date column should be used for all orders
    - relationships:
        - relationship:
            - name: order_item_to_orders
            - description: >-
                Connects order item to order
            - relationship_type: many-to-one
            - join_type: left
            - left_table: ecommerce_analytics.order_item
            - right_table: ecommerce_analytics.orders
            - relationship_columns:
                - left_column: order_number
                - right_column: order_id
        - relationship:
            - name: orders_to_customers
            - description: >-
                Connects orders to customers
            - relationship_type: many-to-one
            - join_type: left
            - left_table: ecommerce_analytics.orders
            - right_table: ecommerce_analytics.customers
            - relationship_columns:
                - left_column: cust_acct_id
                - right_column: customer_id
        - relationship:
            - name: order_item_to_products
            - description: >-
                Connects orders items to product
            - relationship_type: many-to-one
            - join_type: left
            - left_table: ecommerce_analytics.order_items
            - right_table: ecommerce_analytics.products
            - relationship_columns:
                - left_column: item_id
                - right_column: product_id
        - relationship:
            - name: products_to_product_category
            - description: >-
                Connects products to product category
            - relationship_type: many-to-one
            - join_type: left
            - left_table: ecommerce_analytics.products
            - right_table: ecommerce_analytics.product_category
            - relationship_columns:
                - left_column: prod_cat_id
                - right_column: category_id
"""


def register_table_references(project_id, dataset_id, table_id):
    bigquery_table_reference = geminidataanalytics.BigQueryTableReference()
    bigquery_table_reference.project_id = project_id
    bigquery_table_reference.dataset_id = dataset_id
    bigquery_table_reference.table_id = table_id

    return bigquery_table_reference


def create_data_agent(project_id, data_agent_id):
    data_agent_client = geminidataanalytics.DataAgentServiceClient()
    dataset_id = "ecommerce_analytics"
    system_instruction = SYSTEM_INSTRUCTION

    tables_to_register = [
        "customers",
        "order_item",
        "orders",
        "product_category",
        "products"
    ]

    registered_tables = []
    for table_name in tables_to_register:
        table_ref = register_table_references(project_id, dataset_id, table_name)
        registered_tables.append(table_ref)

    # Connect to your data source
    datasource_references = geminidataanalytics.DatasourceReferences()
    datasource_references.bq.table_references = registered_tables  # Up to 10 tables

    # Set up context for stateless chat
    inline_context = geminidataanalytics.Context()
    inline_context.system_instruction = system_instruction
    inline_context.datasource_references = datasource_references

    # Optional: To enable advanced analysis with Python, include the following line:
    inline_context.options.analysis.python.enabled = True

    # Create a data agent
    data_agent = geminidataanalytics.DataAgent()
    data_agent.data_analytics_agent.published_context = inline_context
    data_agent.name = f"projects/{project_id}/locations/global/dataAgents/{data_agent_id}"  # Optional

    request = geminidataanalytics.CreateDataAgentRequest(
        parent=f"projects/{project_id}/locations/global",
        data_agent_id=data_agent_id,  # Optional
        data_agent=data_agent,
    )

    try:
        return data_agent_client.create_data_agent(request=request)
        logging.info(f"Data Agent created, with ID: {data_agent_id}")
    except Exception as e:
        logging.error(f"Error creating Data Agent: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    project_id = "rocketech-de-pgcp-sandbox"
    data_agent_id = "ecommerce_analytics_data_agent_1"
    create_data_agent(project_id, data_agent_id)
