#!/usr/bin/env python3
"""Z64K timedemo runs (P7d, docs/specs/P7-crawl.md 7.3): {1.0f, 1.1} compiled x {2 MHz, 1 MHz} (+ --interp).

usage: test/z64k_crawl.py [--only 110|100f] [--interp] [--reps N] [--out DIR] [--jobs N]

Builds the timedemo sources (test/patchbas.py --timedemo [--slow]), compiles them with Blitz! (1.0f: replaces
`crawl128` on a copy of crawl128-100f.d64; 1.1: tools/mkdisk.py --d64 --bas), runs each in Z64K (VB3 test/z64k.py:
own Xvfb, event = process end via the debugcart $D7FF, -limitcycles/timeout only guards) with -8 DISK -autoload BOOT,
reads the file TIMES (jiffies T9) from the saved d64 (`c1541 -read times`). Results: build/z64k/z64k.json.
Jiffies per second: measured in VICE (vice_crawl.py --timing, field ti_calib: TI ($A0-$A2) over 20 IRQs of known
stopwatch length; result 1.2 jiffies per VIC frame = 60.15/s). Z64K is assumed to use the same KERNAL jiffy logic.
"""
import argparse, concurrent.futures as cf, hashlib, json, os, shutil, subprocess, sys, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VB3 = os.environ.get('VDCBASIC_DIR', os.path.expanduser('~/git/vdc-basic'))
sys.path.insert(0, os.path.join(VB3, 'test'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import z64k

D64_1_0F = os.path.join(ROOT, 'crawl128-100f.d64')


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f'build failed: {" ".join(map(str, cmd))}\n{r.stdout}{r.stderr}')
    return r


def build(work, ver, slow, interp):
    """-> (d64, autoload prg)"""
    import mkdisk
    tag = f'{ver}-{"interp" if interp else "comp"}-{"1mhz" if slow else "2mhz"}'
    src = os.path.join(work, f'src_{ver}.bas')
    if ver == '100f':
        open(src, 'w', encoding='utf-8').write(sh(['git', '-C', ROOT, 'show', 'main:game/crawl.bas']).stdout)
    else:
        shutil.copy(os.path.join(ROOT, 'game', 'crawl.bas'), src)
    td = os.path.join(work, f'td_{tag}.bas')
    sh([sys.executable, os.path.join(HERE, 'patchbas.py'), '--timedemo'] + (['--slow'] if slow else []) + [src, td])
    d64 = os.path.join(work, f'td_{tag}.d64')
    if ver == '100f':
        prg = os.path.join(work, f'td_{tag}.prg')
        sh([sys.executable, os.path.join(ROOT, 'tools', 'bas2prg.py'), td, prg])
        if not interp:
            bd = os.path.join(work, f'td_{tag}_bl')
            shutil.rmtree(bd, ignore_errors=True)
            sh([mkdisk.find_node(), mkdisk.BLITZC, prg, bd, '--runtime', 'improved', '--fastmath', 'off'])
            prg = os.path.join(bd, 'c.prg')
        shutil.copy(D64_1_0F, d64)
        sh(['c1541', d64, '-delete', 'crawl128', '-write', prg, 'crawl128'])
    else:
        sh([sys.executable, os.path.join(ROOT, 'tools', 'mkdisk.py'), '--bas', td, '--d64'] + (['--interp'] if interp else []) + [d64])
    return tag, d64


def one(tag, d64, rep, work, timeout, limit):
    saved = os.path.join(work, f'saved_{tag}_{rep}.d64')
    if os.path.exists(saved):
        os.remove(saved)
    # autoload the disk itself (boot sector / first file), see the report if that does not work
    r = z64k.run(d64, d64=d64, limit=limit, timeout=timeout, save=saved, log=os.path.join(work, f'z64k_{tag}_{rep}.log'))
    t9 = None
    if r.image:
        out = os.path.join(work, f'times_{tag}_{rep}')
        if os.path.exists(out):
            os.remove(out)
        subprocess.run(['c1541', r.image, '-read', 'times,s', out], capture_output=True)
        if os.path.exists(out):
            txt = open(out, 'rb').read().decode('latin1').strip()
            try:
                t9 = int(txt.split()[0])
            except ValueError:
                t9 = None
    print(f'{tag} rep {rep}: rc {r.rc}, T9 {t9}, {r.secs:.0f} s', flush=True)
    return dict(tag=tag, rep=rep, rc=r.rc, t9=t9, secs=r.secs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=None)
    ap.add_argument('--interp', action='store_true')
    ap.add_argument('--reps', type=int, default=1)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--timeout', type=int, default=1500)
    ap.add_argument('--limit', type=int, default=4_000_000_000)
    ap.add_argument('--out', default=os.path.join(ROOT, 'build', 'z64k'))
    a = ap.parse_args()
    work = os.path.abspath(a.out)
    os.makedirs(work, exist_ok=True)
    lib = os.path.join(ROOT, 'libs', 'dbe0.2.lib.prg')
    info = dict(size=os.path.getsize(lib), sha256=hashlib.sha256(open(lib, 'rb').read()).hexdigest())
    jobs = []
    for ver in ('100f', '110'):
        if a.only and a.only != ver:
            continue
        for slow in (False, True):
            tag, d64 = build(work, ver, slow, a.interp)
            for r in range(a.reps):
                jobs.append((tag, d64, r))
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        res = list(ex.map(lambda j: one(*j, work, a.timeout, a.limit), jobs))
    fn = os.path.join(work, 'z64k.json' if not a.only else f'z64k_{a.only}.json')
    json.dump(dict(runs=res, lib=info), open(fn, 'w'), indent=1)
    return 0 if all(r['t9'] is not None for r in res) else 1


if __name__ == '__main__':
    sys.exit(main())
