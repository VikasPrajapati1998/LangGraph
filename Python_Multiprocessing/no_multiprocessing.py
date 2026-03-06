def square(n):
    return n * n

if __name__ == "__main__":
    numbers = [x for x in range(1, 100)]

    results = list(map(square, numbers))

    print("Results:", results)
