import time

from google import genai
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector

# Predefined ~200 London Supermarket Ingredients
INGREDIENTS_DATA = [
    # --- Vegetables ---
    {
        "category": "Vegetables",
        "name": "Broccoli",
        "description": "Fresh green broccoli crown, perfect for steaming or roasting.",
        "price": 1.20,
    },
    {
        "category": "Vegetables",
        "name": "Carrots",
        "description": "Organic sweet orange carrots, great for snacks, soups, or roasting.",
        "price": 0.85,
    },
    {
        "category": "Vegetables",
        "name": "Maris Piper Potatoes",
        "description": "Classic British potatoes, ideal for roasting, mashing, or making chips.",
        "price": 1.50,
    },
    {
        "category": "Vegetables",
        "name": "Brown Onions",
        "description": "Essential cooking ingredient with deep savory flavor.",
        "price": 0.95,
    },
    {
        "category": "Vegetables",
        "name": "Red Onions",
        "description": "Sweet red onions, perfect for salads, burgers, or pickling.",
        "price": 1.10,
    },
    {
        "category": "Vegetables",
        "name": "Garlic",
        "description": "Whole garlic bulbs, a staple seasoning for countless dishes.",
        "price": 0.65,
    },
    {
        "category": "Vegetables",
        "name": "Ginger Root",
        "description": "Fresh spicy ginger root, excellent for stir-fries and teas.",
        "price": 1.40,
    },
    {
        "category": "Vegetables",
        "name": "English Cucumber",
        "description": "Crisp and refreshing cucumber, ideal for salads and sandwiches.",
        "price": 0.79,
    },
    {
        "category": "Vegetables",
        "name": "Beef Tomatoes",
        "description": "Large, juicy tomatoes, perfect for slicing or stuffing.",
        "price": 1.85,
    },
    {
        "category": "Vegetables",
        "name": "Cherry Tomatoes",
        "description": "Sweet baby cherry tomatoes, great for roasting or salads.",
        "price": 1.25,
    },
    {
        "category": "Vegetables",
        "name": "Spinach",
        "description": "Fresh pre-washed baby spinach leaves, rich in iron.",
        "price": 1.50,
    },
    {
        "category": "Vegetables",
        "name": "Iceberg Lettuce",
        "description": "Crisp, classic iceberg lettuce head, great for burgers and wraps.",
        "price": 0.80,
    },
    {
        "category": "Vegetables",
        "name": "Red Bell Pepper",
        "description": "Sweet and crunchy red bell pepper, perfect for stir-fries.",
        "price": 0.99,
    },
    {
        "category": "Vegetables",
        "name": "Yellow Bell Pepper",
        "description": "Crunchy yellow bell pepper, adds color and sweetness to dishes.",
        "price": 0.99,
    },
    {
        "category": "Vegetables",
        "name": "Green Bell Pepper",
        "description": "Slightly bitter and fresh green bell pepper, ideal for fajitas.",
        "price": 0.85,
    },
    {
        "category": "Vegetables",
        "name": "Portobello Mushrooms",
        "description": "Large meaty mushrooms, excellent for grilling or stuffing.",
        "price": 1.95,
    },
    {
        "category": "Vegetables",
        "name": "White Button Mushrooms",
        "description": "Versatile mushrooms, great for sauces and fry-ups.",
        "price": 1.15,
    },
    {
        "category": "Vegetables",
        "name": "Zucchini (Courgette)",
        "description": "Fresh green courgettes, delicious grilled or sautéed.",
        "price": 1.30,
    },
    {
        "category": "Vegetables",
        "name": "Aubergine (Eggplant)",
        "description": "Glossy purple aubergine, perfect for roasting, curries, or moussaka.",
        "price": 1.40,
    },
    {
        "category": "Vegetables",
        "name": "Butternut Squash",
        "description": "Sweet, nutty butternut squash, great for autumn roasting and soups.",
        "price": 1.60,
    },
    {
        "category": "Vegetables",
        "name": "Sweet Potato",
        "description": "Nutritious sweet potatoes, perfect for baking or making fries.",
        "price": 1.70,
    },
    {
        "category": "Vegetables",
        "name": "Celery",
        "description": "Crisp celery stalks, a key base ingredient for stews and soups.",
        "price": 0.90,
    },
    {
        "category": "Vegetables",
        "name": "Leeks",
        "description": "Mild, sweet onion-like flavor, excellent for soups and pies.",
        "price": 1.35,
    },
    {
        "category": "Vegetables",
        "name": "Spring Onions (Scallions)",
        "description": "Fresh green onions, ideal garnish for stir-fries and salads.",
        "price": 0.55,
    },
    {
        "category": "Vegetables",
        "name": "Asparagus Spears",
        "description": "Tender green asparagus spears, delicious grilled or roasted.",
        "price": 2.20,
    },
    {
        "category": "Vegetables",
        "name": "Brussel Sprouts",
        "description": "Classic green sprouts, perfect roasted with bacon.",
        "price": 1.25,
    },
    {
        "category": "Vegetables",
        "name": "Red Cabbage",
        "description": "Crunchy red cabbage, great for coleslaw or slow braising.",
        "price": 1.00,
    },
    {
        "category": "Vegetables",
        "name": "Savoy Cabbage",
        "description": "Wrinkled, textured green cabbage, ideal for winter side dishes.",
        "price": 1.10,
    },
    {
        "category": "Vegetables",
        "name": "Cauliflower",
        "description": "Fresh white cauliflower head, great for baking, roasting, or mashing.",
        "price": 1.30,
    },
    {
        "category": "Vegetables",
        "name": "Pak Choi (Bok Choy)",
        "description": "Crisp leafy green pak choi, staple for authentic Chinese stir-fries.",
        "price": 1.50,
    },
    # --- Fruits ---
    {
        "category": "Fruits",
        "name": "Gala Apples",
        "description": "Crisp and sweet red Gala apples, perfect for snacking.",
        "price": 1.60,
    },
    {
        "category": "Fruits",
        "name": "Bananas",
        "description": "Sweet, ripe yellow bananas, a high-energy snack.",
        "price": 0.90,
    },
    {
        "category": "Fruits",
        "name": "Easy Peeler Clementines",
        "description": "Sweet and juicy clementines, easy to peel.",
        "price": 1.80,
    },
    {
        "category": "Fruits",
        "name": "Conference Pears",
        "description": "Sweet and juicy British pears, perfect for desserts.",
        "price": 1.70,
    },
    {
        "category": "Fruits",
        "name": "Lemons",
        "description": "Zesty yellow lemons, essential for cooking and drinks.",
        "price": 0.35,
    },
    {
        "category": "Fruits",
        "name": "Limes",
        "description": "Fresh green limes, great for Mexican, Thai, and cocktails.",
        "price": 0.40,
    },
    {
        "category": "Fruits",
        "name": "Blueberries",
        "description": "Sweet, antioxidant-rich fresh blueberries.",
        "price": 2.30,
    },
    {
        "category": "Fruits",
        "name": "Strawberries",
        "description": "Sweet British strawberries, perfect with cream.",
        "price": 2.50,
    },
    {
        "category": "Fruits",
        "name": "Raspberries",
        "description": "Tart and sweet fresh raspberries.",
        "price": 2.50,
    },
    {
        "category": "Fruits",
        "name": "Red Grapes",
        "description": "Seedless red grapes, sweet and crisp.",
        "price": 2.00,
    },
    {
        "category": "Fruits",
        "name": "White Grapes",
        "description": "Seedless green grapes, crisp and sweet.",
        "price": 2.00,
    },
    {
        "category": "Fruits",
        "name": "Avocado",
        "description": "Creamy fresh avocado, ready to eat.",
        "price": 1.10,
    },
    {
        "category": "Fruits",
        "name": "Pineapple",
        "description": "Whole sweet gold pineapple, tropical and juicy.",
        "price": 1.95,
    },
    {
        "category": "Fruits",
        "name": "Mango",
        "description": "Sweet Kent mango, juicy and soft.",
        "price": 1.50,
    },
    {
        "category": "Fruits",
        "name": "Oranges",
        "description": "Large juicy oranges, great for snacking or juicing.",
        "price": 1.40,
    },
    {
        "category": "Fruits",
        "name": "Kiwi Fruit",
        "description": "Tangy green kiwi fruit, high in vitamin C.",
        "price": 1.20,
    },
    {
        "category": "Fruits",
        "name": "Watermelon",
        "description": "Refreshing sweet watermelon slice, perfect for summer.",
        "price": 2.50,
    },
    {
        "category": "Fruits",
        "name": "Pomegranate",
        "description": "Whole pomegranate, filled with juicy ruby seeds.",
        "price": 1.25,
    },
    {
        "category": "Fruits",
        "name": "Peaches",
        "description": "Sweet, soft freestone peaches.",
        "price": 1.75,
    },
    {
        "category": "Fruits",
        "name": "Plums",
        "description": "Sweet and tart purple plums.",
        "price": 1.50,
    },
    # --- Meat & Poultry ---
    {
        "category": "Meat & Poultry",
        "name": "Chicken Breasts",
        "description": "Boneless skinless British chicken breast fillets, lean and versatile.",
        "price": 5.50,
    },
    {
        "category": "Meat & Poultry",
        "name": "Chicken Thighs",
        "description": "Bone-in, skin-on chicken thighs for rich flavor and juiciness.",
        "price": 3.80,
    },
    {
        "category": "Meat & Poultry",
        "name": "Chicken Wings",
        "description": "Fresh chicken wings, perfect for baking or frying.",
        "price": 2.20,
    },
    {
        "category": "Meat & Poultry",
        "name": "Whole Chicken",
        "description": "Fresh British whole chicken, ideal for a Sunday roast.",
        "price": 6.00,
    },
    {
        "category": "Meat & Poultry",
        "name": "Minced Beef (10% Fat)",
        "description": "Lean British minced beef, perfect for spaghetti bolognese or lasagna.",
        "price": 4.50,
    },
    {
        "category": "Meat & Poultry",
        "name": "Beef Rump Steak",
        "description": "Tender and flavorful British beef rump steak.",
        "price": 7.50,
    },
    {
        "category": "Meat & Poultry",
        "name": "Beef Chuck Steak",
        "description": "Beef chuck cut, perfect for slow-cooked stews and pies.",
        "price": 5.80,
    },
    {
        "category": "Meat & Poultry",
        "name": "Pork Chops",
        "description": "Thick-cut British pork loin chops, juicy and flavorful.",
        "price": 3.50,
    },
    {
        "category": "Meat & Poultry",
        "name": "Pork Belly",
        "description": "Rich pork belly slices, perfect for crispy roasting or Chinese red braised pork.",
        "price": 4.20,
    },
    {
        "category": "Meat & Poultry",
        "name": "Pork Sausage",
        "description": "Classic British pork sausages, great for breakfast or bangers and mash.",
        "price": 2.50,
    },
    {
        "category": "Meat & Poultry",
        "name": "Minced Pork",
        "description": "Fresh minced pork, ideal for Chinese dumplings, meatballs, and mapo tofu.",
        "price": 3.50,
    },
    {
        "category": "Meat & Poultry",
        "name": "Lamb Chops",
        "description": "Tender British lamb chops, perfect for grilling with rosemary.",
        "price": 8.00,
    },
    {
        "category": "Meat & Poultry",
        "name": "Lamb Shank",
        "description": "Slow-roast lamb shank, rich and tender.",
        "price": 9.00,
    },
    {
        "category": "Meat & Poultry",
        "name": "Smoked Back Bacon",
        "description": "Classic British smoked back bacon slices, perfect for breakfast.",
        "price": 2.20,
    },
    {
        "category": "Meat & Poultry",
        "name": "Unsmoked Streaky Bacon",
        "description": "Crispy streaky bacon slices, great for wraps or wrapping meat.",
        "price": 2.40,
    },
    {
        "category": "Meat & Poultry",
        "name": "Turkey Breast Mince",
        "description": "Ultra-lean turkey mince, a healthy beef alternative.",
        "price": 3.80,
    },
    {
        "category": "Meat & Poultry",
        "name": "Duck Breast",
        "description": "Rich, gamey duck breast fillets, ideal for pan-searing.",
        "price": 7.00,
    },
    {
        "category": "Meat & Poultry",
        "name": "Gammon Joint",
        "description": "British gammon joint, perfect for boiling and glazing.",
        "price": 5.50,
    },
    {
        "category": "Meat & Poultry",
        "name": "Beef Brisket",
        "description": "Tender beef brisket, excellent for slow-cooked pulled beef.",
        "price": 6.80,
    },
    {
        "category": "Meat & Poultry",
        "name": "Pork Loin Roast",
        "description": "Boneless pork loin joint, perfect for crackling roast.",
        "price": 5.00,
    },
    # --- Fish & Seafood ---
    {
        "category": "Fish & Seafood",
        "name": "Salmon Fillets",
        "description": "Boneless skin-on salmon fillets, rich in Omega-3.",
        "price": 6.50,
    },
    {
        "category": "Fish & Seafood",
        "name": "Cod Fillets",
        "description": "Flaky white cod fillets, perfect for classic fish and chips.",
        "price": 5.80,
    },
    {
        "category": "Fish & Seafood",
        "name": "Sea Bass Fillets",
        "description": "Delicate sea bass fillets, perfect for pan-frying or steaming.",
        "price": 6.00,
    },
    {
        "category": "Fish & Seafood",
        "name": "Haddock Fillets",
        "description": "Fresh white haddock fillets, great for baking or frying.",
        "price": 5.50,
    },
    {
        "category": "Fish & Seafood",
        "name": "King Prawns",
        "description": "Raw, peeled king prawns, perfect for stir-fries and curries.",
        "price": 4.50,
    },
    {
        "category": "Fish & Seafood",
        "name": "Cooked Tiger Prawns",
        "description": "Ready-to-eat cooked tiger prawns, perfect for salads.",
        "price": 4.80,
    },
    {
        "category": "Fish & Seafood",
        "name": "Canned Tuna in Sunflower Oil",
        "description": "Flaky canned tuna, perfect for sandwiches and pasta bakes.",
        "price": 1.20,
    },
    {
        "category": "Fish & Seafood",
        "name": "Canned Tuna in Spring Water",
        "description": "Lean canned tuna, great for healthy salads and spreads.",
        "price": 1.25,
    },
    {
        "category": "Fish & Seafood",
        "name": "Canned Sardines in Tomato Sauce",
        "description": "Nutritious sardines in rich tomato sauce.",
        "price": 0.85,
    },
    {
        "category": "Fish & Seafood",
        "name": "Mackerel Fillets",
        "description": "Smoked mackerel fillets, rich and savory, ready to eat.",
        "price": 3.00,
    },
    {
        "category": "Fish & Seafood",
        "name": "Squid Tubes",
        "description": "Cleaned squid tubes, perfect for calamari or seafood stir-fry.",
        "price": 4.00,
    },
    {
        "category": "Fish & Seafood",
        "name": "Scallops",
        "description": "Sweet, delicate king scallops, perfect for quick searing.",
        "price": 8.50,
    },
    {
        "category": "Fish & Seafood",
        "name": "Mussels",
        "description": "Fresh live mussels, great for steaming in white wine sauce.",
        "price": 3.50,
    },
    {
        "category": "Fish & Seafood",
        "name": "Crab Meat",
        "description": "Sweet, shredded white and brown crab meat mix.",
        "price": 5.00,
    },
    {
        "category": "Fish & Seafood",
        "name": "Smoked Salmon",
        "description": "Premium oak-smoked salmon slices, perfect for bagels.",
        "price": 4.50,
    },
    # --- Dairy & Eggs ---
    {
        "category": "Dairy & Eggs",
        "name": "Semi-Skimmed Milk",
        "description": "Fresh British semi-skimmed milk, 2 pints.",
        "price": 1.30,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Whole Milk",
        "description": "Rich and creamy whole milk, 2 pints.",
        "price": 1.35,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Unsalted Butter",
        "description": "Pure British cream unsalted butter, perfect for baking.",
        "price": 2.10,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Salted Butter",
        "description": "Savory cream salted butter, perfect for spreading.",
        "price": 2.10,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Large Free Range Eggs",
        "description": "Six large free-range eggs, rich orange yolks.",
        "price": 1.85,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Cheddar Cheese (Mature)",
        "description": "Sharp, mature British cheddar cheese block.",
        "price": 3.20,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Mozzarella Cheese",
        "description": "Fresh mozzarella cheese ball in whey.",
        "price": 1.10,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Grated Parmesan (Parmigiano)",
        "description": "Finely grated aged Parmesan cheese for pasta dishes.",
        "price": 2.50,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Greek Yogurt",
        "description": "Thick, creamy authentic Greek yogurt, high in protein.",
        "price": 1.75,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Double Cream",
        "description": "Rich double cream, ideal for desserts and sauces.",
        "price": 1.45,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Single Cream",
        "description": "Fresh single cream, lighter option for pouring.",
        "price": 1.15,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Sour Cream",
        "description": "Tangy sour cream, perfect for Mexican dishes.",
        "price": 1.20,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Cottage Cheese",
        "description": "Low-fat curd cottage cheese, healthy snack.",
        "price": 1.30,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Cream Cheese",
        "description": "Smooth soft cream cheese, perfect for bagels.",
        "price": 1.60,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Feta Cheese",
        "description": "Tangy, crumbly Greek feta cheese block.",
        "price": 1.90,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Silken Tofu",
        "description": "Soft silken tofu, great for soups, desserts, or mapo tofu.",
        "price": 1.50,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Firm Tofu",
        "description": "Dense, press-packed firm tofu, excellent for stir-fries.",
        "price": 1.70,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Crème Fraîche",
        "description": "Rich and thick French-style soured cream.",
        "price": 1.50,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Brie Cheese",
        "description": "Soft, creamy French Brie cheese wheel.",
        "price": 2.20,
    },
    {
        "category": "Dairy & Eggs",
        "name": "Oat Milk (Barista)",
        "description": "Creamy oat milk, perfect for coffee and cereals.",
        "price": 1.90,
    },
    # --- Pantry & Grains ---
    {
        "category": "Pantry & Grains",
        "name": "White Basmati Rice",
        "description": "Fragrant long grain white Basmati rice.",
        "price": 2.00,
    },
    {
        "category": "Pantry & Grains",
        "name": "Jasmine Rice",
        "description": "Fragrant Thai Jasmine rice, sticky texture, ideal for Chinese meals.",
        "price": 2.50,
    },
    {
        "category": "Pantry & Grains",
        "name": "Brown Rice",
        "description": "Nutritious whole grain brown rice.",
        "price": 1.80,
    },
    {
        "category": "Pantry & Grains",
        "name": "Penne Pasta",
        "description": "Dry penne rigate pasta, 100% durum wheat.",
        "price": 0.95,
    },
    {
        "category": "Pantry & Grains",
        "name": "Spaghetti",
        "description": "Classic dry spaghetti pasta, perfect for bolognese.",
        "price": 0.95,
    },
    {
        "category": "Pantry & Grains",
        "name": "Macaroni",
        "description": "Elbow macaroni, ideal for mac and cheese.",
        "price": 0.90,
    },
    {
        "category": "Pantry & Grains",
        "name": "Rolled Oats",
        "description": "100% whole grain rolled oats for porridge.",
        "price": 1.10,
    },
    {
        "category": "Pantry & Grains",
        "name": "Plain Flour",
        "description": "All-purpose plain white wheat flour.",
        "price": 0.85,
    },
    {
        "category": "Pantry & Grains",
        "name": "Self-Raising Flour",
        "description": "White flour with raising agents, perfect for cakes.",
        "price": 0.90,
    },
    {
        "category": "Pantry & Grains",
        "name": "Canned Chopped Tomatoes",
        "description": "Rich chopped tomatoes in juice, essential pantry staple.",
        "price": 0.65,
    },
    {
        "category": "Pantry & Grains",
        "name": "Tomato Paste (Purée)",
        "description": "Double concentrated rich tomato purée.",
        "price": 0.50,
    },
    {
        "category": "Pantry & Grains",
        "name": "Canned Chickpeas",
        "description": "Cooked chickpeas in water, great for hummus and curries.",
        "price": 0.70,
    },
    {
        "category": "Pantry & Grains",
        "name": "Canned Red Kidney Beans",
        "description": "Kidney beans in water, essential for chilli con carne.",
        "price": 0.70,
    },
    {
        "category": "Pantry & Grains",
        "name": "Canned Black Beans",
        "description": "Savory black beans, great for Mexican or Chinese dishes.",
        "price": 0.80,
    },
    {
        "category": "Pantry & Grains",
        "name": "Canned Sweetcorn",
        "description": "Sweet, crisp sweetcorn kernels in water.",
        "price": 0.75,
    },
    {
        "category": "Pantry & Grains",
        "name": "Granulated Sugar",
        "description": "Sweet white granulated sugar, 1kg.",
        "price": 1.05,
    },
    {
        "category": "Pantry & Grains",
        "name": "Caster Sugar",
        "description": "Fine baking sugar, perfect for meringues and cakes.",
        "price": 1.40,
    },
    {
        "category": "Pantry & Grains",
        "name": "Brown Soft Sugar",
        "description": "Moist soft brown sugar, adds caramel flavor.",
        "price": 1.60,
    },
    {
        "category": "Pantry & Grains",
        "name": "Honey",
        "description": "Clear honey in a squeezy bottle.",
        "price": 2.20,
    },
    {
        "category": "Pantry & Grains",
        "name": "Maple Syrup",
        "description": "Pure Canadian maple syrup, rich and sweet.",
        "price": 4.50,
    },
    {
        "category": "Pantry & Grains",
        "name": "Olive Oil",
        "description": "Pure olive oil, perfect for cooking and roasting.",
        "price": 5.00,
    },
    {
        "category": "Pantry & Grains",
        "name": "Extra Virgin Olive Oil",
        "description": "Cold-pressed extra virgin olive oil for dressings.",
        "price": 6.50,
    },
    {
        "category": "Pantry & Grains",
        "name": "Vegetable Oil",
        "description": "Neutral cooking oil, perfect for frying.",
        "price": 2.50,
    },
    {
        "category": "Pantry & Grains",
        "name": "Sesame Oil",
        "description": "Toasted sesame oil, highly aromatic, staple for Chinese seasoning.",
        "price": 2.00,
    },
    {
        "category": "Pantry & Grains",
        "name": "Quinoa",
        "description": "High-protein white quinoa grains.",
        "price": 2.30,
    },
    # --- Herbs & Spices ---
    {
        "category": "Herbs & Spices",
        "name": "Salt",
        "description": "Fine table salt for everyday seasoning.",
        "price": 0.60,
    },
    {
        "category": "Herbs & Spices",
        "name": "Black Peppercorns",
        "description": "Whole black peppercorns in a grinder.",
        "price": 1.50,
    },
    {
        "category": "Herbs & Spices",
        "name": "Sichuan Peppercorns",
        "description": "Fragrant, numbing Sichuan peppercorns, essential for authentic Chinese dishes.",
        "price": 2.50,
    },
    {
        "category": "Herbs & Spices",
        "name": "Five Spice Powder",
        "description": "Traditional Chinese blend of cinnamon, cloves, fennel, star anise, and Sichuan pepper.",
        "price": 1.20,
    },
    {
        "category": "Herbs & Spices",
        "name": "Star Anise",
        "description": "Whole star anise pods, great for slow-cooked Chinese braises.",
        "price": 1.50,
    },
    {
        "category": "Herbs & Spices",
        "name": "Dried Oregano",
        "description": "Aromatic dried oregano leaves.",
        "price": 0.95,
    },
    {
        "category": "Herbs & Spices",
        "name": "Dried Basil",
        "description": "Sweet dried basil leaves.",
        "price": 0.95,
    },
    {
        "category": "Herbs & Spices",
        "name": "Chili Flakes",
        "description": "Crushed red hot chili pepper flakes.",
        "price": 1.10,
    },
    {
        "category": "Herbs & Spices",
        "name": "Smoked Paprika",
        "description": "Sweet and smoky Spanish ground paprika.",
        "price": 1.20,
    },
    {
        "category": "Herbs & Spices",
        "name": "Ground Cumin",
        "description": "Earthy, aromatic ground cumin powder.",
        "price": 1.10,
    },
    {
        "category": "Herbs & Spices",
        "name": "Ground Coriander",
        "description": "Citrusy ground coriander seed powder.",
        "price": 1.10,
    },
    {
        "category": "Herbs & Spices",
        "name": "Turmeric Powder",
        "description": "Bright yellow ground turmeric spice.",
        "price": 1.15,
    },
    {
        "category": "Herbs & Spices",
        "name": "Garlic Powder",
        "description": "Dehydrated ground garlic for easy seasoning.",
        "price": 1.20,
    },
    {
        "category": "Herbs & Spices",
        "name": "Onion Powder",
        "description": "Sweet savory onion powder.",
        "price": 1.20,
    },
    {
        "category": "Herbs & Spices",
        "name": "Curry Powder (Mild)",
        "description": "Classic fragrant aromatic curry powder blend.",
        "price": 1.30,
    },
    {
        "category": "Herbs & Spices",
        "name": "Fresh Coriander (Cilantro)",
        "description": "Fresh cut coriander bunch, ideal garnish.",
        "price": 0.75,
    },
    {
        "category": "Herbs & Spices",
        "name": "Fresh Flat Parsley",
        "description": "Fresh Italian flat-leaf parsley bunch.",
        "price": 0.75,
    },
    {
        "category": "Herbs & Spices",
        "name": "Fresh Basil",
        "description": "Fresh sweet basil leaves in a pot.",
        "price": 1.20,
    },
    {
        "category": "Herbs & Spices",
        "name": "Fresh Rosemary",
        "description": "Fragrant fresh rosemary sprigs, great for lamb and potatoes.",
        "price": 0.80,
    },
    {
        "category": "Herbs & Spices",
        "name": "Fresh Thyme",
        "description": "Earthy fresh thyme sprigs.",
        "price": 0.80,
    },
    {
        "category": "Herbs & Spices",
        "name": "Bay Leaves",
        "description": "Dried whole bay leaves, essential for stews.",
        "price": 0.90,
    },
    {
        "category": "Herbs & Spices",
        "name": "Cinnamon Sticks",
        "description": "Whole sweet cinnamon bark sticks.",
        "price": 1.50,
    },
    {
        "category": "Herbs & Spices",
        "name": "Ground Cinnamon",
        "description": "Sweet ground cinnamon powder for baking.",
        "price": 1.10,
    },
    {
        "category": "Herbs & Spices",
        "name": "Nutmeg",
        "description": "Whole nutmeg seeds, great for grating into cheese sauce.",
        "price": 1.60,
    },
    {
        "category": "Herbs & Spices",
        "name": "Cloves",
        "description": "Whole dried cloves, highly aromatic.",
        "price": 1.40,
    },
    # --- Condiments & Sauces ---
    {
        "category": "Condiments & Sauces",
        "name": "Light Soy Sauce",
        "description": "Savory, salty Chinese light soy sauce for stir-fries and seasoning.",
        "price": 1.50,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Dark Soy Sauce",
        "description": "Thick, rich Chinese dark soy sauce for deep color and caramel undertones.",
        "price": 1.60,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Oyster Sauce",
        "description": "Thick, savory oyster-flavored sauce, essential for Chinese stir-fries.",
        "price": 2.20,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Shaoxing Rice Wine",
        "description": "Traditional Chinese cooking wine, neutralizes meat odors and adds depth.",
        "price": 2.50,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Chili Crisp (Lao Gan Ma)",
        "description": "Famous spicy, savory chili oil crisp with soy beans.",
        "price": 2.80,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Doubanjiang (Spicy Broad Bean Paste)",
        "description": "Fermented chili and broad bean paste, the soul of Sichuan Mapo Tofu.",
        "price": 2.50,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Rice Vinegar",
        "description": "Mild, slightly sweet vinegar, ideal for Chinese cooking and dipping.",
        "price": 1.40,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Chinkiang Black Vinegar",
        "description": "Fruity, complex Chinese black vinegar, perfect for dumpling dipping.",
        "price": 2.20,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Mayonnaise",
        "description": "Creamy mayonnaise made with free range eggs.",
        "price": 1.95,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Tomato Ketchup",
        "description": "Rich tomato ketchup in a squeezy bottle.",
        "price": 1.80,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Dijon Mustard",
        "description": "Smooth, sharp French Dijon mustard.",
        "price": 1.30,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Wholegrain Mustard",
        "description": "Coarse wholegrain mustard with wine.",
        "price": 1.30,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Sriracha Hot Sauce",
        "description": "Spicy Thai chili garlic hot sauce.",
        "price": 2.50,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Worcestershire Sauce",
        "description": "Savory, tangy condiment sauce for savory dishes.",
        "price": 1.60,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Sweet Chili Sauce",
        "description": "Sweet and mildly spicy chili dipping sauce.",
        "price": 1.50,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Hoisin Sauce",
        "description": "Thick, sweet and savory Cantonese BBQ sauce.",
        "price": 1.80,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Tahini Paste",
        "description": "Sesame seed paste, perfect for hummus or noodle dressings.",
        "price": 2.30,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Peanut Butter (Smooth)",
        "description": "100% roasted peanut smooth spread.",
        "price": 1.90,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Balsamic Vinegar of Modena",
        "description": "Sweet, dark Italian balsamic vinegar.",
        "price": 2.80,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Red Wine Vinegar",
        "description": "Tangy red wine vinegar for salad dressings.",
        "price": 1.40,
    },
    # --- Bakery & Bread ---
    {
        "category": "Bakery & Bread",
        "name": "White Sourdough Loaf",
        "description": "Artisanal crusty white sourdough loaf, sliced.",
        "price": 2.30,
    },
    {
        "category": "Bakery & Bread",
        "name": "Wholemeal Sliced Bread",
        "description": "Soft, high-fiber wholemeal bread loaf.",
        "price": 1.20,
    },
    {
        "category": "Bakery & Bread",
        "name": "Brioche Burger Buns",
        "description": "Sweet, buttery sliced brioche buns, pack of 4.",
        "price": 1.50,
    },
    {
        "category": "Bakery & Bread",
        "name": "Pita Breads",
        "description": "White pocket pita breads, perfect for stuffing, pack of 6.",
        "price": 0.90,
    },
    {
        "category": "Bakery & Bread",
        "name": "Tortilla Wraps",
        "description": "Soft white flour tortillas, great for fajitas, pack of 8.",
        "price": 1.10,
    },
    {
        "category": "Bakery & Bread",
        "name": "Naan Breads",
        "description": "Flame-baked garlic and coriander naans, pack of 2.",
        "price": 1.40,
    },
    {
        "category": "Bakery & Bread",
        "name": "Croissants",
        "description": "All-butter flaky French croissants, pack of 4.",
        "price": 2.00,
    },
    {
        "category": "Bakery & Bread",
        "name": "Baguette",
        "description": "Freshly baked crusty white French baguette.",
        "price": 0.85,
    },
    {
        "category": "Bakery & Bread",
        "name": "English Muffins",
        "description": "Toasting muffins, perfect for breakfast egg muffins, pack of 4.",
        "price": 1.00,
    },
    {
        "category": "Bakery & Bread",
        "name": "Crumpets",
        "description": "Fluffy, spongy crumpets with butter-absorbing holes, pack of 6.",
        "price": 0.95,
    },
    # --- Baking & Cooking Extras ---
    {
        "category": "Baking & Cooking Extras",
        "name": "Baking Powder",
        "description": "Raising agent for baking cakes and biscuits.",
        "price": 1.20,
    },
    {
        "category": "Baking & Cooking Extras",
        "name": "Bicarbonate of Soda",
        "description": "Pure baking soda for cooking and cleaning.",
        "price": 1.10,
    },
    {
        "category": "Baking & Cooking Extras",
        "name": "Cornstarch (Cornflour)",
        "description": "Pure white starch, perfect for thickening sauces and marinades.",
        "price": 1.00,
    },
    {
        "category": "Baking & Cooking Extras",
        "name": "Cocoa Powder",
        "description": "Unsweetened cocoa powder for rich chocolate baking.",
        "price": 1.80,
    },
    {
        "category": "Baking & Cooking Extras",
        "name": "Vanilla Extract",
        "description": "Natural vanilla bean extract flavoring.",
        "price": 3.50,
    },
    {
        "category": "Baking & Cooking Extras",
        "name": "Active Dry Yeast",
        "description": "Fast action dry yeast sachets for bread baking.",
        "price": 1.25,
    },
    {
        "category": "Baking & Cooking Extras",
        "name": "Coconut Milk (Canned)",
        "description": "Rich canned coconut milk, ideal for Thai and Indian curries.",
        "price": 1.10,
    },
    {
        "category": "Baking & Cooking Extras",
        "name": "Chicken Stock Pots",
        "description": "Concentrated chicken stock pots, pack of 4.",
        "price": 1.65,
    },
    {
        "category": "Baking & Cooking Extras",
        "name": "Beef Stock Cubes",
        "description": "Dehydrated beef stock cubes, pack of 8.",
        "price": 1.20,
    },
    {
        "category": "Baking & Cooking Extras",
        "name": "Vegetable Stock Pots",
        "description": "Concentrated vegetable stock pots, pack of 4.",
        "price": 1.65,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Sichuan Chili Oil",
        "description": "Spicy Sichuan chili oil with flakes, perfect for Mapo Tofu and noodles.",
        "price": 2.20,
    },
    {
        "category": "Herbs & Spices",
        "name": "White Pepper Powder",
        "description": "Ground white pepper, essential for hot and sour soup.",
        "price": 1.20,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Douchi (Fermented Black Beans)",
        "description": "Traditional Chinese fermented black beans, adds savory depth.",
        "price": 1.80,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Pixian Doubanjiang (Chili Bean Paste)",
        "description": "Authentic fermented broad bean paste from Pixian, essential for Mapo Tofu.",
        "price": 2.60,
    },
    {
        "category": "Pantry & Grains",
        "name": "Cooking Oil",
        "description": "Refined neutral oil for stir-frying and deep-frying.",
        "price": 2.20,
    },
    {
        "category": "Vegetables",
        "name": "Garlic Greens",
        "description": "Fresh garlic shoots, traditional garnish for Mapo Tofu.",
        "price": 1.50,
    },
    {
        "category": "Pantry & Grains",
        "name": "Roasted Peanuts",
        "description": "Salted roasted peanuts, traditional crunchy garnish for Kung Pao chicken.",
        "price": 1.20,
    },
    {
        "category": "Pantry & Grains",
        "name": "Peanut Oil",
        "description": "High smoke point peanut oil for stir-frying and deep-frying.",
        "price": 2.80,
    },
    {
        "category": "Pantry & Grains",
        "name": "Wheat Noodles",
        "description": "Traditional Chinese wheat noodles for stir-fry or soup.",
        "price": 1.20,
    },
    {
        "category": "Pantry & Grains",
        "name": "Rock Sugar",
        "description": "Traditional Chinese rock sugar for sweetening and glazing braised pork.",
        "price": 1.50,
    },
    {
        "category": "Herbs & Spices",
        "name": "Dried Red Chilies",
        "description": "Whole dried Sichuan red chilies, essential for Kung Pao and Mapo.",
        "price": 1.30,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Chinese Sesame Paste",
        "description": "Rich roasted sesame paste, essential for Dan Dan noodles and hot pot dipping sauces.",
        "price": 2.20,
    },
    {
        "category": "Condiments & Sauces",
        "name": "Sui Mi Ya Cai (Sichuan Mustard Greens)",
        "description": "Traditional minced and pickled Sichuan mustard greens, essential topping for Dan Dan noodles.",
        "price": 2.50,
    },
    {
        "category": "Pantry & Grains",
        "name": "Dried Shiitake Mushrooms",
        "description": "Dried shiitake mushrooms, adds rich umami broth flavor when rehydrated.",
        "price": 2.50,
    },
    {
        "category": "Herbs & Spices",
        "name": "Toasted Sesame Seeds",
        "description": "Toasted white sesame seeds, perfect garnish for Chinese dishes.",
        "price": 1.10,
    },
    {
        "category": "Pantry & Grains",
        "name": "Dried Goji Berries",
        "description": "Dried goji berries (Gouqi), traditional Chinese herb used in soups and steaming.",
        "price": 1.80,
    },
    {
        "category": "Pantry & Grains",
        "name": "Dried Cordyceps Flowers",
        "description": "Dried cordyceps flower mushrooms (Chongcao Hua), rich golden color and earthy flavor.",
        "price": 3.00,
    },
]


