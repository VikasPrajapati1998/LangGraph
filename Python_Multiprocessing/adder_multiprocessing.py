import multiprocessing
import time

def partial_sum(start, end):
    total = 0
    for i in range(start, end):
        total += i
    return total

if __name__ == "__main__":
    start_time = time.perf_counter()

    N = 10000000000  # original upper limit in your old loop
    num_processes = 4

    # calculate chunk size
    chunk_size = N // num_processes
    ranges = []
    start = 1

    for i in range(num_processes):
        end = start + chunk_size
        if i == num_processes - 1:
            end = N  # exclude the last number to mimic old loop
        ranges.append((start, end))
        start = end

    # create pool and run partial sums
    with multiprocessing.Pool(num_processes) as pool:
        results = pool.starmap(partial_sum, ranges)

    total = sum(results)

    end_time = time.perf_counter()

    print("Sum:", total)
    print("Execution Time:", end_time - start_time, "seconds")
