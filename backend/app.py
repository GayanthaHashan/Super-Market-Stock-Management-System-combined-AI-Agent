import datetime
import os
import random
import re
import sys
from xml.sax.saxutils import escape

import certifi
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from pymongo import MongoClient

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# SETTINGS

load_dotenv()         # reads the .env file (MONGO_URI, ...)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "supermarket_db")
MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
CURRENCY = os.getenv("CURRENCY", "$")
PORT = int(os.getenv("PORT", "5000"))

HISTORY_DAYS = 60          # how many days of sales history we create
MAX_STEPS = 12             # guard: the agent can never loop forever



#  DATABASE (MongoDB)
# Two collections:
#   products -> one document per product (the product profile + stock)
#   sales    -> one document per product per day (units sold, revenue, profit)

db = None    # filled in by connect_db()

# The 50 dummy products. - (name, brand, category, price, cost price, unit, origin, shelf life in days, average units sold per day, storage, description)

SAMPLE_PRODUCTS = [

    ("Bananas", "FreshPick", "Fruits & Vegetables", 1.20, 0.80, "1 kg", "Ecuador", 6, 40,
     "Room temperature", "Sweet ripe bananas, a good source of potassium and quick energy."),
    ("Red Apples", "Orchard Gold", "Fruits & Vegetables", 2.80, 1.90, "1 kg", "New Zealand", 30, 28,
     "Refrigerate", "Crisp and juicy red apples, great as a snack or in desserts."),
    ("Tomatoes", "Green Valley", "Fruits & Vegetables", 2.20, 1.40, "1 kg", "Local farms", 7, 30,
     "Cool place, away from sunlight", "Fresh vine tomatoes for salads, curries and sauces."),
    ("Potatoes", "Green Valley", "Fruits & Vegetables", 1.60, 1.00, "2 kg", "Local farms", 30, 26,
     "Cool, dark and dry place", "All-purpose potatoes suitable for boiling, frying and baking."),
    ("Red Onions", "Green Valley", "Fruits & Vegetables", 1.40, 0.90, "1 kg", "India", 45, 24,
     "Cool and dry place", "Medium red onions with a strong flavour for everyday cooking."),
    ("Carrots", "FreshPick", "Fruits & Vegetables", 1.30, 0.80, "500 g", "Local farms", 14, 18,
     "Refrigerate", "Crunchy orange carrots rich in vitamin A."),

    ("Fresh Milk", "Meadow Fresh", "Dairy & Eggs", 1.50, 1.05, "1 L", "Local dairy", 7, 45,
     "Refrigerate at 1-4 C", "Full cream pasteurised fresh milk."),
    ("Cheddar Cheese", "Meadow Fresh", "Dairy & Eggs", 4.20, 3.00, "200 g", "Ireland", 90, 14,
     "Refrigerate at 1-4 C", "Mature cheddar block with a rich and creamy taste."),
    ("Greek Yogurt", "Hellenic Farms", "Dairy & Eggs", 3.10, 2.20, "500 g", "Greece", 21, 16,
     "Refrigerate at 1-4 C", "Thick and creamy natural yogurt with high protein."),
    ("Salted Butter", "Meadow Fresh", "Dairy & Eggs", 3.60, 2.70, "250 g", "New Zealand", 120, 12,
     "Refrigerate at 1-4 C", "Smooth salted butter for spreading and cooking."),
    ("Eggs Dozen", "Sunny Farm", "Dairy & Eggs", 3.30, 2.40, "12 pack", "Local farms", 28, 35,
     "Cool place or refrigerate", "Farm fresh medium-size eggs."),
    ("Cooking Cream", "Meadow Fresh", "Dairy & Eggs", 2.40, 1.70, "250 ml", "Local dairy", 60, 8,
     "Refrigerate after opening", "UHT cooking cream for sauces, soups and desserts."),

    ("White Bread", "Golden Crust", "Bakery", 1.80, 1.10, "600 g loaf", "Baked in store", 4, 38,
     "Room temperature, dry place", "Soft sliced white bread baked fresh every morning."),
    ("Whole Wheat Bread", "Golden Crust", "Bakery", 2.20, 1.40, "600 g loaf", "Baked in store", 5, 20,
     "Room temperature, dry place", "High fibre whole wheat sandwich loaf."),
    ("Butter Croissants", "Golden Crust", "Bakery", 3.50, 2.30, "4 pack", "Baked in store", 3, 14,
     "Room temperature", "Flaky buttery croissants, best eaten fresh."),
    ("Burger Buns", "Golden Crust", "Bakery", 2.10, 1.30, "6 pack", "Baked in store", 5, 12,
     "Room temperature", "Soft sesame burger buns."),
    ("Chocolate Muffins", "Golden Crust", "Bakery", 3.20, 2.10, "4 pack", "Baked in store", 5, 10,
     "Room temperature", "Moist muffins filled with chocolate chips."),

    ("Chicken Breast", "FarmFresh", "Meat & Seafood", 6.50, 4.80, "500 g", "Local farms", 4, 22,
     "Refrigerate at 0-4 C", "Skinless boneless chicken breast fillets."),
    ("Minced Beef", "FarmFresh", "Meat & Seafood", 7.80, 5.90, "500 g", "Australia", 3, 14,
     "Refrigerate at 0-4 C", "Lean minced beef for burgers, pasta sauces and curries."),
    ("Salmon Fillet", "Ocean Catch", "Meat & Seafood", 9.90, 7.40, "300 g", "Norway", 3, 8,
     "Refrigerate at 0-2 C", "Fresh Atlantic salmon fillet rich in omega-3."),
    ("Frozen Prawns", "Ocean Catch", "Meat & Seafood", 8.50, 6.20, "400 g", "Vietnam", 365, 7,
     "Keep frozen at -18 C", "Peeled and deveined frozen prawns."),
    ("Beef Sausages", "FarmFresh", "Meat & Seafood", 5.20, 3.70, "400 g", "Local farms", 14, 12,
     "Refrigerate at 0-4 C", "Seasoned beef sausages for grilling or frying."),

    ("Cola", "FizzUp", "Beverages", 1.90, 1.20, "1.5 L", "Local bottler", 180, 42,
     "Cool place", "Classic sparkling cola drink."),
    ("Orange Juice", "SunBurst", "Beverages", 2.90, 2.00, "1 L", "Brazil", 14, 20,
     "Refrigerate after opening", "100% pressed orange juice with no added sugar."),
    ("Mineral Water", "Pure Spring", "Beverages", 0.90, 0.50, "1.5 L", "Local spring", 540, 55,
     "Cool place", "Natural still mineral water."),
    ("Green Tea Bags", "Leaf & Co", "Beverages", 3.40, 2.30, "25 bags", "China", 540, 11,
     "Dry place, airtight", "Light and refreshing green tea bags."),
    ("Instant Coffee", "BeanHouse", "Beverages", 5.90, 4.30, "100 g", "Colombia", 540, 14,
     "Dry place, airtight", "Rich instant coffee granules."),
    ("Energy Drink", "Volt", "Beverages", 1.80, 1.10, "250 ml", "Austria", 365, 25,
     "Cool place", "Caffeinated energy drink with B vitamins."),
    ("Ginger Ale", "FizzUp", "Beverages", 1.70, 1.05, "1 L", "Local bottler", 180, 13,
     "Cool place", "Mild ginger flavoured sparkling drink."),

    ("Potato Chips", "Crispy", "Snacks", 1.90, 1.20, "150 g", "Local factory", 120, 36,
     "Cool and dry place", "Lightly salted crunchy potato chips."),
    ("Milk Chocolate Bar", "ChocoJoy", "Snacks", 1.50, 0.95, "100 g", "Switzerland", 270, 33,
     "Below 25 C", "Smooth milk chocolate bar."),
    ("Salted Peanuts", "Nutty", "Snacks", 2.30, 1.50, "200 g", "India", 240, 15,
     "Cool and dry place", "Roasted and lightly salted peanuts."),
    ("Butter Cookies", "Baker's Lane", "Snacks", 3.40, 2.30, "300 g", "Denmark", 180, 13,
     "Cool and dry place", "Crispy butter cookies in a tin."),
    ("Cheese Crackers", "Crunchy", "Snacks", 2.20, 1.40, "180 g", "Local factory", 150, 17,
     "Cool and dry place", "Baked crackers with real cheese flavour."),
    ("Gummy Bears", "SweetBear", "Snacks", 1.60, 0.95, "150 g", "Germany", 300, 19,
     "Below 25 C", "Soft fruity gummy bear sweets."),
    ("Granola Bars", "NutriBar", "Snacks", 3.80, 2.60, "6 pack", "USA", 240, 11,
     "Cool and dry place", "Oat and honey granola bars with nuts."),

    ("Basmati Rice", "Royal Grain", "Pantry", 11.50, 8.80, "5 kg", "India", 720, 14,
     "Cool and dry place", "Long grain aged basmati rice."),
    ("Spaghetti", "Pasta Bella", "Pantry", 1.70, 1.05, "500 g", "Italy", 720, 24,
     "Cool and dry place", "Durum wheat spaghetti."),
    ("Sunflower Oil", "Golden Drop", "Pantry", 4.60, 3.50, "1 L", "Ukraine", 540, 18,
     "Cool place, away from sunlight", "Refined sunflower cooking oil."),
    ("White Sugar", "SweetCane", "Pantry", 1.40, 1.00, "1 kg", "Local mill", 720, 27,
     "Dry place", "Fine granulated white sugar."),
    ("Wheat Flour", "MillStone", "Pantry", 1.60, 1.10, "1 kg", "Local mill", 365, 21,
     "Cool and dry place", "All-purpose wheat flour for baking and cooking."),
    ("Tomato Ketchup", "RedPot", "Pantry", 2.50, 1.60, "500 g", "Local factory", 365, 15,
     "Cool place, refrigerate after opening", "Sweet and tangy tomato ketchup."),
    ("Corn Flakes", "MorningCrunch", "Pantry", 4.20, 3.00, "500 g", "UK", 365, 18,
     "Cool and dry place", "Crispy toasted corn flakes breakfast cereal."),
    ("Canned Tuna", "Ocean Catch", "Pantry", 2.30, 1.60, "185 g", "Thailand", 1095, 20,
     "Cool and dry place", "Tuna chunks in sunflower oil."),

    ("Dishwashing Liquid", "SparkleClean", "Household & Personal Care", 2.80, 1.80, "750 ml", "Local factory", 730, 12,
     "Room temperature", "Lemon scented liquid that cuts through grease."),
    ("Laundry Detergent", "FreshWash", "Household & Personal Care", 8.90, 6.50, "2 kg", "Malaysia", 730, 9,
     "Dry place", "Powder detergent for machine and hand wash."),
    ("Toilet Paper", "SoftTouch", "Household & Personal Care", 6.80, 4.90, "9 rolls", "Local factory", 1825, 17,
     "Dry place", "Soft 3-ply toilet paper rolls."),
    ("Shampoo", "SilkyHair", "Household & Personal Care", 5.60, 3.90, "400 ml", "Local factory", 1095, 10,
     "Room temperature", "Daily care shampoo for all hair types."),
    ("Toothpaste", "BrightSmile", "Household & Personal Care", 2.90, 1.80, "150 g", "Local factory", 1095, 16,
     "Room temperature", "Fluoride toothpaste for cavity protection."),
    ("Hand Soap", "PureHands", "Household & Personal Care", 2.40, 1.50, "250 ml", "Local factory", 730, 13,
     "Room temperature", "Gentle antibacterial liquid hand soap."),
]

