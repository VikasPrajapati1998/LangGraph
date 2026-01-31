from __future__ import annotations

from fastmcp import FastMCP
from typing import Any, Dict, List, Union
import math
import statistics
import random

mcp = FastMCP("Calculator")

# ================= Utility Functions =================

def success_response(operation: str, numbers: List[float], result: Any, description: str) -> Dict[str, Any]:
    """Format success response"""
    return {
        "status": "success",
        "operation": operation,
        "numbers": numbers,
        "result": result,
        "description": description,
    }


def error_response(operation: str, numbers: Any, message: str) -> Dict[str, Any]:
    """Format error response"""
    return {
        "status": "error",
        "operation": operation,
        "numbers": numbers if isinstance(numbers, list) else str(numbers),
        "result": None,
        "description": f"Error: {message}",
    }


def parse_numbers(numbers: Union[str, List[float]]) -> List[float]:
    """Convert input to list of floats"""
    # Handle string input (comma-separated)
    if isinstance(numbers, str):
        numbers = numbers.split(",")
    
    # Convert to list if single number
    if isinstance(numbers, (int, float)):
        numbers = [numbers]
    
    # Parse each number
    nums = []
    for n in numbers:
        if isinstance(n, (int, float)):
            nums.append(float(n))
        elif isinstance(n, str):
            nums.append(float(n.strip()))
        else:
            raise TypeError(f"Cannot convert {type(n).__name__} to number")
    
    if not nums:
        raise ValueError("At least one number is required")
    
    return nums


def require_exact(nums: List[float], count: int):
    """Ensure exactly count numbers are provided"""
    if len(nums) != count:
        raise ValueError(f"Exactly {count} numbers required, got {len(nums)}")


# ================= Main Calculator Tool =================

