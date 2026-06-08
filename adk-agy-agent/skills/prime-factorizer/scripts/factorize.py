#!/usr/bin/env python3
"""CLI: python factorize.py <int> — prints the prime factorization."""
import sys
from collections import Counter


def prime_factors(n: int) -> list[int]:
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors


if __name__ == "__main__":
    n = int(sys.argv[1])
    pf = prime_factors(n)
    c = Counter(pf)
    pretty = " x ".join(f"{p}^{e}" if e > 1 else f"{p}" for p, e in sorted(c.items()))
    print(f"{n} = {pretty}   (prime factors: {pf})")
