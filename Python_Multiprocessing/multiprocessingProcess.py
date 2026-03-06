from multiprocessing import Process
import os


def info(title):
    print(title)
    print("Module name:", __name__)
    print("Parent process ID:", os.getppid())
    print("Process ID:", os.getpid())
    print("-" * 30)


def f(name):
    info("Running function f")
    print("Hello", name)


if __name__ == "__main__":
    info("Main process")

    # Create processes
    p1 = Process(target=f, args=("Alice",))
    p2 = Process(target=f, args=("Bob",))

    # Start processes
    p1.start()
    p2.start()

    # Wait for processes to finish
    p1.join()
    p2.join()

    print("All processes finished")