@mcp.tool()
async def calculator(numbers: Union[str, List[float]], operation: str) -> Dict[str, Any]:
    """
    Universal calculator tool that performs various mathematical operations.
    
    Args:
        numbers: Numbers to operate on. Can be:
                 - List: [1, 2, 3]
                 - Comma-separated string: "1,2,3"
                 - Single number: 5
        operation: The operation to perform. Options:
            - Basic: "add", "sub", "multi", "div", "mod"
            - Advanced: "pow", "sqrt", "abs"
            - Statistical: "mean", "median", "mode", "min", "max", "range", "variance", "std_dev", "sum"
            - Financial: "percentage", "percentage_change"
            - Utility: "random"
    
    Returns:
        Dictionary with status, operation, numbers, result, and description
    
    Examples:
        calculator([10, 20, 30], "add") -> {"result": 60, "description": "Sum of [10, 20, 30] = 60"}
        calculator("100,20,30", "sub") -> {"result": 50}
        calculator([2, 3, 4], "multi") -> {"result": 24}
        calculator([100, 2, 5], "div") -> {"result": 10}
        calculator([10, 3], "mod") -> {"result": 1}
        calculator([2, 8], "pow") -> {"result": 256}
        calculator([16], "sqrt") -> {"result": 4.0}
        calculator([-5, 3, -2], "abs") -> {"result": [5, 3, 2]}
        calculator([10, 5, 8, 12], "mean") -> {"result": 8.75}
        calculator([25, 100], "percentage") -> {"result": 25.0}
    """
    try:
        # Parse numbers
        nums = parse_numbers(numbers)
        
        # Normalize operation name to lowercase
        op = operation.lower().strip()
        
        # ========== BASIC ARITHMETIC ==========
        if op in ["add", "addition", "plus", "+"]:
            result = sum(nums)
            return success_response(op, nums, result, f"Sum of {nums} = {result}")
        
        elif op in ["sub", "subtract", "subtraction", "minus", "-"]:
            result = nums[0] - sum(nums[1:])
            return success_response(op, nums, result, f"{nums[0]} - {sum(nums[1:])} = {result}")
        
        elif op in ["multi", "multiply", "multiplication", "times", "*", "x"]:
            result = math.prod(nums)
            return success_response(op, nums, result, f"Product of {nums} = {result}")
        
        elif op in ["div", "divide", "division", "/"]:
            divisor = math.prod(nums[1:]) if len(nums) > 1 else 1
            if divisor == 0:
                raise ZeroDivisionError("Division by zero")
            result = nums[0] / divisor
            return success_response(op, nums, result, f"{nums[0]} / {divisor} = {result}")
        
        elif op in ["mod", "modulo", "modulus", "remainder", "%"]:
            require_exact(nums, 2)
            if nums[1] == 0:
                raise ZeroDivisionError("Modulo by zero")
            result = nums[0] % nums[1]
            return success_response(op, nums, result, f"{nums[0]} mod {nums[1]} = {result}")
        
        # ========== ADVANCED MATH ==========
        elif op in ["pow", "power", "exponent", "^", "**"]:
            require_exact(nums, 2)
            result = nums[0] ** nums[1]
            return success_response(op, nums, result, f"{nums[0]} ^ {nums[1]} = {result}")
        
        elif op in ["sqrt", "square_root", "root"]:
            value = nums[0]
            if value < 0:
                raise ValueError("Square root of negative number not allowed")
            result = math.sqrt(value)
            return success_response(op, nums, result, f"√{value} = {result}")
        
        elif op in ["abs", "absolute", "absolute_value"]:
            result = [abs(n) for n in nums]
            return success_response(op, nums, result, f"|{nums}| = {result}")
        
        # ========== STATISTICAL ==========
        elif op in ["mean", "average", "avg"]:
            result = sum(nums) / len(nums)
            return success_response(op, nums, result, f"Mean of {nums} = {result}")
        
        elif op in ["median", "middle"]:
            result = statistics.median(nums)
            return success_response(op, nums, result, f"Median of {nums} = {result}")
        
        elif op in ["mode", "most_frequent"]:
            result = statistics.mode(nums)
            return success_response(op, nums, result, f"Mode of {nums} = {result}")
        
        elif op in ["min", "minimum", "smallest"]:
            result = min(nums)
            return success_response(op, nums, result, f"Min of {nums} = {result}")
        
        elif op in ["max", "maximum", "largest"]:
            result = max(nums)
            return success_response(op, nums, result, f"Max of {nums} = {result}")
        
        elif op in ["range", "spread"]:
            result = max(nums) - min(nums)
            return success_response(op, nums, result, f"Range of {nums} = {result}")
        
        elif op in ["variance", "var"]:
            if len(nums) < 2:
                raise ValueError("Variance requires at least 2 numbers")
            result = statistics.variance(nums)
            return success_response(op, nums, result, f"Variance of {nums} = {result}")
        
        elif op in ["std_dev", "std", "stdev", "standard_deviation"]:
            if len(nums) < 2:
                raise ValueError("Standard deviation requires at least 2 numbers")
            result = statistics.stdev(nums)
            return success_response(op, nums, result, f"Std dev of {nums} = {result}")
        
        elif op in ["sum", "total"]:
            result = sum(nums)
            return success_response(op, nums, result, f"Sum of {nums} = {result}")
        
        # ========== FINANCIAL ==========
        elif op in ["percentage", "percent", "%of"]:
            require_exact(nums, 2)
            part, whole = nums
            if whole == 0:
                raise ZeroDivisionError("Whole cannot be zero")
            result = (part / whole) * 100
            return success_response(op, nums, result, f"{part} is {result}% of {whole}")
        
        elif op in ["percentage_change", "percent_change", "pct_change"]:
            require_exact(nums, 2)
            old, new = nums
            if old == 0:
                raise ZeroDivisionError("Old value cannot be zero")
            result = ((new - old) / old) * 100
            return success_response(op, nums, result, f"Change from {old} to {new} = {result:+.2f}%")
        
        # ========== UTILITY ==========
        elif op in ["random", "rand"]:
            # nums = [min, max, count] or [min, max] or [max]
            if len(nums) == 1:
                min_val, max_val, count = 1, int(nums[0]), 1
            elif len(nums) == 2:
                min_val, max_val, count = int(nums[0]), int(nums[1]), 1
            elif len(nums) >= 3:
                min_val, max_val, count = int(nums[0]), int(nums[1]), int(nums[2])
            else:
                raise ValueError("Random needs 1-3 numbers: [max], [min, max], or [min, max, count]")
            
            if min_val > max_val:
                raise ValueError("min_val must be <= max_val")
            if count < 1:
                raise ValueError("count must be >= 1")
            
            values = [random.randint(min_val, max_val) for _ in range(count)]
            result = values[0] if count == 1 else values
            return success_response(op, nums, result, f"Random {count} number(s) [{min_val}-{max_val}]: {result}")
        
        # ========== UNKNOWN OPERATION ==========
        else:
            return error_response(
                op,
                nums,
                f"Unknown operation '{operation}'. Valid: add, sub, multi, div, mod, pow, sqrt, abs, mean, median, mode, min, max, range, variance, std_dev, sum, percentage, percentage_change, random"
            )
            
    except Exception as e:
        return error_response(operation, numbers, str(e))


# =================== Run Server =================

if __name__ == "__main__":
    mcp.run()