# Supplier of each category
CATEGORY_SUPPLIERS = {
    "Fruits & Vegetables": "Green Valley Farms",
    "Dairy & Eggs": "Meadow Fresh Dairy",
    "Bakery": "Golden Crust Bakery",
    "Meat & Seafood": "Ocean & Farm Foods",
    "Beverages": "Fizz & Fresh Distributors",
    "Snacks": "Snack World Ltd",
    "Pantry": "Harvest Wholesale",
    "Household & Personal Care": "HomeCare Supplies",
}

# Products that start with no stock or low stock (so the system has some alerts)
OUT_OF_STOCK_ITEMS = ["Salmon Fillet", "Energy Drink", "Butter Croissants", "Granola Bars"]
LOW_STOCK_ITEMS = ["Fresh Milk", "White Bread", "Cheddar Cheese", "Potato Chips",
                   "Basmati Rice", "Hand Soap"]


def connect_db() -> None:
    #Connect to MongoDB and create the indexes.
    global db
    if MONGO_URI.startswith("mongodb+srv"):
        # Atlas (cloud) connection. certifi gives Python the SSL certificates.
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000,
                             tlsCAFile=certifi.where())
    else:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)

    client.admin.command("ping")    # fails here if the link is wrong
    db = client[DB_NAME]
    db.products.create_index("sku", unique=True)
    db.sales.create_index([("sku", 1), ("date", 1)])
    print(f"Connected to MongoDB database '{DB_NAME}'")


