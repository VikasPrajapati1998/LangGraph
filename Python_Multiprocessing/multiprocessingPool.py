import multiprocessing

def square(n):
    return n * n

if __name__ == "__main__":
    numbers = [x for x in range(1, 100)]

    # Create a pool of worker processes
    with multiprocessing.Pool(8) as pool:
        results = pool.map(square, numbers)

    print("Results:", results)
