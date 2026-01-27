from dotenv import load_dotenv, find_dotenv
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
import requests
import os
from typing import List, Union

load_dotenv(find_dotenv())

# Tools
## Search Tool
search_tool = DuckDuckGoSearchRun(region="us-en")

## Generalized Calculator Tool
@tool
def calculator(numbers: List[float], operation: str) -> dict:
    """
    Perform mathematical operations on a list of numbers.
    
    Args:
        numbers: List of numbers to perform operation on (e.g., [10, 20, 30])
        operation: The operation to perform
    
    Supported operations:
        Basic arithmetic:
        - add: Sum of all numbers
        - subtract: First number minus sum of remaining numbers
        - multiply: Product of all numbers
        - divide: First number divided by product of remaining numbers
        
        Statistical operations:
        - mean/average: Average of all numbers
        - median: Middle value when numbers are sorted
        - mode: Most frequently occurring number
        - sum: Total sum of all numbers
        - min: Minimum value
        - max: Maximum value
        - range: Difference between max and min
        
        Advanced operations:
        - percentage: Calculate percentage (requires exactly 2 numbers: [part, whole])
        - percentage_change: Calculate percentage change (requires exactly 2 numbers: [old, new])
        - variance: Statistical variance
        - std_dev: Standard deviation
        - product: Product of all numbers
        - power: Raise first number to power of second (requires exactly 2 numbers)
        - sqrt: Square root of first number
        - absolute: Absolute values of all numbers
    
    Returns:
        Dictionary with operation details and result
    
    Examples:
        - calculator([10, 20, 30], "add") -> 60
        - calculator([100, 25], "percentage") -> 25% of 100 = 25.0
        - calculator([50, 75], "percentage_change") -> 50% increase
        - calculator([10, 5, 8, 12], "mean") -> 8.75
    """
    try:
        # Validate input
        if not numbers or len(numbers) == 0:
            return {"error": "At least one number is required"}
        
        operation = operation.lower().strip()
        
        # Basic Arithmetic Operations
        if operation in ["add", "sum"]:
            result = sum(numbers)
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"Sum of {numbers} = {result}"
            }
        
        elif operation == "subtract":
            if len(numbers) < 2:
                return {"error": "Subtraction requires at least 2 numbers"}
            result = numbers[0] - sum(numbers[1:])
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"{numbers[0]} - {sum(numbers[1:])} = {result}"
            }
        
        elif operation in ["multiply", "product"]:
            result = 1
            for num in numbers:
                result *= num
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"Product of {numbers} = {result}"
            }
        
        elif operation == "divide":
            if len(numbers) < 2:
                return {"error": "Division requires at least 2 numbers"}
            divisor = 1
            for num in numbers[1:]:
                divisor *= num
            if divisor == 0:
                return {"error": "Division by zero is not allowed"}
            result = numbers[0] / divisor
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"{numbers[0]} ÷ {divisor} = {result}"
            }
        
        # Statistical Operations
        elif operation in ["mean", "average"]:
            result = sum(numbers) / len(numbers)
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"Average of {numbers} = {result}"
            }
        
        elif operation == "median":
            sorted_nums = sorted(numbers)
            n = len(sorted_nums)
            if n % 2 == 0:
                result = (sorted_nums[n//2 - 1] + sorted_nums[n//2]) / 2
            else:
                result = sorted_nums[n//2]
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"Median of {numbers} = {result}"
            }
        
        elif operation == "mode":
            from collections import Counter
            counts = Counter(numbers)
            max_count = max(counts.values())
            modes = [num for num, count in counts.items() if count == max_count]
            return {
                "operation": operation,
                "numbers": numbers,
                "result": modes[0] if len(modes) == 1 else modes,
                "description": f"Mode of {numbers} = {modes[0] if len(modes) == 1 else modes}"
            }
        
        elif operation == "min":
            result = min(numbers)
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"Minimum of {numbers} = {result}"
            }
        
        elif operation == "max":
            result = max(numbers)
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"Maximum of {numbers} = {result}"
            }
        
        elif operation == "range":
            result = max(numbers) - min(numbers)
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"Range of {numbers} = {result}"
            }
        
        # Percentage Operations
        elif operation == "percentage":
            if len(numbers) != 2:
                return {"error": "Percentage calculation requires exactly 2 numbers: [percentage, whole]"}
            percentage, whole = numbers
            result = (percentage / 100) * whole
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"{percentage}% of {whole} = {result}"
            }
        
        elif operation == "percentage_change":
            if len(numbers) != 2:
                return {"error": "Percentage change requires exactly 2 numbers: [old_value, new_value]"}
            old_value, new_value = numbers
            if old_value == 0:
                return {"error": "Old value cannot be zero for percentage change"}
            change = ((new_value - old_value) / old_value) * 100
            return {
                "operation": operation,
                "numbers": numbers,
                "result": change,
                "description": f"Change from {old_value} to {new_value} = {change:.2f}% {'increase' if change > 0 else 'decrease'}"
            }
        
        # Advanced Operations
        elif operation == "variance":
            mean = sum(numbers) / len(numbers)
            variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
            return {
                "operation": operation,
                "numbers": numbers,
                "result": variance,
                "description": f"Variance of {numbers} = {variance}"
            }
        
        elif operation in ["std_dev", "standard_deviation"]:
            mean = sum(numbers) / len(numbers)
            variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
            std_dev = variance ** 0.5
            return {
                "operation": operation,
                "numbers": numbers,
                "result": std_dev,
                "description": f"Standard deviation of {numbers} = {std_dev}"
            }
        
        elif operation == "power":
            if len(numbers) != 2:
                return {"error": "Power operation requires exactly 2 numbers: [base, exponent]"}
            base, exponent = numbers
            result = base ** exponent
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"{base} ^ {exponent} = {result}"
            }
        
        elif operation in ["sqrt", "square_root"]:
            if len(numbers) != 1:
                return {"error": "Square root requires exactly 1 number"}
            if numbers[0] < 0:
                return {"error": "Cannot calculate square root of negative number"}
            result = numbers[0] ** 0.5
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"√{numbers[0]} = {result}"
            }
        
        elif operation in ["abs", "absolute"]:
            result = [abs(x) for x in numbers]
            return {
                "operation": operation,
                "numbers": numbers,
                "result": result,
                "description": f"Absolute values of {numbers} = {result}"
            }
        
        else:
            return {
                "error": f"Unsupported operation '{operation}'",
                "supported_operations": [
                    "add", "subtract", "multiply", "divide", "sum", "product",
                    "mean", "average", "median", "mode", "min", "max", "range",
                    "percentage", "percentage_change", "variance", "std_dev",
                    "power", "sqrt", "absolute"
                ]
            }
    
    except Exception as e:
        return {"error": str(e)}