def make_daily_units(average: float, date: datetime.date) -> int:
    #Make a believable number of units sold for one day (weekends sell more).
    factor = 1.0
    if date.weekday() == 4:                      # Friday
        factor = 1.15
    elif date.weekday() >= 5:                    # Saturday, Sunday
        factor = 1.35
    return int(round(average * factor * random.uniform(0.6, 1.4)))


def make_sale_doc(product: dict, date: str, units: int) -> dict:
    #Build one sales document (one product, one day).
    return {
        "sku": product["sku"],
        "product_name": product["name"],
        "category": product["category"],
        "date": date,
        "units_sold": units,
        "revenue": round(units * product["price"], 2),
        "profit": round(units * (product["price"] - product["cost_price"]), 2),
    }


def seed_database(force: bool = False) -> None:
    #Create the 50 products and 60 days of sales if the database is empty.
    if force:
        db.products.delete_many({})
        db.sales.delete_many({})
        print("Old data deleted.")

    if db.products.count_documents({}) > 0:
        print("Database already has products - skipping the seed step.")
        return

    random.seed(42)                 # same data every time we seed
    today = datetime.date.today()
    products = []
    sales = []
    number = 1

    for item in SAMPLE_PRODUCTS:
        (name, brand, category, price, cost, unit, origin,
         shelf_days, daily, storage, description) = item

        reorder_level = max(5, daily * 2)
        if name in OUT_OF_STOCK_ITEMS:
            stock = 0
        elif name in LOW_STOCK_ITEMS:
            stock = random.randint(1, reorder_level)
        else:
            stock = daily * random.randint(4, 10)

        product = {
            "sku": f"P{number:03d}",
            "name": name,
            "brand": brand,
            "category": category,
            "price": price,
            "cost_price": cost,
            "unit": unit,
            "stock": stock,
            "reorder_level": reorder_level,
            "supplier": CATEGORY_SUPPLIERS[category],
            "origin": origin,
            "storage": storage,
            "shelf_life_days": shelf_days,
            "barcode": str(random.randint(10 ** 12, 10 ** 13 - 1)),
            "description": description,
            "date_added": today.isoformat(),
            "last_restocked": (today - datetime.timedelta(days=random.randint(1, 10))).isoformat(),
        }
        products.append(product)

        # sales history for this product
        for days_ago in range(HISTORY_DAYS - 1, -1, -1):
            date = today - datetime.timedelta(days=days_ago)
            units = make_daily_units(daily, date)
            if name in OUT_OF_STOCK_ITEMS and days_ago < 2:
                units = 0                        # nothing sold, the shelf is empty
            if units > 0:
                sales.append(make_sale_doc(product, date.isoformat(), units))

        number += 1

    db.products.insert_many(products)
    db.sales.insert_many(sales)
    print(f"Seeded {len(products)} products and {len(sales)} daily sales records.")


