"""Exact inclusive segmented sieve, executable as an uploaded PARCS Solver."""
import json
import math
import socket
import time

import Pyro4


def base_primes(limit):
    flags = bytearray(b'\x01') * (limit + 1)
    flags[:min(2, len(flags))] = b'\x00' * min(2, len(flags))
    for p in range(2, math.isqrt(limit) + 1):
        if flags[p]:
            flags[p*p:limit+1:p] = b'\x00' * ((limit-p*p)//p + 1)
    return [i for i, value in enumerate(flags) if value]


def sieve_range(lo, hi, primes, block_size=1000000, collect=False):
    """Keep at most block_size flags; optionally return every prime for small demos."""
    count, total, first, last, values = 0, 0, None, None, []
    for start in range(max(2, lo), hi + 1, block_size):
        end = min(hi, start + block_size - 1)
        flags = bytearray(b'\x01') * (end - start + 1)
        for p in primes:
            if p*p > end:
                break
            multiple = max(p*p, ((start+p-1)//p)*p)
            if multiple <= end:
                flags[multiple-start::p] = b'\x00' * ((end-multiple)//p+1)
        for offset, is_prime in enumerate(flags):
            if is_prime:
                value = start + offset
                count += 1
                total += value
                if first is None:
                    first = value
                last = value
                if collect:
                    values.append(value)
    result = dict(count=count, sum=total, first=first, last=last)
    if collect:
        result['primes'] = values
    return result


def partition(lo, hi, n):
    size = hi - lo + 1
    return [(lo + size*i//n, lo + size*(i+1)//n - 1) for i in range(n)]


def merge(parts, collect=False):
    nonempty = [part for part in parts if part['count']]
    result = dict(count=sum(p['count'] for p in parts),
                  sum=sum(p['sum'] for p in parts),
                  first=nonempty[0]['first'] if nonempty else None,
                  last=nonempty[-1]['last'] if nonempty else None)
    if collect:
        result['primes'] = [v for part in parts for v in part['primes']]
    return result


class Solver:
    def __init__(self, workers=None, input_file_name=None, output_file_name=None):
        self.workers = workers or []
        self.input_file_name = input_file_name
        self.output_file_name = output_file_name

    @staticmethod
    @Pyro4.expose
    def mymap(lo, hi, primes, block_size, collect):
        result = sieve_range(lo, hi, primes, block_size, collect)
        return dict(result=result, hostname=socket.gethostname(), lo=lo, hi=hi)

    def solve(self):
        with open(self.input_file_name) as source:
            config = json.load(source)
        lo, hi = int(config['lo']), int(config['hi'])
        n = int(config.get('workers', 0))
        block_size = int(config.get('block_size', 1000000))
        collect = bool(config.get('collect', False))
        if lo < 0 or hi < lo or block_size < 1 or not 0 <= n <= len(self.workers):
            raise ValueError('Invalid range, block size or worker count')
        if collect and hi-lo+1 > 1000000:
            raise ValueError('collect mode is limited to one million integers')
        started = time.perf_counter()
        primes = base_primes(math.isqrt(hi))
        if n == 0:
            parts = [dict(result=sieve_range(lo, hi, primes, block_size, collect),
                          hostname=socket.gethostname(), lo=lo, hi=hi)]
        else:
            # Dispatch ALL async calls before waiting; workers actually overlap.
            futures = [worker.mymap(a, b, primes, block_size, collect)
                       for worker, (a, b) in zip(self.workers[:n], partition(lo, hi, n))]
            parts = [future.value for future in futures]
        result = merge([p['result'] for p in parts], collect)
        elapsed = time.perf_counter() - started
        output = dict(config=config, seconds=elapsed, result=result,
                      master=socket.gethostname(), partitions=parts)
        with open(self.output_file_name, 'w') as target:
            json.dump(output, target, indent=2)
