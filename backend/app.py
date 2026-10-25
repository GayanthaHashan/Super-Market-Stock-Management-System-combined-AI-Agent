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