def top_up_sales() -> None:
    #If the app was not started for some days, create sales for the missing days.
    last = db.sales.find_one(sort=[("date", -1)])
    if last is None:
        return

    today = datetime.date.today()
    last_date = datetime.date.fromisoformat(last["date"])
    if last_date >= today:
        return

    # average units per day of each product in the 14 days before the gap
    start = (last_date - datetime.timedelta(days=13)).isoformat()
    totals = {}
    for s in db.sales.find({"date": {"$gte": start}}):
        totals[s["sku"]] = totals.get(s["sku"], 0) + s["units_sold"]

    day = last_date + datetime.timedelta(days=1)
    if (today - day).days > HISTORY_DAYS:
        day = today - datetime.timedelta(days=HISTORY_DAYS - 1)

    new_sales = []
    products = list(db.products.find({}, {"_id": 0}))
    while day <= today:
        for product in products:
            if product["stock"] <= 0:
                continue                         # nothing to sell
            average = totals.get(product["sku"], 0) / 14
            units = make_daily_units(average, day)
            if units > 0:
                new_sales.append(make_sale_doc(product, day.isoformat(), units))
        day += datetime.timedelta(days=1)

    if new_sales:
        db.sales.insert_many(new_sales)
        print(f"Added {len(new_sales)} sales records for the days since the last run.")


# Helper fucntions

STOP_WORDS = {"the", "a", "an", "is", "are", "do", "we", "have", "any", "of", "and",
              "me", "tell", "about", "show", "give", "details", "detail", "info",
              "stock", "price", "much", "how", "many", "what", "for", "in", "on"}


def money(amount: float) -> str:
    #Format a number as money, e.g. $1,250.50
    return f"{CURRENCY}{amount:,.2f}"


def get_status(stock: int, reorder_level: int) -> str:
    #Stock status of a product.
    if stock <= 0:
        return "Out of Stock"
    if stock <= reorder_level:
        return "Low Stock"
    return "In Stock"


def add_status(product: dict) -> dict:
    #Return a copy of the product with the 'status' field added.
    result = dict(product)
    result.pop("_id", None)
    result["status"] = get_status(result["stock"], result["reorder_level"])
    return result


def get_date_range(period: str):
    #Turn 'daily' / 'weekly' / 'monthly' into (start_date, end_date, label).
    p = str(period).strip().lower()
    today = datetime.date.today()

    if p in ("today", "daily", "day", "1"):
        days = 1
        label = "Daily (today)"
    elif p in ("week", "weekly", "7"):
        days = 7
        label = "Weekly (last 7 days)"
    elif p in ("month", "monthly", "30"):
        days = 30
        label = "Monthly (last 30 days)"
    else:
        raise ValueError(f"unknown period '{period}'. Use 'daily', 'weekly' or 'monthly'.")

    start = today - datetime.timedelta(days=days - 1)
    return start.isoformat(), today.isoformat(), label


def list_dates(start: str, end: str) -> list:
    #All dates from start to end (inclusive) as 'YYYY-MM-DD' strings.
    day = datetime.date.fromisoformat(start)
    last = datetime.date.fromisoformat(end)
    dates = []
    while day <= last:
        dates.append(day.isoformat())
        day += datetime.timedelta(days=1)
    return dates


def get_sales(start: str, end: str, sku: str = None) -> list:
    #Read the sales documents between two dates (optionally for one product).
    query = {"date": {"$gte": start, "$lte": end}}
    if sku:
        query["sku"] = sku
    return list(db.sales.find(query, {"_id": 0}))


def sales_totals(sales: list):
    #Add up units, revenue and profit of a list of sales documents.
    units = 0
    revenue = 0.0
    profit = 0.0
    for s in sales:
        units += s["units_sold"]
        revenue += s["revenue"]
        profit += s["profit"]
    return units, round(revenue, 2), round(profit, 2)


def units_by_date(sales: list) -> dict:
    #Units sold on each date.
    result = {}
    for s in sales:
        result[s["date"]] = result.get(s["date"], 0) + s["units_sold"]
    return result


def revenue_by_date(sales: list) -> dict:
    # Revenue on each date.
    result = {}
    for s in sales:
        result[s["date"]] = result.get(s["date"], 0) + s["revenue"]
    return result


def trend_text(first_half: int, second_half: int) -> str:
    #Compare the first half of a period with the second half.
    if first_half == 0 and second_half == 0:
        return "no sales"
    if first_half == 0:
        return "rising (sales only in the recent days)"
    change = (second_half - first_half) / first_half * 100
    if change > 10:
        return f"rising (+{change:.0f}% in the second half)"
    if change < -10:
        return f"falling ({change:.0f}% in the second half)"
    return "steady"


def search_regex(pattern: str, limit: int) -> list:
    #Search name and brand first. Only if nothing is found, search the category.
    query = {"$or": [
        {"name": {"$regex": pattern, "$options": "i"}},
        {"brand": {"$regex": pattern, "$options": "i"}},
    ]}
    found = list(db.products.find(query, {"_id": 0}).limit(limit))
    if len(found) > 0:
        return found

    query = {"category": {"$regex": pattern, "$options": "i"}}
    return list(db.products.find(query, {"_id": 0}).limit(limit))


