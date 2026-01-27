from __future__ import annotations

from fastmcp import FastMCP
from typing import Iterable, Any, Dict, List
import math
import statistics
import random

mcp = FastMCP("Calculator")

# ================= Utility =================

def success_response(tool: str, numbers, result, description: str) -> Dict[str, Any]:
    return {
        "status": "success",
        "tool": tool,
        "numbers": numbers,
        "result": result,
        "description": description,
    }


def error_response(tool: str, numbers, message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "tool": tool,
        "numbers": numbers,
        "result": None,
        "description": message,
    }


def _as_number(x) -> float:
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        return float(x.strip())
    raise TypeError("Expected a number (int, float, or numeric string)")


def _as_number_list(values) -> List[float]:
    if isinstance(values, str):
        values = values.split(",")

    if not isinstance(values, Iterable):
        raise TypeError("Expected an iterable of numbers")

    nums = [_as_number(v) for v in values]
    if not nums:
        raise ValueError("At least one number is required")
    return nums


def _require_exact(nums: list[float], count: int):
    if len(nums) != count:
        raise ValueError(f"Exactly {count} numbers are required")

# ================= Basic Arithmetic =================

@mcp.tool()
async def add(numbers):
    """
    Add all numbers together.

    Behavior:
        - Accepts one or more numbers
        - Returns the total sum of all values

    Example:
        add([10, 20, 30]) -> 60
    """
    try:
        nums = _as_number_list(numbers)
        result = sum(nums)
        return success_response("add", nums, result, f"Sum of {nums} = {result}")
    except Exception as e:
        return error_response("add", numbers, str(e))


@mcp.tool()
async def subtract(numbers):
    """
    Subtract numbers from left to right.

    Behavior:
        - Takes the first number
        - Subtracts the sum of all remaining numbers from it

    Example:
        subtract([100, 20, 30]) -> 50
    """
    try:
        nums = _as_number_list(numbers)
        result = nums[0] - sum(nums[1:])
        return success_response(
            "subtract", nums, result, f"{nums[0]} - {nums[1:]} = {result}"
        )
    except Exception as e:
        return error_response("subtract", numbers, str(e))


@mcp.tool()
async def multiply(numbers):
    """
    Multiply all numbers together.

    Behavior:
        - Accepts one or more numbers
        - Returns the product of all values

    Example:
        multiply([2, 3, 4]) -> 24
    """
    try:
        nums = _as_number_list(numbers)
        result = math.prod(nums)
        return success_response(
            "multiply", nums, result, f"Product of {nums} = {result}"
        )
    except Exception as e:
        return error_response("multiply", numbers, str(e))


@mcp.tool()
async def divide(numbers):
    """
    Divide the first number by the product of the remaining numbers.

    Behavior:
        - First number is the dividend
        - Remaining numbers are multiplied to form the divisor
        - Division by zero is not allowed

    Example:
        divide([100, 2, 5]) -> 10
    """
    try:
        nums = _as_number_list(numbers)
        divisor = math.prod(nums[1:]) if len(nums) > 1 else 1
        if divisor == 0:
            raise ZeroDivisionError("Division by zero")
        result = nums[0] / divisor
        return success_response(
            "divide", nums, result, f"{nums[0]} / {divisor} = {result}"
        )
    except Exception as e:
        return error_response("divide", numbers, str(e))

# ================= Statistical =================

@mcp.tool()
async def mean(numbers):
    """
    Calculate the arithmetic mean (average) of all numbers.

    Behavior:
        - Adds all values
        - Divides by the count of values

    Example:
        mean([10, 5, 8, 12]) -> 8.75
    """
    try:
        nums = _as_number_list(numbers)
        result = sum(nums) / len(nums)
        return success_response("mean", nums, result, f"Mean of {nums} = {result}")
    except Exception as e:
        return error_response("mean", numbers, str(e))


