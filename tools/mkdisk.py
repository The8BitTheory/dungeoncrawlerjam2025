#!/usr/bin/env python3
"""Build a Crawl 128 (1.1, dungeonboringengine 0.2, VDC-BASIC v3) disk image.

usage: mkdisk.py [--interp] [--d64 | --d81] [--rebuild-assets] [--rebuild-libs] [--no-bootsector] OUT

  --interp           the game on the disk is the tokenised source ($4001) instead of the Blitz! 128
                     compilation (runtime image 2, $4001)
  --d64 / --d81      image type (default: from the extension of OUT, else d81)
  --rebuild-assets   run crawlconv (engine repository) on the 1.0f disk and write art/dbe02/ again;
                     default: use the checked-in files in art/dbe02/
  --rebuild-libs     copy the engine binaries (build/dbe0.2.stub, build/dbe0.2.lib), VDCBASIC3 and the
                     boot loader (boot/boot.bas with line 50 RUN"CRAWL128") to libs/ again
  --no-bootsector    do not write the boot sector
  --bas FILE         BASIC source instead of game/crawl.bas (test builds with the test hook, test/patchbas.py)

Steps: bas2prg -> blitzc (not with --interp; the load address of c.prg must be $4001, runtime image 2)
-> disk with c1541: BOOT first (autostart loads the first file), vdcbasic3, crawl128, engine and assets,
crawl128.cd1 and the high-score file taken from the 1.0f disk, font.vrl and title.vrl from art/dbe02 -> boot sector (vdc-basic tools/mkboot.py).

Work directory: build/ (gitignored). Neighbour repositories: DBE_DIR (dungeonboringengine),
VDCBASIC_DIR (vdc-basic, branch v3), BLITZC (blitzc cli.js); node from NODE, PATH or ~/.nvm.
"""
import argparse, glob, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HOME = os.path.expanduser('~')
DBE = os.environ.get('DBE_DIR', os.path.join(HOME, 'git', 'dungeonboringengine'))
VB3 = os.environ.get('VDCBASIC_DIR', os.path.join(HOME, 'git', 'vdc-basic'))
BLITZ_RUNTIME = os.environ.get('BLITZ_RUNTIME', 'improved')   # original | fixed | improved
BLITZC = os.environ.get('BLITZC', os.path.join(HOME, 'git', 'blitz-compiler', 'blitz128', 'blitzc', 'js', 'cli.js'))
BUILD = os.path.join(ROOT, 'build')
ART = os.path.join(ROOT, 'art', 'dbe02')
LIBS = os.path.join(ROOT, 'libs')
DISK_1_0F = os.path.join(ROOT, 'crawl128-100f.d81')