def find_products(text: str, limit: int = 5) -> list:
    """
    Keyword retrieval from the database (this is the 'R' of our RAG).
    1) try the whole text   2) if nothing is found, try each word on its own.
    """
    text = text.strip()
    if text == "":
        return []

    # exact product name first
    exact = db.products.find_one(
        {"name": {"$regex": f"^{re.escape(text)}$", "$options": "i"}}, {"_id": 0})
    if exact:
        return [exact]

    found = search_regex(re.escape(text), limit)
    if len(found) > 0:
        return found

    for word in text.lower().split():
        word = word.strip("?.,!'\"")
        if len(word) < 3 or word in STOP_WORDS:
            continue
        if word.endswith("s"):
            word = word[:-1]                     # "apples" -> "apple"
        found = search_regex(re.escape(word), limit)
        if len(found) > 0:
            return found
    return []


def format_product(p: dict) -> str:
    #Turn a product document into readable text for the LLM.
    product = add_status(p)
    margin = (product["price"] - product["cost_price"]) / product["price"] * 100
    if product["stock"] > 0:
        available = "Available now"
    else:
        available = "NOT available right now"

    lines = [
        f"Product: {product['name']} (SKU {product['sku']})",
        f"Brand: {product['brand']}",
        f"Category: {product['category']}",
        f"Description: {product['description']}",
        f"Selling price: {money(product['price'])} per {product['unit']}",
        f"Cost price: {money(product['cost_price'])} (profit margin {margin:.0f}%)",
        f"Stock: {product['stock']} units -> {product['status']} ({available})",
        f"Reorder level: {product['reorder_level']} units",
        f"Supplier: {product['supplier']}",
        f"Origin: {product['origin']}",
        f"Storage: {product['storage']}",
        f"Shelf life: {product['shelf_life_days']} days",
        f"Barcode: {product['barcode']}",
        f"Last restocked: {product['last_restocked']}",
    ]
    return "\n".join(lines)

#The LLM
# temperature=0 -> the same question gives the same answer
# num_ctx=8192  -> a bigger memory window, because tool results can be long

llm = ChatOllama(model=MODEL, temperature=0, num_ctx=8192)


#Agent tools

# product details tool
@tool
def get_product_details(product_name: str) -> str:
    """Get the full profile and current stock status of a product from the store database.
    Use this when the user asks about a product, for example 'tell me about milk',
    'do we have eggs?' or 'what is the price of cola?'.
    product_name is the product name or part of it."""
    try:
        if not product_name or product_name.strip() == "":
            return "error: please give a product name."

        found = find_products(product_name, limit=3)
        if len(found) == 0:
            return f"No product found matching '{product_name}'. Ask the user to check the spelling."

        text = f"Found {len(found)} matching product(s):\n\n"
        for p in found:
            text += format_product(p) + "\n\n"
        return text
    except Exception as e:
        return f"error: {e}"

# analyse one or more products
@tool
def analyze_products(product_names: str, days: int = 30) -> str:
    """Analyse the current stock and the sales performance of one or more products
    over the last N days (1 to 60, default 30). product_names is a comma separated
    list, for example 'milk, bread, eggs'. Use this when the user asks for an analysis,
    performance check or comparison of products."""
    try:
        if not product_names or product_names.strip() == "":
            return "error: please give at least one product name."
        if days < 1 or days > HISTORY_DAYS:
            return f"error: days must be between 1 and {HISTORY_DAYS}."

        end = datetime.date.today().isoformat()
        start = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
        dates = list_dates(start, end)
        middle = len(dates) // 2

        names = product_names.replace(" and ", ",").split(",")
        text = f"PRODUCT ANALYSIS for the last {days} days ({start} to {end})\n\n"

        for name in names:
            if name.strip() == "":
                continue
            found = find_products(name, limit=1)
            if len(found) == 0:
                text += f"'{name.strip()}': product not found.\n\n"
                continue

            p = add_status(found[0])
            sales = get_sales(start, end, p["sku"])
            units, revenue, profit = sales_totals(sales)
            per_day = units_by_date(sales)

            first_half = 0
            second_half = 0
            best_date = None
            best_units = 0
            for i, date in enumerate(dates):
                u = per_day.get(date, 0)
                if i < middle:
                    first_half += u
                else:
                    second_half += u
                if u > best_units:
                    best_units = u
                    best_date = date

            average = units / days
            if average > 0:
                cover = f"{p['stock'] / average:.1f} days of stock left at this speed"
            else:
                cover = "no sales, so stock cover cannot be calculated"

            text += f"{p['name']} ({p['sku']}, {p['category']})\n"
            text += f"- Current stock: {p['stock']} units ({p['status']}), reorder level {p['reorder_level']}\n"
            text += f"- Price: {money(p['price'])}, profit margin {(p['price'] - p['cost_price']) / p['price'] * 100:.0f}%\n"
            text += f"- Units sold: {units}, revenue {money(revenue)}, profit {money(profit)}\n"
            text += f"- Average per day: {average:.1f} units\n"
            if best_date:
                text += f"- Best day: {best_date} ({best_units} units)\n"
            text += f"- Trend: {trend_text(first_half, second_half)}\n"
            text += f"- Stock cover: {cover}\n\n"

        return text
    except Exception as e:
        return f"error: {e}"


