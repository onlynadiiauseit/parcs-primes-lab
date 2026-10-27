"""Submit actual PARCS jobs; save raw evidence, CSV and an SVG chart."""
import argparse
import csv
import io
import json
from pathlib import Path
import random
import statistics
import time

import requests


def run_job(url, config, timeout=7200):
    with Path(__file__).with_name('prime_solver.py').open('rb') as solver:
        response = requests.post(url+'/api/job', data={'job_name': f"PRIMES N={config['workers']}"},
            files={'solution_file': ('solution.py', solver),
                   'input_file': ('input.json', io.BytesIO(json.dumps(config).encode()))}, timeout=30)
    response.raise_for_status()
    job_id = response.json()['job_id']
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = requests.get(f'{url}/api/job/{job_id}', timeout=30)
        response.raise_for_status()
        status = response.json()
        if status['ended']:
            if status['failed']:
                raise RuntimeError(status)
            response = requests.get(f'{url}/api/job/{job_id}/output', timeout=60)
            response.raise_for_status()
            # Scheduler cleans up RPC servers after marking a job ended.
            return response.json()
        time.sleep(0.2)
    raise TimeoutError(f'PARCS job {job_id} exceeded {timeout} seconds')


def plot(rows, path):
    # Self-contained standard SVG; no plotting package needed in Cloud Shell.
    maximum = max(r['median_seconds'] for r in rows) * 1.15
    def y(value):
        return 330 - 260*value/maximum
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="430" viewBox="0 0 800 430">',
           '<rect width="800" height="430" fill="white"/>',
           '<g font-family="sans-serif" font-size="15" fill="#172b4d">',
           '<text x="90" y="30">PARCS: час виконання (медіана), с</text>']
    for i in range(6):
        value = maximum*i/5
        yy = y(value)
        out += [f'<path d="M90 {yy} H760" stroke="#ddd"/>',
                f'<text x="10" y="{yy+5}">{value:.3f}</text>']
    points = []
    for i, row in enumerate(rows):
        x = 120+i*150
        yy = y(row['median_seconds'])
        label = 'Послідовно' if row['workers']==0 else str(row['workers'])
        out += [f'<circle cx="{x}" cy="{yy}" r="5" fill="#2563eb"/>',
                f'<text x="{x}" y="{yy-12}" text-anchor="middle">{row["median_seconds"]:.3f}</text>',
                f'<text x="{x}" y="365" text-anchor="middle">{label}</text>']
        if row['workers']:
            points.append(f'{x},{yy}')
    out += [f'<polyline points="{" ".join(points)}" fill="none" stroke="#2563eb" stroke-width="2"/>',
            '<text x="310" y="410">Кількість воркерів</text></g></svg>']
    path.write_text('\n'.join(out), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    parser.add_argument('--lo', type=int, default=2)
    parser.add_argument('--hi', type=int, default=100000000)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--out', default='results/cloud')
    args = parser.parse_args()
    if args.repeats < 1 or args.lo < 0 or args.hi < args.lo:
        parser.error('Invalid repeats or range')
    output = Path(args.out)
    if (output/'raw.json').exists():
        parser.error('Output already contains results; choose a new --out directory')
    output.mkdir(parents=True, exist_ok=True)
    response = requests.get(args.url+'/api/worker', timeout=30)
    response.raise_for_status()
    workers = response.json()['workers']
    if len(workers) != 4 or not all(w['enabled'] for w in workers):
        raise RuntimeError('Exactly 4 enabled PARCS workers are required')
    (output/'workers.json').write_text(json.dumps(workers, indent=2))
    # Correctness demo returns every prime, so count-only bugs cannot pass unnoticed.
    expected = [2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61,67,71,73,79,83,89,97]
    for n in range(5):
        demo = run_job(args.url, dict(lo=0, hi=100, workers=n, collect=True))
        assert demo['result']['primes'] == expected, demo
        (output/f'demo-{n}.json').write_text(json.dumps(demo, indent=2))
    records, baseline = [], None
    modes = list(range(5))
    rng = random.Random(42)
    for repeat in range(1, args.repeats+1):
        rng.shuffle(modes)
        for n in modes:
            result = run_job(args.url, dict(lo=args.lo, hi=args.hi, workers=n, block_size=1000000))
            if baseline is None:
                baseline = result['result']
            if result['result'] != baseline:
                raise RuntimeError('Sequential/parallel result mismatch')
            hosts = [p['hostname'] for p in result['partitions']]
            if n and len(set(hosts)) != n:
                raise RuntimeError('Parallel partitions must run on distinct worker hosts')
            record = dict(repeat=repeat, workers=n, **result)
            records.append(record)
            (output/'raw.json').write_text(json.dumps(records, indent=2))
            print(f"repeat={repeat} workers={n} seconds={result['seconds']:.6f} count={baseline['count']} hosts={hosts}", flush=True)
    serial = statistics.median(r['seconds'] for r in records if r['workers']==0)
    rows = []
    for n in range(5):
        samples = [r['seconds'] for r in records if r['workers']==n]
        median = statistics.median(samples)
        rows.append(dict(workers=n, median_seconds=median, min_seconds=min(samples),
                         max_seconds=max(samples), speedup=serial/median,
                         efficiency=serial/median/n if n else '', count=baseline['count']))
    with (output/'summary.csv').open('w', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plot(rows, output/'timing.svg')
    lines = ['| Режим | Медіана, с | Прискорення |', '|---|---:|---:|']
    for row in rows:
        mode = 'Послідовний' if row['workers']==0 else f"{row['workers']} worker"
        lines.append(f"| {mode} | {row['median_seconds']:.6f} | {row['speedup']:.3f} |")
    (output/'table.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
    print(f'Files saved in {output}')


if __name__ == '__main__':
    main()
