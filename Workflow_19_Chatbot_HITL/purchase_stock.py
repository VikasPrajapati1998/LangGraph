from typing import Annotated, Dict, Any
from langchain.tools import tool
from langgraph.types import interrupt


@tool
async def purchase_stock(
    stock_name: Annotated[str, "Name of the stock to purchase"],
    stock_price: Annotated[float, "Price per unit of the stock"],
    quantity: Annotated[int, "Number of units to purchase"],
) -> Dict[str, Any]:
    """
    Purchase the stock of the given stock.
    Simulated purchase with robust error handling.
    """

    try: 
        # ---------- Validation ----------
        if not stock_name or not stock_name.strip():
            raise ValueError("Stock name cannot be empty")

        if stock_price <= 0:
            raise ValueError("Stock price must be greater than 0")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than 0")
        
        # ---------- HITL ------------
        decision = interrupt(f"Approve buying {quantity} shares of {stock_name} at {stock_price} each? (yes/no): ")
        
        if isinstance(decision, str) and decision.lower() == 'yes':
            # ---------- Business Logic ----------
            total_cost = stock_price * quantity

            # ---------- Success Response ----------
            return {
                "status": "success",
                "action": "purchase_stock",
                "stock_name": stock_name.strip().upper(),
                "price_per_unit": round(stock_price, 2),
                "quantity": quantity,
                "total_cost": round(total_cost, 2),
                "message": (
                    f"Successfully purchased {quantity} shares of "
                    f"{stock_name.upper()} at {stock_price} each."
                )
            }
        else:
            return {
                "status": "cancelled",
                "message": f"Purchase of {quantity} shares of {stock_name} was cancelled by user.",
                "stock_name": stock_name,
                "quantity": quantity,
                "price_per_unit": stock_price
            }

    except ValueError as ve:
        # ---------- Input Errors ----------
        return {
            "status": "error",
            "error_type": "validation_error",
            "message": str(ve),
        }

    except Exception as e:
        # ---------- Unexpected Errors ----------
        return {
            "status": "error",
            "error_type": "internal_error",
            "message": "An unexpected error occurred while purchasing stock.",
            "details": str(e),
        }
