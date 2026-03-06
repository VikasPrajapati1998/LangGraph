from multiprocessing import Process
import math

def compute_factorial(n):
    print(f"Factorial of {n} is {math.factorial(n)}")

if __name__ == "__main__":
    numbers = [1,2,3,4,5,6,7,8,9,10]

    processes = []

    # Create a process for each number
    for n in numbers:
        p = Process(target=compute_factorial, args=(n,))
        processes.append(p)
        p.start()

    # Wait for all processes to finish
    for p in processes:
        p.join()

    print("All factorials computed using Process!")