@mcp.tool()
async def median(numbers):
    """
    Calculate the median (middle value) of the numbers.

    Behavior:
        - Sorts values
        - Returns the middle value
        - If even count, returns the average of the two middle values

    Example:
        median([1, 3, 5]) -> 3
        median([1, 3, 5, 7]) -> 4
    """
    try:
        nums = _as_number_list(numbers)
        result = statistics.median(nums)
        return success_response("median", nums, result, f"Median of {nums} = {result}")
    except Exception as e:
        return error_response("median", numbers, str(e))


@mcp.tool()
async def mode(numbers):
    """
    Calculate the mode (most frequently occurring value).

    Behavior:
        - Returns the value that appears most often
        - Raises an error if no unique mode exists

    Example:
        mode([1, 2, 2, 3]) -> 2
    """
    try:
        nums = _as_number_list(numbers)
        result = statistics.mode(nums)
        return success_response("mode", nums, result, f"Mode of {nums} = {result}")
    except Exception as e:
        return error_response("mode", numbers, str(e))


@mcp.tool()
async def sum_values(numbers):
    """
    Calculate the total sum of all numbers.

    Behavior:
        - Adds all values together

    Example:
        sum_values([5, 10, 15]) -> 30
    """
    try:
        nums = _as_number_list(numbers)
        result = sum(nums)
        return success_response("sum", nums, result, f"Sum of {nums} = {result}")
    except Exception as e:
        return error_response("sum", numbers, str(e))


@mcp.tool()
async def min_value(numbers):
    """
    Find the minimum value.

    Behavior:
        - Returns the smallest number in the list

    Example:
        min_value([3, 7, 2]) -> 2
    """
    try:
        nums = _as_number_list(numbers)
        result = min(nums)
        return success_response("min", nums, result, f"Min of {nums} = {result}")
    except Exception as e:
        return error_response("min", numbers, str(e))


@mcp.tool()
async def max_value(numbers):
    """
    Find the maximum value.

    Behavior:
        - Returns the largest number in the list

    Example:
        max_value([3, 7, 2]) -> 7
    """
    try:
        nums = _as_number_list(numbers)
        result = max(nums)
        return success_response("max", nums, result, f"Max of {nums} = {result}")
    except Exception as e:
        return error_response("max", numbers, str(e))


@mcp.tool()
async def range_value(numbers):
    """
    Calculate the range of values.

    Behavior:
        - Range = max value − min value

    Example:
        range_value([2, 8, 3]) -> 6
    """
    try:
        nums = _as_number_list(numbers)
        result = max(nums) - min(nums)
        return success_response(
            "range", nums, result, f"Range of {nums} = {result}"
        )
    except Exception as e:
        return error_response("range", numbers, str(e))


@mcp.tool()
async def variance(numbers):
    """
    Calculate the statistical variance.

    Behavior:
        - Measures how far values are spread from the mean
        - Requires at least two numbers

    Example:
        variance([1, 2, 3, 4]) -> 1.666...
    """
    try:
        nums = _as_number_list(numbers)
        if len(nums) < 2:
            raise ValueError("Variance requires at least two numbers")
        result = statistics.variance(nums)
        return success_response(
            "variance", nums, result, f"Variance of {nums} = {result}"
        )
    except Exception as e:
        return error_response("variance", numbers, str(e))


@mcp.tool()
async def std_dev(numbers):
    """
    Calculate the standard deviation.

    Behavior:
        - Square root of variance
        - Indicates spread of data
        - Requires at least two numbers

    Example:
        std_dev([1, 2, 3, 4]) -> 1.290...
    """
    try:
        nums = _as_number_list(numbers)
        if len(nums) < 2:
            raise ValueError("Standard deviation requires at least two numbers")
        result = statistics.stdev(nums)
        return success_response(
            "std_dev", nums, result, f"Std deviation of {nums} = {result}"
        )
    except Exception as e:
        return error_response("std_dev", numbers, str(e))