def generate_embedding(client, text):
    """Call Google GenAI SDK to generate content embedding."""
    try:
        response = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
        )
        return response.embeddings[0].values
    except Exception as e:
        print(f"Error generating embedding: {e}")
        raise e


def seed_database():
    print(f"Starting database seeding. Total items: {len(INGREDIENTS_DATA)}")

    client = genai.Client(
        vertexai=True, project="rocketech-de-pgcp-sandbox", location="us-central1"
    )
    db = firestore.Client(project="rocketech-de-pgcp-sandbox", database="agents-shared")

    collection_ref = db.collection("ingredients")

    success_count = 0
    for i, item in enumerate(INGREDIENTS_DATA):
        name = item["name"]
        category = item["category"]
        description = item["description"]
        price = item["price"]

        # Format a descriptive text payload for embedding
        text_payload = (
            f"Name: {name}. Category: {category}. Description: {description}."
        )

        print(
            f"[{i + 1}/{len(INGREDIENTS_DATA)}] Embedding and seeding: {name} ({category})"
        )

        try:
            embedding = generate_embedding(client, text_payload)

            # Firestore expects the Vector type for vector indexing/search
            doc_data = {
                "name": name,
                "category": category,
                "description": description,
                "price": price,
                "embedding": Vector(embedding),
            }

            # Use name normalized as document ID
            doc_id = (
                name.lower()
                .replace(" ", "_")
                .replace("(", "")
                .replace(")", "")
                .replace("/", "_")
            )
            collection_ref.document(doc_id).set(doc_data)
            success_count += 1

            # Add minor sleep to avoid aggressive rate limits if any
            time.sleep(0.1)

        except Exception as e:
            print(f"Failed to seed {name}: {e}")

    print(
        f"Seeding completed successfully! Seeded {success_count}/{len(INGREDIENTS_DATA)} documents."
    )

    print("\n" + "=" * 80)
    print("CRITICAL ACTION REQUIRED:")
    print("To use Vector Search, you must create a Firestore composite vector index.")
    print("Run a search query to obtain the creation link, or build it manually:")
    print("Collection: ingredients")
    print("Field: embedding (Vector, Dimension: 768 for gemini-embedding-2)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    seed_database()
