import threading
import time

def task(name):
    for i in range(10):
        print(f"{name} is running {i}")
        time.sleep(1)

# Create threads
t1 = threading.Thread(target=task, args=("Thread-1",))
t2 = threading.Thread(target=task, args=("Thread-2",))

# Start threads
t1.start()
t2.start()

# Wait for threads to finish
t1.join()
t2.join()

print("All threads finished")
