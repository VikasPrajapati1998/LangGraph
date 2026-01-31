from __future__ import annotations
from fastmcp import FastMCP
from typing import Any, Dict
import requests


mcp = FastMCP("StockServer")

# ================= Utility =================

def success_response(tool: str, numbers, result) -> Dict[str, Any]:
    return {
        "status": "success",
        "tool": tool,
        "numbers": numbers,
        "result": result,
    }


def error_response(tool: str, numbers, message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "tool": tool,
        "numbers": numbers,
        "result": message,
    }


# ================= Tools ===================

@mcp.tool()
async def get_stock_price(symbol: str) -> dict:
    """
    Fetch the latest real-time stock price and trading information for a given stock symbol.
    
    This tool retrieves current market data from Alpha Vantage API including:
    - Current stock price
    - Trading volume
    - Previous close price
    - Day's high and low prices
    - Price change and percentage change
    
    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL' for Apple, 'TSLA' for Tesla, 
                'GOOGL' for Google, 'MSFT' for Microsoft, 'AMZN' for Amazon,
                'WIPRO.BSE' for Wipro on BSE, 'RELIANCE.BSE' for Reliance)
    """
    URL = "https://www.alphavantage.co/query"
    ALPHAVANTAGE_API_KEY="VQ676BFVISUZVO2U"
    
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": ALPHAVANTAGE_API_KEY,
    }
    
    try:
        response = requests.get(URL, params=params, timeout=10).json()
        global_quote = response.get("Global Quote", {})
        
        # If empty response, might be API limit or invalid symbol
        if not global_quote:
            return {
                "error": f"No data found for symbol '{symbol}'. This could be due to: invalid symbol, API rate limit, or API key issue.",
                "response": response
            }
        return success_response("get_stock_price", symbol, global_quote)
    except Exception as e:
        return error_response("get_stock_price", symbol, str(e))
        

if __name__ == "__main__":
    mcp.run()
