import math
import random
import unittest
from lab.prime_solver import base_primes, sieve_range, partition, merge


def reference(lo, hi):
    return [v for v in range(max(2,lo), hi+1)
            if all(v%d for d in range(2, math.isqrt(v)+1))]


class SieveTests(unittest.TestCase):
    def test_random_boundaries_and_partitions(self):
        rng = random.Random(19)
        for _ in range(100):
            lo = rng.randrange(0, 2000)
            hi = lo + rng.randrange(0, 250)
            primes = base_primes(math.isqrt(hi))
            expected = reference(lo,hi)
            for n in range(1,5):
                parts = [sieve_range(a,b,primes,17,True) for a,b in partition(lo,hi,n)]
                result = merge(parts,True)
                self.assertEqual(result['primes'], expected)
                self.assertEqual(result['sum'], sum(expected))
                self.assertEqual(result['count'], len(expected))

    def test_known_count(self):
        result = sieve_range(0,1000000,base_primes(1000))
        self.assertEqual(result['count'],78498)
        self.assertEqual(result['sum'],37550402023)


if __name__ == '__main__':
    unittest.main()
