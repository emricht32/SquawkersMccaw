"""This module contains the implementation of a function to calculate Fibonacci numbers.
The fib(n) function calculates the nth Fibonacci number using an iterative approach for efficiency.
"""

def fib(n):
    if n <= 1:
        return n
    previous, current = 0, 1
    for _ in range(2, n + 1):
        previous, current = current, previous + current
    return current

if __name__ == "__main__":
    print(fib(10))
