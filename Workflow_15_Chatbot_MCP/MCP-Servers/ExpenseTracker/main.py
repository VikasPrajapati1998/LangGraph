from fastmcp import FastMCP
import aiosqlite
import os
import json
from typing import List, Dict, Optional, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

# Flag to track if database has been initialized
_db_initialized = False

mcp = FastMCP("ExpenseTracker")


# ========== Helper Functions ==========

def success_response(tool: str, response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a standardized success response.
    """
    return {
        "status": "success",
        "tool": tool,
        "response": response
    }


def error_response(tool: str, error: str) -> Dict[str, Any]:
    """
    Generate a standardized error response.
    """
    return {
        "status": "error",
        "tool": tool,
        "error": error
    }


# ========== Database Initialization ==========

async def init_db() -> None:
    """
    Initialize the SQLite database and create required tables if missing.

    This function is safe to run multiple times and will not
    overwrite existing data.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)
            await db.commit()
    except Exception as e:
        pass


async def ensure_db_exists() -> None:
    """
    Ensure database exists by inserting and deleting a dummy record.
    This forces the database file to be created on first run.
    """
    try:
        await init_db()  # First ensure table exists
        
        async with aiosqlite.connect(DB_PATH) as db:
            # Insert dummy data to ensure database is properly created
            cursor = await db.execute(
                """
                INSERT INTO expenses (date, amount, category, subcategory, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                ('1970-01-01', 1, 'System', 'Initialization', 'Dummy record')
            )
            dummy_id = cursor.lastrowid
            await db.commit()
            
            # Immediately delete the dummy record
            await db.execute("DELETE FROM expenses WHERE id = ?", (dummy_id,))
            await db.commit()
    except Exception as e:
        pass


# ========== CRUD MCP Tools ==========

@mcp.tool()
async def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = '',
    note: str = ''
) -> Dict[str, Any]:
    """
    Add a new expense entry to the database.

    Args:
        date (str): Expense date (YYYY-MM-DD).
        amount (float): Expense amount (must be > 0).
        category (str): Main expense category.
        subcategory (str, optional): Subcategory name.
        note (str, optional): Additional notes.

    Returns:
        Dict[str, Any]: Status and inserted expense ID.
    """
    global _db_initialized
    
    # Ensure database is initialized on first use
    if not _db_initialized:
        await ensure_db_exists()
        _db_initialized = True
    
    try:
        if amount <= 0:
            return error_response("add_expense", "Amount must be greater than zero")

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """
                INSERT INTO expenses (date, amount, category, subcategory, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (date, amount, category, subcategory, note)
            )
            await db.commit()

            return success_response(
                tool="add_expense",
                response={
                    "id": cursor.lastrowid,
                    "date": date,
                    "amount": amount,
                    "category": category,
                    "subcategory": subcategory,
                    "note": note
                }
            )

    except Exception as e:
        return error_response("add_expense", str(e))


@mcp.tool()
async def edit_expense(
    expense_id: int,
    date: str,
    amount: float,
    category: str,
    subcategory: str = '',
    note: str = ''
) -> Dict[str, Any]:
    """
    Update an existing expense record.

    Args:
        expense_id (int): ID of the expense to update.
        date (str): Updated date.
        amount (float): Updated amount.
        category (str): Updated category.
        subcategory (str, optional): Updated subcategory.
        note (str, optional): Updated note.

    Returns:
        Dict[str, Any]: Update status and affected row count.
    """
    global _db_initialized
    
    # Ensure database is initialized on first use
    if not _db_initialized:
        await ensure_db_exists()
        _db_initialized = True
    
    try:
        if amount <= 0:
            return error_response("edit_expense", "Amount must be greater than zero")

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """
                UPDATE expenses
                SET date = ?, amount = ?, category = ?, subcategory = ?, note = ?
                WHERE id = ?
                """,
                (date, amount, category, subcategory, note, expense_id)
            )
            await db.commit()

            if cursor.rowcount == 0:
                return error_response("edit_expense", "Expense ID not found")

            return success_response(
                tool="edit_expense",
                response={
                    "updated": cursor.rowcount,
                    "id": expense_id,
                    "date": date,
                    "amount": amount,
                    "category": category,
                    "subcategory": subcategory,
                    "note": note
                }
            )

    except Exception as e:
        return error_response("edit_expense", str(e))


