# ruff: noqa
import os
import google.auth
from pydantic import BaseModel, Field

# Set environment variables for Vertex AI
_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.workflow import Workflow, node
from google.genai import types

from app.tools import search_ingredient_price


# Define Pydantic models for structured outputs
class RecipeIngredient(BaseModel):
    name: str = Field(description="The name of the ingredient.")
    amount: str = Field(
        description="The amount needed (e.g. '200g', '2 tbsp', 'to taste')."
    )


class Recipe(BaseModel):
    name: str = Field(description="The name of the recipe.")
    instructions: list[str] = Field(
        description="Step-by-step instructions to make the recipe."
    )
    required_ingredients: list[RecipeIngredient] = Field(
        description="All ingredients required for this recipe."
    )
    missing_ingredients: list[str] = Field(
        description="Minor ingredients required for this recipe that are NOT in the fridge."
    )


class RecipePlanningOutput(BaseModel):
    recipes: list[Recipe] = Field(description="A list of 3 suggested recipes.")


# Define Node 1: Recipe Planner (LLM-driven)
plan_recipes = LlmAgent(
    name="plan_recipes",
    model="gemini-3.5-flash",
    instruction=(
        "You are an expert recipe planner. The user will provide ingredients in their fridge, "
        "dietary goals, and their city. Suggest 3 authentic recipes that can be made right now. "
        "For each recipe, list all required ingredients and their amounts, and identify any minor ingredients "
        "needed that are NOT currently in the user's fridge (these are missing ingredients). "
        "CRITICAL RULES:\n"
        "1. Focus strictly on traditional, culturally authentic dishes and cooking methods. Avoid westernizing "
        "Chinese dishes or suggesting non-authentic ingredients (e.g. do NOT use peanut butter for Kung Pao Chicken, "
        "use actual peanuts; do NOT use non-authentic sauces or substitutions).\n"
        "2. For missing ingredients, specify only the clean, generic ingredient name (e.g. 'Jasmine Rice', 'Dark Soy Sauce', "
        "'Sichuan Peppercorns', 'Shaoxing Rice Wine', 'White Pepper Powder'). Do NOT include any price estimates, store references, or approximate costs "
        "in the ingredient names (e.g. do NOT output 'Shaoxing rice wine (~£2.20 at Loon Fung)' or 'Garlic (~£0.85 for a pack of 3)'). "
        "Only write the simple ingredient name. This is crucial for successful database price lookup."
    ),
    output_schema=RecipePlanningOutput,
    output_key="recipe_plan",
)


# Define Node 2: Price Fetcher (Function-driven)
@node
def fetch_prices(ctx: Context, node_input: dict) -> Event:
    """Takes the list of missing ingredients and calls the Firestore search tool to get local London prices."""
    recipes_data = node_input.get("recipes", [])

    # Extract unique missing ingredients across all recipes
    all_missing = set()
    for recipe in recipes_data:
        for missing in recipe.get("missing_ingredients", []):
            clean_name = missing.strip().lower()
            if clean_name:
                all_missing.add(clean_name)

    # Search prices for each missing ingredient using our Firestore vector search tool
    # Group by the matched supermarket item name to avoid duplicates and double counting!
    prices_map = {}
    for ingredient in sorted(all_missing):
        matched = search_ingredient_price(ingredient)
        matched_name = matched.get("name")

        if matched_name in prices_map:
            req_items = prices_map[matched_name]["requested_items"]
            if isinstance(req_items, list) and ingredient not in req_items:
                req_items.append(ingredient)
        else:
            prices_map[matched_name] = {
                "requested_items": [ingredient],
                "matched_name": matched_name,
                "category": matched.get("category"),
                "description": matched.get("description"),
                "price": matched.get("price", 0.0),
            }

    return Event(
        output={"recipes": recipes_data, "missing_prices": prices_map},
        state={"missing_prices": prices_map},
    )


# Define Node 3: Response Formatter (Function-driven, user-facing output)
@node
def format_response(ctx: Context, node_input: dict):
    """Formats the final text output for the user, combining recipes and missing ingredient prices."""
    recipes = node_input.get("recipes", [])
    prices_map = node_input.get("missing_prices", {})

    markdown_lines = []
    markdown_lines.append("# Local Recipe Planner - Your Custom Meal Plan\n")

    markdown_lines.append("## Suggested Recipes\n")
    for i, recipe in enumerate(recipes):
        markdown_lines.append(f"### {i + 1}. {recipe['name']}\n")
        markdown_lines.append("**Required Ingredients:**")
        for ing in recipe.get("required_ingredients", []):
            markdown_lines.append(f"- {ing['name']} ({ing['amount']})")

        markdown_lines.append("\n**Instructions:**")
        for step_idx, step in enumerate(recipe.get("instructions", [])):
            markdown_lines.append(f"{step_idx + 1}. {step}")

        missing = recipe.get("missing_ingredients", [])
        if missing:
            markdown_lines.append(f"\n**Missing Ingredients:** {', '.join(missing)}")
        else:
            markdown_lines.append("\n**You have all ingredients for this recipe!**")
        markdown_lines.append("\n" + "-" * 40 + "\n")

    markdown_lines.append(
        "## Missing Ingredients Price Guide (London Supermarket Generic Prices)\n"
    )

    total_cost = 0.0
    if prices_map:
        markdown_lines.append(
            "| Missing Item | Matched London Item | Category | Price | Description |"
        )
        markdown_lines.append("| --- | --- | --- | --- | --- |")
        for matched_name, data in sorted(prices_map.items()):
            price = data["price"]
            total_cost += price
            # Show all user-requested items that matched this database item
            requested_str = ", ".join(sorted(data["requested_items"]))
            markdown_lines.append(
                f"| {requested_str} | {matched_name} | {data['category']} | £{price:.2f} | {data['description']} |"
            )

        markdown_lines.append(
            f"\n**Estimated Total Cost for Missing Ingredients: £{total_cost:.2f}**\n"
        )
    else:
        markdown_lines.append(
            "You don't need to buy any extra ingredients! Enjoy your meal.\n"
        )

    final_text = "\n".join(markdown_lines)

    # Yield content event for the Web UI/Playground/A2A client
    yield Event(
        content=types.Content(
            role="model", parts=[types.Part.from_text(text=final_text)]
        )
    )
    yield Event(output=final_text)


# Build the Workflow Graph
root_agent = Workflow(
    name="local_recipe_planner",
    edges=[
        ("START", plan_recipes),
        (plan_recipes, fetch_prices),
        (fetch_prices, format_response),
    ],
    description="Graph-based local recipe planner with missing ingredients pricing.",
)

# App instance
app = App(
    root_agent=root_agent,
    name="app",
)
