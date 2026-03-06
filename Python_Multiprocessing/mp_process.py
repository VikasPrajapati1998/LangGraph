from multiprocessing import Process

def square(n):
    print(f"Square of {n} is {n * n}")

def cube(n):
    print(f"Cube of {n} is {n * n * n}")

if __name__ == "__main__":
    numbers =  [x for x in range(1, 100)]
    processes = []

    # Create a process for each number for square
    for n in numbers:
        p = Process(target=square, args=(n,))
        processes.append(p)
        p.start()

    # Wait for all square processes to finish
    for p in processes:
        p.join()

    print("\nNow computing cubes...\n")
    processes = []

    # Create a process for each number for cube
    for n in numbers:
        p = Process(target=cube, args=(n,))
        processes.append(p)
        p.start()

    # Wait for all cube processes to finish
    for p in processes:
        p.join()

    print("All processes finished")