# ================= Advanced =================

@mcp.tool()
async def percentage(numbers):
    """
    Calculate percentage.

    Behavior:
        - Requires exactly two numbers: [part, whole]
        - Returns (part / whole) * 100
    """
    try:
        nums = _as_number_list(numbers)
        _require_exact(nums, 2)
        part, whole = nums
        if whole == 0:
            raise ZeroDivisionError("Whole cannot be zero")
        result = (part / whole) * 100
        return success_response(
            "percentage", nums, result, f"{part}% of {whole} = {result}"
        )
    except Exception as e:
        return error_response("percentage", numbers, str(e))


@mcp.tool()
async def percentage_change(numbers):
    """
    Calculate percentage change.

    Behavior:
        - Requires exactly two numbers: [old, new]
        - Returns percentage increase or decrease
    """
    try:
        nums = _as_number_list(numbers)
        _require_exact(nums, 2)
        old, new = nums
        if old == 0:
            raise ZeroDivisionError("Old value cannot be zero")
        result = ((new - old) / old) * 100
        return success_response(
            "percentage_change",
            nums,
            result,
            f"Percentage change from {old} to {new} = {result}%",
        )
    except Exception as e:
        return error_response("percentage_change", numbers, str(e))


@mcp.tool()
async def product(numbers):
    """
    Calculate the product of all numbers.

    Equivalent to multiplication but exposed as a separate tool.
    """
    try:
        nums = _as_number_list(numbers)
        result = math.prod(nums)
        return success_response(
            "product", nums, result, f"Product of {nums} = {result}"
        )
    except Exception as e:
        return error_response("product", numbers, str(e))


@mcp.tool()
async def power(numbers):
    """
    Raise the first number to the power of the second.

    Behavior:
        - Requires exactly two numbers: [base, exponent]
    """
    try:
        nums = _as_number_list(numbers)
        _require_exact(nums, 2)
        result = nums[0] ** nums[1]
        return success_response(
            "power", nums, result, f"{nums[0]} ^ {nums[1]} = {result}"
        )
    except Exception as e:
        return error_response("power", numbers, str(e))


@mcp.tool()
async def sqrt(numbers):
    """
    Calculate the square root of the first number.

    Behavior:
        - Uses only the first value
        - Negative values are not allowed
    """
    try:
        nums = _as_number_list(numbers)
        value = nums[0]
        if value < 0:
            raise ValueError("Square root of negative number is not allowed")
        result = math.sqrt(value)
        return success_response(
            "sqrt", nums, result, f"√{value} = {result}"
        )
    except Exception as e:
        return error_response("sqrt", numbers, str(e))


@mcp.tool()
async def absolute(numbers):
    """
    Calculate absolute values.

    Behavior:
        - Returns a list of absolute values for all numbers
    """
    try:
        nums = _as_number_list(numbers)
        result = [abs(n) for n in nums]
        return success_response(
            "absolute", nums, result, f"|{nums}| = {result}"
        )
    except Exception as e:
        return error_response("absolute", numbers, str(e))

# ================= Utility =================

@mcp.tool()
async def get_random(min_val: int = 1, max_val: int = 100, count: int = 1):
    """
    Generate random integers.

    Behavior:
        - Generates random integers between min_val and max_val (inclusive)
        - If count == 1, returns a single integer
        - If count > 1, returns a list of integers
    """
    try:
        if min_val > max_val:
            raise ValueError("min_val must be <= max_val")
        if count < 1:
            raise ValueError("count must be >= 1")

        values = [random.randint(min_val, max_val) for _ in range(count)]
        result = values[0] if count == 1 else values
        return success_response(
            "get_random",
            [min_val, max_val, count],
            result,
            f"Generated random values = {result}",
        )
    except Exception as e:
        return error_response("get_random", [min_val, max_val, count], str(e))
    

# =================== Run Server =================

if __name__ == "__main__":
    mcp.run()