@mcp.tool()
async def delete_expense(expense_id: int) -> Dict[str, Any]:
    """
    Delete an expense record by ID.

    Args:
        expense_id (int): Expense ID to delete.

    Returns:
        Dict[str, Any]: Deletion status and affected row count.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "DELETE FROM expenses WHERE id = ?",
                (expense_id,)
            )
            await db.commit()

            if cursor.rowcount == 0:
                return error_response("delete_expense", "Expense ID not found")

            return success_response(
                tool="delete_expense",
                response={
                    "deleted": cursor.rowcount,
                    "id": expense_id
                }
            )

    except Exception as e:
        return error_response("delete_expense", str(e))


@mcp.tool()
async def list_expenses(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve a list of expenses with optional date filtering.

    Args:
        start_date (str, optional): Filter expenses from this date.
        end_date (str, optional): Filter expenses up to this date.

    Returns:
        Dict[str, Any]: Standardized response with list of expense records.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            query = """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
            """
            params = []

            if start_date and end_date:
                query += " WHERE date BETWEEN ? AND ?"
                params.extend([start_date, end_date])
            elif start_date:
                query += " WHERE date >= ?"
                params.append(start_date)
            elif end_date:
                query += " WHERE date <= ?"
                params.append(end_date)

            query += " ORDER BY date ASC"

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            expenses = [dict(row) for row in rows]
            
            return success_response(
                tool="list_expenses",
                response={
                    "expenses": expenses,
                    "count": len(expenses),
                    "start_date": start_date,
                    "end_date": end_date
                }
            )

    except Exception as e:
        return error_response("list_expenses", str(e))


# ========== Summary MCP Tool ==========

@mcp.tool()
async def summarize_expenses(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Summarize total expenses grouped by category.

    Args:
        start_date (str, optional): Start date filter.
        end_date (str, optional): End date filter.
        category (str, optional): Limit to a specific category.

    Returns:
        Dict[str, Any]: Standardized response with category-wise expense totals.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            query = "SELECT category, SUM(amount) FROM expenses"
            params = []
            conditions = []

            if start_date:
                conditions.append("date >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("date <= ?")
                params.append(end_date)
            if category:
                conditions.append("category = ?")
                params.append(category)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " GROUP BY category"

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            summary = [
                {"category": row[0], "total": row[1] or 0.0}
                for row in rows
            ]
            
            total_amount = sum(item["total"] for item in summary)
            
            return success_response(
                tool="summarize_expenses",
                response={
                    "summary": summary,
                    "total_categories": len(summary),
                    "grand_total": total_amount,
                    "start_date": start_date,
                    "end_date": end_date,
                    "category_filter": category
                }
            )

    except Exception as e:
        return error_response("summarize_expenses", str(e))


# ========== MCP Resource ==========

@mcp.resource("expense://categories", mime_type="application/json")
async def categories() -> Dict[str, Any]:
    """
    Provide expense categories and subcategories from a JSON file.

    Returns:
        Dict[str, Any]: Categories data or error information.
    """
    try:
        if not os.path.exists(CATEGORIES_PATH):
            return error_response("categories", "categories.json not found")

        with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        return success_response(
            tool="categories",
            response=data
        )

    except json.JSONDecodeError:
        return error_response("categories", "Invalid JSON format in categories.json")
    except Exception as e:
        return error_response("categories", str(e))


# ========== Run MCP Server ==========

if __name__ == "__main__":
    """
    Start the MCP ExpenseTracker server.
    """
    mcp.run()

