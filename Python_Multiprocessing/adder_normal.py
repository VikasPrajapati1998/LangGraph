import time

start_time = time.time()

total = 0
for i in range(1, 10000000000):
    total += i

print("Sum:", total)

end_time = time.time()
print("Execution Time:", end_time - start_time, "seconds")

