import multiprocessing
import time

def task(name):
    for i in range(10):
        print(f"{name} running {i}")
        time.sleep(1)

if __name__ == "__main__":
    # Create processes
    p1 = multiprocessing.Process(target=task, args=("Process-1",))
    p2 = multiprocessing.Process(target=task, args=("Process-2",))

    # Start processes
    p1.start()
    p2.start()

    # Wait for them to finish
    p1.join()
    p2.join()

    print("All processes finished")