# monthly sales summary of ONE product tool
@tool
def monthly_sales_summary(product_name: str) -> str:
    """Calculate the full sales of ONE product for the last 30 days and show how the
    product performed in the market on each day of the month (day-by-day table, best
    and worst days, weekly totals, ranking among all products).
    Use this when the user asks for the monthly sales or monthly performance of a product."""
    try:
        if not product_name or product_name.strip() == "":
            return "error: please give a product name."
        found = find_products(product_name, limit=1)
        if len(found) == 0:
            return f"No product found matching '{product_name}'."

        p = add_status(found[0])
        start, end, label = get_date_range("monthly")
        dates = list_dates(start, end)

        # sales of this product
        sales = get_sales(start, end, p["sku"])
        units, revenue, profit = sales_totals(sales)
        per_day = units_by_date(sales)
        per_day_money = revenue_by_date(sales)

        # best day, slowest day, weekday vs weekend
        best_date = dates[0]
        worst_date = dates[0]
        weekday_total = 0
        weekday_count = 0
        weekend_total = 0
        weekend_count = 0
        for date in dates:
            u = per_day.get(date, 0)
            if u > per_day.get(best_date, 0):
                best_date = date
            if u < per_day.get(worst_date, 0):
                worst_date = date
            if datetime.date.fromisoformat(date).weekday() >= 5:
                weekend_total += u
                weekend_count += 1
            else:
                weekday_total += u
                weekday_count += 1

        # market position: compare with all the other products
        all_sales = get_sales(start, end)
        totals = {}
        category_totals = {}
        for s in all_sales:
            totals[s["sku"]] = totals.get(s["sku"], 0) + s["units_sold"]
        ranking = sorted(totals.values(), reverse=True)
        rank = ranking.index(units) + 1 if units in ranking else len(ranking) + 1

        same_category = list(db.products.find({"category": p["category"]}, {"_id": 0}))
        category_units = 0
        for other in same_category:
            category_units += totals.get(other["sku"], 0)
        category_average = category_units / len(same_category) if same_category else 0
        if category_average > 0:
            difference = (units - category_average) / category_average * 100
            position = f"{abs(difference):.0f}% {'above' if difference >= 0 else 'below'} the category average"
        else:
            position = "no category data"

        # build the text
        text = f"MONTHLY SALES SUMMARY: {p['name']} ({p['sku']})\n"
        text += f"Period: {start} to {end} ({len(dates)} days)\n"
        text += f"Total units sold: {units}\n"
        text += f"Total revenue: {money(revenue)}\n"
        text += f"Total profit: {money(profit)}\n"
        text += f"Average per day: {units / len(dates):.1f} units\n"
        text += f"Best day: {best_date} ({per_day.get(best_date, 0)} units)\n"
        text += f"Slowest day: {worst_date} ({per_day.get(worst_date, 0)} units)\n"
        if weekday_count > 0 and weekend_count > 0:
            text += (f"Weekday average: {weekday_total / weekday_count:.1f} units, "
                     f"weekend average: {weekend_total / weekend_count:.1f} units\n")
        text += (f"Market position: rank {rank} of {len(ranking)} selling products by units, "
                 f"{position} ({p['category']}, average {category_average:.0f} units per product)\n")
        text += f"Current stock: {p['stock']} units ({p['status']})\n\n"

        text += "Weekly totals:\n"
        week_number = 1
        for i in range(0, len(dates), 7):
            chunk = dates[i:i + 7]
            week_units = 0
            week_money = 0.0
            for date in chunk:
                week_units += per_day.get(date, 0)
                week_money += per_day_money.get(date, 0)
            text += f"- Week {week_number} ({chunk[0]} to {chunk[-1]}): {week_units} units, {money(week_money)}\n"
            week_number += 1

        text += "\nDay-by-day sales:\n"
        for date in dates:
            day_name = datetime.date.fromisoformat(date).strftime("%a")
            text += f"{date} ({day_name}): {per_day.get(date, 0)} units, {money(per_day_money.get(date, 0))}\n"
        return text
    except Exception as e:
        return f"error: {e}"


# most sold items tool
@tool
def top_selling_items(period: str = "monthly", limit: int = 5) -> str:
    """Find the most sold items in the store for a period: 'daily', 'weekly' or 'monthly'.
    limit is how many top items to list (1 to 20). Also shows the slowest items and the
    sales of each category. Use this when the user asks for best sellers, most sold
    items or top products."""
    try:
        if limit < 1 or limit > 20:
            return "error: limit must be between 1 and 20."
        start, end, label = get_date_range(period)
        sales = get_sales(start, end)
        if len(sales) == 0:
            return f"No sales found for {label}."

        by_product = {}
        by_category = {}
        for s in sales:
            sku = s["sku"]
            if sku not in by_product:
                by_product[sku] = {"name": s["product_name"], "category": s["category"],
                                   "units": 0, "revenue": 0.0}
            by_product[sku]["units"] += s["units_sold"]
            by_product[sku]["revenue"] += s["revenue"]
            by_category[s["category"]] = by_category.get(s["category"], 0) + s["units_sold"]

        ranked = sorted(by_product.values(), key=lambda x: x["units"], reverse=True)
        total_units, total_revenue, total_profit = sales_totals(sales)

        text = f"TOP SELLING ITEMS - {label} ({start} to {end})\n"
        text += f"Store total: {total_units} units, revenue {money(total_revenue)}, profit {money(total_profit)}\n\n"

        text += f"Top {limit} by units sold:\n"
        for i, item in enumerate(ranked[:limit]):
            share = item["units"] / total_units * 100
            text += (f"{i + 1}. {item['name']} ({item['category']}): {item['units']} units, "
                     f"{money(item['revenue'])}, {share:.1f}% of all units\n")

        text += "\nSlowest 3 items:\n"
        for item in ranked[-3:]:
            text += f"- {item['name']}: {item['units']} units\n"

        text += "\nUnits sold by category:\n"
        for category, units in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
            text += f"- {category}: {units} units\n"
        return text
    except ValueError as e:
        return f"error: {e}"
    except Exception as e:
        return f"error: {e}"


