import threading
import time

# Shared variable and lock
total = 0
lock = threading.Lock()

def partial_sum(start, end):
    global total
    subtotal = 0
    for i in range(start, end):
        subtotal += i
    # Safely add subtotal to shared total
    with lock:
        total += subtotal

if __name__ == "__main__":
    start_time = time.perf_counter()

    N = 10000000000  # upper limit
    num_threads = 4

    # Calculate chunk size
    chunk_size = N // num_threads
    threads = []
    start = 1

    for i in range(num_threads):
        end = start + chunk_size
        if i == num_threads - 1:
            end = N  # mimic old loop
        t = threading.Thread(target=partial_sum, args=(start, end))
        threads.append(t)
        start = end

    # Start all threads
    for t in threads:
        t.start()

    # Wait for all threads to finish
    for t in threads:
        t.join()

    end_time = time.perf_counter()

    print("Sum:", total)
    print("Execution Time:", end_time - start_time, "seconds")
    