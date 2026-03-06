from multiprocessing import Pool
import math

def compute_factorial(n):
    return math.factorial(n)

if __name__ == "__main__":
    numbers = [1,2,3,4,5,6,7,8,9,10]

    # Create a pool of 4 worker processes
    with Pool(4) as pool:
        results = pool.map(compute_factorial, numbers)

    # Print results
    for n, fact in zip(numbers, results):
        print(f"Factorial of {n} is {fact}")

    print("All factorials computed using Pool!")