def run(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        sys.exit('mkdisk: failed: ' + ' '.join(map(str, cmd)))
    return r


def find_node():
    n = os.environ.get('NODE') or shutil.which('node')
    if not n:
        c = sorted(glob.glob(os.path.join(HOME, '.nvm', 'versions', 'node', '*', 'bin', 'node')),
                   key=lambda p: [int(x) for x in p.split('/node/v')[1].split('/')[0].split('.')])
        n = c[-1] if c else None
    if not n:
        sys.exit('mkdisk: node not found (NODE)')
    return n


def tokenise_boot(dst):
    """VB3 boot/boot.bas with line 50 = RUN"CRAWL128", tokenised for $1C01."""
    src = open(os.path.join(VB3, 'boot', 'boot.bas')).read().splitlines()
    out = [l for l in src if not l.startswith('50 ')] + ['50 RUN"CRAWL128"']
    bas = os.path.join(BUILD, 'boot.bas')
    open(bas, 'w').write('\n'.join(out) + '\n')
    run([sys.executable, os.path.join(VB3, 'test', 'bastok.py'), bas, dst])


def rebuild_libs():
    for name in ('stub', 'lib'):
        shutil.copy(os.path.join(DBE, 'build', 'dbe0.2.' + name), os.path.join(LIBS, 'dbe0.2.%s.prg' % name))
    shutil.copy(os.path.join(VB3, 'vdcbasic3.bin'), os.path.join(LIBS, 'vdcbasic3.prg'))
    tokenise_boot(os.path.join(LIBS, 'boot.prg'))


def rebuild_assets():
    out = os.path.join(BUILD, 'assets')
    shutil.rmtree(out, ignore_errors=True)
    run([sys.executable, os.path.join(DBE, 'tools', 'crawlconv.py'), '--d81', DISK_1_0F, out])
    os.makedirs(ART, exist_ok=True)
    run([sys.executable, os.path.join(HERE, 'vrlpics.py'), '--d81', DISK_1_0F, ART])
    for f in sorted(os.listdir(out)):
        p = os.path.join(out, f)
        if os.path.isfile(p):
            shutil.copy(p, os.path.join(ART, f))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('--interp', action='store_true')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--d64', action='store_true')
    g.add_argument('--d81', action='store_true')
    ap.add_argument('--rebuild-assets', action='store_true')
    ap.add_argument('--rebuild-libs', action='store_true')
    ap.add_argument('--no-bootsector', action='store_true')
    ap.add_argument('--bas', default=os.path.join(ROOT, 'game', 'crawl.bas'))
    a = ap.parse_args()
    kind = 'd64' if a.d64 else 'd81' if a.d81 else ('d64' if a.out.endswith('.d64') else 'd81')

    os.makedirs(BUILD, exist_ok=True)
    if a.rebuild_libs:
        rebuild_libs()
    if a.rebuild_assets:
        rebuild_assets()

    bas = os.path.abspath(a.bas)
    tool = os.path.join(HERE, 'bas2prg.py')
    if a.interp:
        game = os.path.join(BUILD, 'crawl_4001.prg')
        run([sys.executable, tool, '--start', '0x4001', bas, game])
    else:
        src = os.path.join(BUILD, 'crawl_1c01.prg')
        run([sys.executable, tool, bas, src])
        bdir = os.path.join(BUILD, 'blitz')
        shutil.rmtree(bdir, ignore_errors=True)
        run([find_node(), BLITZC, src, bdir, '--runtime', BLITZ_RUNTIME, '--fastmath', 'off'])
        game = os.path.join(bdir, 'c.prg')
        if open(game, 'rb').read(2) != b'\x01\x40':
            sys.exit('mkdisk: c.prg does not start at $4001 (kein Image 2)')

    # the two files of the 1.0f disk that did not change
    old = os.path.join(BUILD, 'from100f')
    os.makedirs(old, exist_ok=True)
    for n in ('crawl128.cd1', 'greatestcrawl128,s'):
        run(['c1541', DISK_1_0F, '-read', n, os.path.join(old, n.split(',')[0])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    files = [  # (host file, name on disk)
        (os.path.join(LIBS, 'boot.prg'), 'boot'),
        (os.path.join(LIBS, 'vdcbasic3.prg'), 'vdcbasic3'),
        (game, 'crawl128'),
        (os.path.join(LIBS, 'dbe0.2.stub.prg'), 'dbe0.2.stub'),
        (os.path.join(LIBS, 'dbe0.2.lib.prg'), 'dbe0.2.lib'),
    ]
    for n in ('crawl.dmp', 'crawl.dvg', 'walls.dts'):
        files.append((os.path.join(ART, n), n))
    for n in sorted(glob.glob(os.path.join(ART, 'walls*.vrl'))):
        files.append((n, os.path.basename(n)))
    for n in ('ghost.s2', 'ghost.vrl', 'gem.s2', 'gem.vrl'):
        files.append((os.path.join(ART, n), n))
    files.append((os.path.join(old, 'crawl128.cd1'), 'crawl128.cd1'))
    for n in ('font.vrl', 'title.vrl'):
        files.append((os.path.join(ART, n), n))
    files.append((os.path.join(old, 'greatestcrawl128'), 'greatestcrawl128,s'))
    for h, _ in files:
        if not os.path.isfile(h):
            sys.exit('mkdisk: missing ' + h)

    if os.path.exists(a.out):
        os.unlink(a.out)
    cmd = ['c1541', '-format', 'crawl128-110,01', kind, a.out]
    for h, n in files:
        cmd += ['-write', h, n]
    run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not a.no_bootsector:
        bs = os.path.join(BUILD, 'bootsector.bin')
        run([sys.executable, os.path.join(VB3, 'tools', 'mkboot.py'), bs, '--name', 'BOOT',
             '--message', 'CRAWL 128', '--disk', a.out])
    print('%s: %s (%s)' % (a.out, 'interpreted' if a.interp else 'compiled', kind))


if __name__ == '__main__':
    main()
