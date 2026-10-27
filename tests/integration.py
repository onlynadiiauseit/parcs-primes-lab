"""Local separate-process PARCS smoke test; not a cloud benchmark."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import requests
from lab.benchmark import run_job

os.environ['NO_PROXY']='*'
root = Path(__file__).resolve().parents[1]
processes, logs = [], []
try:
    for i in range(5):
        log = tempfile.TemporaryFile(mode='w+')
        logs.append(log)
        args = [sys.executable,'start.py','-ip','127.0.0.1','-port',str(18080+i)]
        if i:
            args += ['-master_ip','127.0.0.1','-master_port','18080']
        processes.append(subprocess.Popen(args,cwd=root,stdout=log,stderr=log, env={**os.environ, "PARCS_RPC_PORT": str(19090+i)}))
    url='http://127.0.0.1:18080'
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        try:
            r=requests.get(url+'/api/worker',timeout=2)
            if len(r.json()['workers'])==4:
                break
        except requests.RequestException:
            pass
        time.sleep(.3)
    else:
        raise RuntimeError('Workers did not register')
    for page in ['/', '/workers','/jobs','/add_job']:
        requests.get(url+page).raise_for_status()
    for n in range(5):
        result=run_job(url,dict(lo=0,hi=1000000,workers=n),timeout=45)
        assert result['result']['count']==78498, result
        assert result['result']['sum']==37550402023, result
        assert len(result['partitions'])==max(1,n)
        print(f'PASS: PARCS job N={n}, count=78498',flush=True)
    for n in range(5):
        result=run_job(url,dict(lo=0,hi=10,workers=n,collect=True),timeout=45)
        assert result['result']['primes']==[2,3,5,7]
    print('PASS: exact prime lists, all modes')
except Exception:
    for i,log in enumerate(logs):
        log.seek(0)
        print(f'NODE {i}:\n'+log.read()[-10000:])
    raise
finally:
    for p in processes:
        p.terminate()
    for p in processes:
        p.wait(timeout=10)
    for log in logs:
        log.close()
