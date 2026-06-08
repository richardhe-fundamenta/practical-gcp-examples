---
name: prime-factorizer
description: Compute the prime factorization of an integer by executing Python in the sandbox
when_to_use: When the user asks to factorize a number, find prime factors, or for a prime factorization
---

# Prime factorization

When the user asks for the prime factors (or prime factorization) of an integer N,
use your code execution tool to run Python in the sandbox. Substitute the user's
number for N, run this exactly:

```python
from collections import Counter

def prime_factors(n):
    n = int(n)
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

N = 360  # <-- replace with the user's number
pf = prime_factors(N)
c = Counter(pf)
pretty = " x ".join(f"{p}^{e}" if e > 1 else f"{p}" for p, e in sorted(c.items()))
print(f"{N} = {pretty}   (prime factors: {pf})")
```

Always actually execute the code in the sandbox (do not compute it in your head).
Your final reply MUST be the exact printed result line (for example:
`360 = 2^3 x 3^2 x 5   (prime factors: [2, 2, 2, 3, 3, 5])`). Do not reply with a
summary of your steps.
