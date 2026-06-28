import os

from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

# Configure clients globally
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# We initialize clients for us-central1 and our Firestore database
genai_client = genai.Client(
    vertexai=True, project="rocketech-de-pgcp-sandbox", location="us-central1"
)
db_client = firestore.Client(
    project="rocketech-de-pgcp-sandbox", database="agents-shared"
)


def search_ingredient_price(ingredient_name: str) -> dict:
    """Finds the closest matching ingredient in London supermarkets and retrieves its category, description, and price in GBP.

    Args:
        ingredient_name: The name or description of the ingredient (e.g. 'pork mince', 'spring onion', 'ginger').

    Returns:
        A dictionary containing the name, category, description, and price of the closest matched ingredient in London.
    """
    try:
        # Generate embedding for the search query
        response = genai_client.models.embed_content(
            model="text-embedding-004",
            contents=ingredient_name,
        )
        query_vector = response.embeddings[0].values

        # Perform Firestore Vector Search
        collection = db_client.collection("ingredients")
        results = collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vector),
            distance_measure=DistanceMeasure.COSINE,
            limit=1,
        ).get()

        if not results:
            return {
                "name": ingredient_name,
                "category": "Unknown",
                "description": "No matching ingredient found in the London database.",
                "price": 0.0,
            }

        doc = results[0]
        data = doc.to_dict()
        return {
            "name": data.get("name"),
            "category": data.get("category"),
            "description": data.get("description"),
            "price": float(data.get("price", 0.0)),
        }
    except Exception as e:
        print(f"Error searching ingredient price for '{ingredient_name}': {e}")
        # Return a fallback representation so the agent fails gracefully
        return {
            "name": ingredient_name,
            "category": "Unknown",
            "description": f"Fallback due to error: {e!s}",
            "price": 1.50,  # Reasonable default price in GBP
        }
