import multiprocessing

def square(n):
    return n * n

def cube(n):
    return n * n * n

if __name__ == "__main__":
    numbers = [x for x in range(1, 100)]

    # Create a pool of worker processes
    with multiprocessing.Pool(4) as pool:
        square_results = pool.map(square, numbers)
    
    with multiprocessing.Pool(4) as pool:
        cube_results = pool.map(cube, numbers)

    print("Square Results: ", square_results)
    print("\n"*2)
    print("Cube Results: ", cube_results)
