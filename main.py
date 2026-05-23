from fastmcp import FastMCP
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import certifi

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

# Create MongoDB client
client = MongoClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where()
)

# Database
db = client["expense_tracker"]

# Collections
expenses_collection = db["expenses"]
categories_collection = db["categories"]

# Initialize MCP server
mcp = FastMCP(name= "ExpenseTracker")

# Seed default categories once
DEFAULT_CATEGORIES = ["Food", "Travel", "Shopping", "Billing", "Entertainment", "Health"]

if categories_collection.count_documents == 0:
    categories_collection.insert_many([
        {"name": category}
        for category in DEFAULT_CATEGORIES
    ])

@mcp.tool()
def add_expense(date, amount, category, subcategory="", note=""):
    '''Add a new expense'''

    # Validate category exists
    category_exists = categories_collection.find_one({"name": category})

    if not category_exists:
        return {
            "status": "error",
            "message": f"Invalid category: {category}"
        }
    
    result = expenses_collection.insert_one({
        "date": date,
        "amount": float(amount),
        "category": category,
        "subcategory": subcategory,
        "note": note
    })

    return {
        "status": "ok",
        "id": str(result.inserted_id)
    }


@mcp.tool()
def list_expenses(start_date, end_date):
    '''List expenses between two dates'''

    expenses = expenses_collection.find({
        "date": {
            "$gte": start_date,
            "$lte": end_date
        }
    }).sort("date", 1)

    return [
        {
            "id": str(expense["_id"]),
            "date": expense["date"],
            "amount": expense["amount"],
            "category": expense["category"],
            "subcategory": expense.get("subcategory", ""),
            "note": expense.get("note", "")
        }
        for expense in expenses
    ]


@mcp.tool()
def summarize(start_date, end_date, category=None):
    '''Summarize expenses by category'''

    match_stage = {
        "date": {
            "$gte": start_date,
            "$lte": end_date
        }
    }

    if category:
        match_stage["category"] = category

    pipeline = [
        {
            "$match": match_stage
        },
        {
            "$group": {
                "_id": "$category",
                "total_amount": {
                    "$sum": "$amount"
                }
            }
        },
        {
            "$sort": {
                "_id": 1
            }
        }
    ]

    summary = expenses_collection.aggregate(pipeline)

    return [
        {
            "category": item["_id"],
            "total_amount": item["total_amount"]
        }
        for item in summary
    ]


@mcp.tool()
def add_category(name):
    '''Add a new category'''

    existing = categories_collection.find_one({"name": name})

    if existing:
        return {
            "status": "error",
            "message": "Category already exists"
        }
    
    result = categories_collection.insert_one({"name": name})

    return {
        "status": "ok",
        "id": str(result.inserted_id)
    }


@mcp.resource(
    "expense://categories",
    mime_type="application/json"
)
def categories():
    """
    Return all categories.
    """

    categories_data = categories_collection.find(
        {},
        {"_id": 0, "name": 1}
    ).sort("name", 1)

    return [
        category["name"]
        for category in categories_data
    ]


if __name__ == "__main__":
    mcp.run(transport= "http", host= "0.0.0.0", port= 8000)