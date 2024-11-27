import random
import uuid
import pandas as pd

from google.cloud import bigquery
from faker import Faker
from datetime import datetime

# BigQuery configurations
PROJECT_ID = "rocketech-de-pgcp-sandbox"
DATASET_ID = "dataset_ecommerce"

# Initialize Faker and BigQuery client
fake = Faker("en_GB")
client = bigquery.Client()


# Create dataset
def create_dataset():
    dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
    dataset = bigquery.Dataset(dataset_ref)

    # Optional: Set the dataset location (e.g., EU, US)
    dataset.location = "EU"  # Set to your desired location

    # Create the dataset
    dataset = client.create_dataset(dataset, exists_ok=True)
    print(f"Dataset {DATASET_ID} created or already exists.")


# Create table schemas
def create_tables():
    tables = {
        "customers": [
            {"name": "customer_id", "field_type": "STRING"},
            {"name": "first_name", "field_type": "STRING"},
            {"name": "last_name", "field_type": "STRING"},
            {"name": "email", "field_type": "STRING"},
            {"name": "date_of_birth", "field_type": "DATE"},
            {"name": "signup_date", "field_type": "DATE"},
            {"name": "postcode", "field_type": "STRING"},
            {"name": "address_line1", "field_type": "STRING"},
            {"name": "address_line2", "field_type": "STRING"},
            {"name": "county", "field_type": "STRING"},
            {"name": "city", "field_type": "STRING"},
            {"name": "country", "field_type": "STRING"},
            {"name": "ethnic_group", "field_type": "STRING"},
            {"name": "gender", "field_type": "STRING"},
            {"name": "income_level", "field_type": "STRING"},
            {"name": "is_active", "field_type": "BOOLEAN"},
        ],
        "products": [
            {"name": "product_id", "field_type": "STRING"},
            {"name": "product_name", "field_type": "STRING"},
            {"name": "category", "field_type": "STRING"},
            {"name": "price", "field_type": "FLOAT"},
            {"name": "stock_quantity", "field_type": "INTEGER"},
        ],
        "orders": [
            {"name": "order_id", "field_type": "STRING"},
            {"name": "customer_id", "field_type": "STRING"},
            {"name": "order_date", "field_type": "DATETIME"},
            {"name": "shipping_address", "field_type": "STRING"},
            {"name": "postcode", "field_type": "STRING"},
            {"name": "total_amount", "field_type": "FLOAT"},
            {"name": "status", "field_type": "STRING"},
        ],
        "order_items": [
            {"name": "order_item_id", "field_type": "STRING"},
            {"name": "order_id", "field_type": "STRING"},
            {"name": "product_id", "field_type": "STRING"},
            {"name": "quantity", "field_type": "INTEGER"},
            {"name": "price_each", "field_type": "FLOAT"},
        ],
    }

    for table_name, schema in tables.items():
        table_id = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"
        schema = [bigquery.SchemaField(**field) for field in schema]
        table = bigquery.Table(table_id, schema=schema)
        client.create_table(table, exists_ok=True)
        print(f"Created table: {table_id}")


# Generate synthetic data
def generate_data():
    customers = []
    products = []
    orders = []
    order_items = []

    # Generate customers
    for _ in range(100000):
        customer_id = str(uuid.uuid4())
        customers.append({
            "customer_id": customer_id,
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.email(),
            "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=80),
            "signup_date": fake.date_between(start_date="-2y", end_date="-1d"),
            "postcode": fake.postcode(),
            "address_line1": fake.street_address(),
            "address_line2": fake.secondary_address(),
            "county": fake.county(),
            "city": fake.city(),
            "country": "United Kingdom",
            "ethnic_group": random.choice(["White", "Black or African", "Asian", "Mixed", "Other"]),
            "gender": random.choice(["Male", "Female", "Other"]),
            "income_level": random.choice(["Low", "Medium", "High"]),
            "is_active": random.choice([True, False]),
        })

    # Generate products
    for _ in range(50):
        products.append({
            "product_id": str(uuid.uuid4()),
            "product_name": fake.word(),
            "category": random.choice(["Electronics", "Clothing", "Home", "Beauty"]),
            "price": round(random.uniform(5, 500), 2),
            "stock_quantity": random.randint(10, 100),
        })

    # Generate orders and order items for Q3 2024
    for _ in range(20000):
        order_id = str(uuid.uuid4())
        customer_id = random.choice(customers)["customer_id"]
        order_date = fake.date_time_between(start_date=datetime(2024, 7, 1), end_date=datetime(2024, 9, 30))
        total_amount = round(random.uniform(20, 1000), 2)
        orders.append({
            "order_id": order_id,
            "customer_id": customer_id,
            "order_date": order_date,
            "shipping_address": fake.address(),
            "postcode": fake.postcode(),
            "total_amount": total_amount,
            "status": random.choice(["Completed", "Pending", "Cancelled"]),
        })

        # Generate order items
        for _ in range(random.randint(1, 5)):
            product = random.choice(products)
            quantity = random.randint(1, 3)
            order_items.append({
                "order_item_id": str(uuid.uuid4()),
                "order_id": order_id,
                "product_id": product["product_id"],
                "quantity": quantity,
                "price_each": product["price"],
            })

    return customers, products, orders, order_items


# Upload data to BigQuery
def upload_to_bigquery(table_name, data):
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"
    df = pd.DataFrame(data)
    client.load_table_from_dataframe(df, table_id).result()
    print(f"Uploaded {len(data)} records to {table_id}")


# Main function
def main():
    create_dataset()
    create_tables()
    customers, products, orders, order_items = generate_data()
    upload_to_bigquery("customers", customers)
    upload_to_bigquery("products", products)
    upload_to_bigquery("orders", orders)
    upload_to_bigquery("order_items", order_items)


if __name__ == "__main__":
    main()