# stock status list tool
@tool
def check_stock_status(status: str = "all") -> str:
    """List which products are available and which are not right now.
    status can be 'out of stock', 'low stock', 'in stock' or 'all'.
    Use this when the user asks what is out of stock, running low, or available."""
    try:
        s = status.strip().lower()
        if s not in ("out of stock", "low stock", "in stock", "all", "out", "low", "in"):
            return "error: status must be 'out of stock', 'low stock', 'in stock' or 'all'."

        products = list(db.products.find({}, {"_id": 0}).sort("name", 1))
        out_list = []
        low_list = []
        in_list = []
        for p in products:
            state = get_status(p["stock"], p["reorder_level"])
            if state == "Out of Stock":
                out_list.append(p)
            elif state == "Low Stock":
                low_list.append(p)
            else:
                in_list.append(p)

        text = (f"STOCK OVERVIEW: {len(products)} products | {len(in_list)} in stock | "
                f"{len(low_list)} low stock | {len(out_list)} out of stock\n\n")

        if s in ("out of stock", "out", "all"):
            text += "OUT OF STOCK (not available):\n"
            for p in out_list:
                text += f"- {p['name']} ({p['category']}), reorder level {p['reorder_level']}\n"
            text += "\n"
        if s in ("low stock", "low", "all"):
            text += "LOW STOCK (need restocking soon):\n"
            for p in low_list:
                text += f"- {p['name']}: {p['stock']} left, reorder level {p['reorder_level']}\n"
            text += "\n"
        if s in ("in stock", "in"):
            text += "IN STOCK (available):\n"
            for p in in_list:
                text += f"- {p['name']}: {p['stock']} units\n"
        return text
    except Exception as e:
        return f"error: {e}"

# sales report PDF tool
def gather_report_data(period: str) -> dict:
    """Collect everything the report needs from the database."""
    start, end, label = get_date_range(period)
    sales = get_sales(start, end)
    units, revenue, profit = sales_totals(sales)
    per_day = units_by_date(sales)
    per_day_money = revenue_by_date(sales)

    daily_rows = []
    for date in list_dates(start, end):
        daily_rows.append((date, per_day.get(date, 0), per_day_money.get(date, 0.0)))

    by_product = {}
    by_category = {}
    for s in sales:
        sku = s["sku"]
        if sku not in by_product:
            by_product[sku] = {"name": s["product_name"], "units": 0, "revenue": 0.0}
        by_product[sku]["units"] += s["units_sold"]
        by_product[sku]["revenue"] += s["revenue"]

        category = s["category"]
        if category not in by_category:
            by_category[category] = {"units": 0, "revenue": 0.0}
        by_category[category]["units"] += s["units_sold"]
        by_category[category]["revenue"] += s["revenue"]

    ranked = sorted(by_product.values(), key=lambda x: x["units"], reverse=True)

    out_list = []
    low_list = []
    for p in db.products.find({}, {"_id": 0}):
        state = get_status(p["stock"], p["reorder_level"])
        if state == "Out of Stock":
            out_list.append(p["name"])
        elif state == "Low Stock":
            low_list.append(f"{p['name']} ({p['stock']} left)")

    return {
        "period": period, "label": label, "start": start, "end": end,
        "units": units, "revenue": revenue, "profit": profit,
        "daily_rows": daily_rows, "top": ranked[:5], "bottom": ranked[-3:],
        "categories": by_category, "out_of_stock": out_list, "low_stock": low_list,
    }


def report_data_to_text(data: dict) -> str:
    """Turn the report data into text that we give to the LLM."""
    text = f"Report: {data['label']} from {data['start']} to {data['end']}\n"
    text += f"Total units sold: {data['units']}\n"
    text += f"Total revenue: {money(data['revenue'])}\n"
    text += f"Total profit: {money(data['profit'])}\n\n"

    text += "Daily sales (date, units, revenue):\n"
    for date, units, revenue in data["daily_rows"]:
        text += f"{date}: {units} units, {money(revenue)}\n"

    text += "\nTop 5 products by units:\n"
    for item in data["top"]:
        text += f"- {item['name']}: {item['units']} units, {money(item['revenue'])}\n"

    text += "\nSlowest products:\n"
    for item in data["bottom"]:
        text += f"- {item['name']}: {item['units']} units\n"

    text += "\nSales by category:\n"
    for category, values in data["categories"].items():
        text += f"- {category}: {values['units']} units, {money(values['revenue'])}\n"

    text += "\nOut of stock: " + (", ".join(data["out_of_stock"]) or "none") + "\n"
    text += "Low stock: " + (", ".join(data["low_stock"]) or "none") + "\n"
    return text