## Stock Price Tool
@tool
def get_stock_price(symbol: str) -> dict: 
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
    
    Returns:
        Dictionary containing stock quote information with keys like:
        - '01. symbol': Stock symbol
        - '05. price': Current price
        - '06. volume': Trading volume
        - '08. previous close': Previous day's closing price
        - '09. change': Price change amount
        - '10. change percent': Percentage change
        
        Or {'error': 'error message'} if request fails
    
    Examples:
        - get_stock_price("AAPL") -> Returns Apple stock data
        - get_stock_price("TSLA") -> Returns Tesla stock data
        - get_stock_price("WIPRO") -> Returns Wipro stock data
    
    Note:
        Requires ALPHAVANTAGE_API_KEY to be set in environment variables.
        API has rate limits (typically 5 calls per minute for free tier).
    """
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": os.getenv("ALPHAVANTAGE_API_KEY"),
    }
    try:
        response = requests.get(url, params=params, timeout=10).json()
        global_quote = response.get("Global Quote", {})
        
        # If empty response, might be API limit or invalid symbol
        if not global_quote:
            return {
                "error": f"No data found for symbol '{symbol}'. This could be due to: invalid symbol, API rate limit, or API key issue.",
                "response": response
            }
        
        return global_quote
    except requests.Timeout:
        return {"error": f"Request timeout while fetching stock price for {symbol}"}
    except requests.RequestException as e:
        return {"error": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