ANALYST_PROMPT = (
    "You are a retail sales analyst for a small supermarket. Use ONLY the data given "
    "by the user. Write the report analysis in plain text (no markdown symbols, no "
    "tables) with exactly these three parts:\n"
    "SUMMARY: 2-3 sentences about total sales and profit.\n"
    "KEY FINDINGS: 3-4 short lines starting with '- ' about best and slowest products, "
    "categories and daily pattern.\n"
    "RECOMMENDATIONS: 3 short lines starting with '- ' about restocking and promotions.\n"
    "Never invent numbers."
)


def write_ai_analysis(data: dict) -> str:
    """Ask the Ollama LLM to write the analysis text of the report."""
    try:
        reply = llm.invoke([
            ("system", ANALYST_PROMPT),
            ("user", report_data_to_text(data)),
        ])
        return reply.content
    except Exception as e:
        return (f"The AI analysis could not be created ({e}). "
                "The tables in this report still contain all the data.")


@tool
def create_sales_report_pdf(period: str = "weekly") -> str:
    """Create a downloadable PDF sales report for a period: 'daily', 'weekly' or 'monthly'.
    It collects the sales data from the database, writes an AI analysis and builds the PDF.
    Use this when the user asks for a sales report, a summary report or a PDF."""
    try:
        data = gather_report_data(period)
        if data["units"] == 0:
            return f"No sales found for {data['label']}, so no report was created."

        analysis = write_ai_analysis(data)
        filename = make_pdf(data, analysis)

        text = f"REPORT_FILE: {filename}\n"
        text += f"A PDF report was created for {data['label']} ({data['start']} to {data['end']}).\n"
        text += f"Total units: {data['units']}, revenue {money(data['revenue'])}, profit {money(data['profit'])}.\n"
        text += "Top product: " + data["top"][0]["name"] + f" ({data['top'][0]['units']} units).\n\n"
        text += "AI ANALYSIS IN THE REPORT:\n" + analysis
        return text
    except ValueError as e:
        return f"error: {e}"
    except Exception as e:
        return f"error: could not create the report ({e})"


TOOLS = [get_product_details, analyze_products, monthly_sales_summary,
         create_sales_report_pdf, top_selling_items, check_stock_status]


# The PDF Maker
ORANGE = colors.HexColor("#E8590C")
BROWN = colors.HexColor("#4B2E1E")
CREAM = colors.HexColor("#FFF4E6")


def pdf_table(rows: list, widths: list) -> Table:
    """A table with an orange header row and brown text."""
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORANGE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, -1), BROWN),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CREAM]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5CDB5")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def clean_ai_text(text: str) -> str:
    """Remove markdown symbols so the PDF looks clean."""
    text = text.replace("**", "").replace("__", "").replace("#", "")
    return text.strip()


def make_pdf(data: dict, analysis: str) -> str:
    """Build the PDF file in the reports folder and return the file name."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"sales_report_{data['period']}_{stamp}.pdf".replace(" ", "_")
    path = os.path.join(REPORTS_DIR, filename)

    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Title"], textColor=ORANGE, fontSize=22)
    heading = ParagraphStyle("heading", parent=styles["Heading2"], textColor=ORANGE, spaceBefore=12)
    body = ParagraphStyle("body", parent=styles["BodyText"], textColor=BROWN, leading=14)

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    story = []

    story.append(Paragraph("Stock Sense - Sales Report", title))
    story.append(Paragraph(f"{escape(data['label'])}: {data['start']} to {data['end']}", body))
    story.append(Paragraph("Generated on " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), body))
    story.append(Spacer(1, 10))

    # key numbers
    story.append(Paragraph("Key Numbers", heading))
    story.append(pdf_table([
        ["Units sold", "Revenue", "Profit"],
        [str(data["units"]), money(data["revenue"]), money(data["profit"])],
    ], [5.5 * cm, 5.5 * cm, 5.5 * cm]))

    # AI analysis
    story.append(Paragraph("AI Analysis", heading))
    for line in clean_ai_text(analysis).split("\n"):
        if line.strip() == "":
            continue
        story.append(Paragraph(escape(line.strip()), body))

    # top products
    story.append(Paragraph("Top 5 Products", heading))
    rows = [["Rank", "Product", "Units", "Revenue"]]
    for i, item in enumerate(data["top"]):
        rows.append([str(i + 1), item["name"], str(item["units"]), money(item["revenue"])])
    story.append(pdf_table(rows, [1.5 * cm, 7 * cm, 3 * cm, 5 * cm]))

    # categories
    story.append(Paragraph("Sales by Category", heading))
    rows = [["Category", "Units", "Revenue"]]
    for category, values in data["categories"].items():
        rows.append([category, str(values["units"]), money(values["revenue"])])
    story.append(pdf_table(rows, [8 * cm, 3.5 * cm, 5 * cm]))

    # daily sales
    story.append(Paragraph("Daily Sales", heading))
    rows = [["Date", "Units", "Revenue"]]
    for date, units, revenue in data["daily_rows"]:
        rows.append([date, str(units), money(revenue)])
    story.append(pdf_table(rows, [6 * cm, 4 * cm, 6.5 * cm]))

    # stock alerts
    story.append(Paragraph("Stock Alerts", heading))
    story.append(Paragraph("<b>Out of stock:</b> " + escape(", ".join(data["out_of_stock"]) or "none"), body))
    story.append(Paragraph("<b>Low stock:</b> " + escape(", ".join(data["low_stock"]) or "none"), body))

    doc.build(story)
    return filename
