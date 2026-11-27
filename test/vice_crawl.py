#!/usr/bin/env python3
"""Pixel test of Crawl 128 1.1 against 1.0f (P7c, docs/specs/P7-crawl.md 6.3).

usage: test/vice_crawl.py --timing [--ports 6641,6642] [--reps 2] [--configs LIST] [--record NAME] [--out DIR]   (P7d, see timing_main;
                          measures 1.1 only and compares with test/timing-results.json, --configs 100f-... measures 1.0f)
       test/vice_crawl.py [--runs ref,orig,interp,comp] [--ports 6637,6638] [--reuse] [--control]
                          [--out DIR] [--timeout S] [--no-build] [--scenes-only | --walk-only]

Runs (each in VICE x128 -80col -VDC64KB -warp, disk by -8 and -autostart, own monitor port):
  ref     1.0f compiled, rebuilt from `git show main:game/crawl.bas` + test hook (test/patchbas.py)   = reference
  orig    1.0f compiled, the original of crawl128-100f.d81 without hook (walk only; shows whether the rebuild
          and the hook change the pictures)
  interp  1.1 interpreted + hook (tools/mkdisk.py --interp --bas)
  comp    1.1 compiled + hook
Each run: menu (RETURN), start picture, the 39 keys of the walk, M (automap) and any key, then the scenes
(ghost positions through the hook, 32 scenes, computed from the map). At every game prompt (GETIN with an empty
keyboard buffer, two interrupts later) the VDC RAM [0,9600) and [46335,65535) and the registers 0-36 are saved
(`bank vdc`, `bsave`; `io d600`). Event driven: breakpoints on GETIN ($FFE4), on the BASIC error vector
(($0300)) and on the IRQ vector; --timeout and -limitcycles are only guards. No sleeps.
Prompt recognition: the BASIC line $3B/$3C when the program keeps it (interpreted: 5 = disk prompt -> space,
3560-3630 menu -> RETURN, 4040 game, 6710/6720 automap); the Blitz! compilation does not keep it, there the order
holds: first prompt = menu (RETURN), every further prompt is a game prompt (the menu GET loop is not called again).

Checks (compare phase, all on the saved dumps):
  1. interp and comp equal ref at every prompt (VRAM + registers; walk, automap, scenes)
  2. orig equals ref in the walk
  3. crawl01 (engine repository, model of VIEW 0.1) equals the real 1.0f window (rows 5-99 and, where the model
     writes, row 100; columns 6-73) at every prompt with the position/ghost recorded by the hook
  4. automap: the map area at the M prompt is the whole map (1.0f behaviour, AM%=0): expected bytes from the map
     (free 255, wall $11), blinking player marker excluded
  5. no BASIC error
--control: one byte of the reference dump is falsified; exactly this picture must be reported.
Port rule: --ports, else DBE_VICE_PORT (6631-6649), bind check; only the own VICE processes are ended.
Exit code 0 = all checks green.
"""
import argparse, concurrent.futures as cf, os, pickle, re, shutil, subprocess, sys, time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VB3 = os.environ.get('VDCBASIC_DIR', os.path.expanduser('~/git/vdc-basic'))
DBE = os.environ.get('DBE_DIR', os.path.expanduser('~/git/dungeonboringengine'))
sys.path.insert(0, os.path.join(VB3, 'test'))
sys.path.insert(0, os.path.join(DBE, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import vicemon as vm

WALK = 'WWEWWEWWQWWQWWQWWWWWQAAAAAEAAWWWWWQWWWQ'
R0, R1 = (0, 9600), (46335, 65535)           # compared VDC RAM ranges
HOOK_IN, HOOK_OUT = 0x0C44, 0x0CC0
MAPADDR, EI = 20 * 80 + 12, 80               # automap on the screen (crawl.bas 6600)
# Pointer registers that legitimately differ and are constant over the run: R14/R15 text cursor address (cursor
# off, R10 = $A0; moved by the PRINT output of the loader, which may differ, spec 4.3 no. 4), R32/R33 block copy
# source (last copy of the loader/HUD set-up; each copy sets it first). Reported as "tolerated".
POINTER_REGS = (14, 15, 32, 33)
DISK_1_0F = os.path.join(ROOT, 'crawl128-100f.d81')
# VRAM areas checked at the menu prompt: visible screen/title, title picture (TA = 9600, 2338 bytes), font (CA = 19200, 1730 bytes)
MENU_AREAS = dict(screen=(0, 9600), title=(9600, 9600 + 2338), font=(19200, 19200 + 1730))


# ---------------------------------------------------------------- builds

def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        sys.exit(f'build failed: {" ".join(map(str, cmd))}\n{r.stdout}{r.stderr}')
    return r


def node():
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import mkdisk
    return mkdisk.find_node(), mkdisk.BLITZC


def build_all(work, verbose=True):
    """Hooked disks for ref, interp, comp; returns {name: disk} and notes on the 1.0f rebuild."""
    os.makedirs(work, exist_ok=True)
    disks, notes = {}, {}
    # 1.0f reference
    src = os.path.join(work, 'crawl_100f.bas')
    open(src, 'w', encoding='utf-8').write(sh(['git', '-C', ROOT, 'show', 'main:game/crawl.bas']).stdout)
    hk = os.path.join(work, 'crawl_100f_hook.bas')
    sh([sys.executable, os.path.join(HERE, 'patchbas.py'), src, hk])
    nd, blitzc = node()
    import mkdisk

    def compile_(bas, tag):
        prg = os.path.join(work, tag + '.prg')
        sh([sys.executable, os.path.join(ROOT, 'tools', 'bas2prg.py'), bas, prg])
        bd = os.path.join(work, tag + '_bl')
        shutil.rmtree(bd, ignore_errors=True)
        sh([nd, blitzc, prg, bd, '--runtime', mkdisk.BLITZ_RUNTIME, '--fastmath', 'off'])
        return os.path.join(bd, 'c.prg')

    plain = compile_(src, 'ref_plain')
    orig = os.path.join(work, 'orig.prg')
    sh(['c1541', DISK_1_0F, '-read', 'crawl128', orig])
    a, b = open(plain, 'rb').read(), open(orig, 'rb').read()
    notes['rebuild_1.0f_identical'] = a == b
    notes['rebuild_sizes'] = (len(a), len(b))
    hooked = compile_(hk, 'ref_hook')
    d = os.path.join(work, 'ref.d81')
    shutil.copy(DISK_1_0F, d)
    # same file order as the original: crawl128 is the first file; delete + write puts it in the freed slot
    sh(['c1541', d, '-delete', 'crawl128', '-write', hooked, 'crawl128'])
    ls = sh(['c1541', d, '-list']).stdout
    first = [l for l in ls.splitlines() if l.strip().startswith(('86 ', '87 ', '88 ', '89 ', '9'))]
    notes['ref_first_file'] = [l for l in ls.splitlines() if '"' in l][1:2]
    disks['ref'] = d
    disks['orig'] = DISK_1_0F
    # 1.1
    h11 = os.path.join(work, 'crawl_110_hook.bas')
    sh([sys.executable, os.path.join(HERE, 'patchbas.py'), os.path.join(ROOT, 'game', 'crawl.bas'), h11])
    for name, extra in (('interp', ['--interp']), ('comp', [])):
        d = os.path.join(work, name + '.d81')
        sh([sys.executable, os.path.join(ROOT, 'tools', 'mkdisk.py'), '--bas', h11, *extra, d])
        disks[name] = d
    return disks, notes


# ---------------------------------------------------------------- one VICE run

def regs_of(m):
    t = m.cmd('io d600')
    sec = t.split('VDC Internal Registers:')[1]
    vals = []
    for l in sec.splitlines():
        mm = re.match(r'\s*([0-9a-f]{2}):((?:\s+[0-9a-f]{2})+)\s*$', l)
        if mm:
            vals += [int(x, 16) for x in mm.group(2).split()]
    if len(vals) < 37:
        raise RuntimeError('VDC registers not parsed: ' + sec[:200])
    return vals[:37]


def drive(name, disk, port, scenes, keys, tmo, out):
    """-> dict(prompts=[...], errors=[...], info...). prompt = dict(tag, key, line, vram, regs, hook)"""
    res = dict(name=name, prompts=[], errors=[], interp=None)
    os.makedirs(out, exist_ok=True)
    tmpf = os.path.join(out, 'vram.tmp')

    def word(m, a):
        b = m.mem(a, 2)
        return b[0] | b[1] << 8

    def script(m):
        err_at = None                               # vectors are set up by the system after the reset
        bp_get = m.bp(0xFFE4)
        bp_irq = None

        def line():
            return word(m, 0x3B)

        def wait_prompt():
            nonlocal err_at
            while True:
                pc, _ = m.go()
                if pc == err_at:
                    res['errors'].append(f'BASIC error in line {line()}, X={m.reg_x()}')
                    raise RuntimeError(res['errors'][-1])
                if pc == 0xFFE4 and m.mem(0xD0)[0] == 0:
                    return

        def feed(ch):
            m.cmd(f'> 034a {ord(ch):02x}')
            m.cmd('> 00d0 01')

        def settle():
            nonlocal bp_irq
            if bp_irq is None:
                bp_irq = m.bp(word(m, 0x314))
            m.cmd(f'disable {bp_get}')
            m.cmd(f'enable {bp_irq}')
            for _ in range(2):
                pc, _ = m.go()
                if pc == err_at:
                    raise RuntimeError('BASIC error while settling')
            m.cmd(f'disable {bp_irq}')
            m.cmd(f'enable {bp_get}')

        def dump(tag, key):
            settle()
            hk = m.mem(HOOK_OUT, 6)
            ln = line()
            m.cmd('bank vdc')
            m.cmd(f'bsave "{tmpf}" 0 0000 ffff')
            m.cmd('bank default')
            v = open(tmpf, 'rb').read()
            print(f'  {name}: {tag} line {ln} hook {hk}', flush=True)
            os.unlink(tmpf)
            if len(v) < 0x10000:
                raise RuntimeError('VRAM dump too short: %d' % len(v))
            res['prompts'].append(dict(tag=tag, key=key, line=ln, regs=regs_of(m), full=None,
                                       vram=v[R0[0]:R0[1]] + v[R1[0]:R1[1]], hook=(hk[0] | hk[1] << 8, hk[2],
                                                                                  hk[3] | hk[4] << 8, hk[5])))

        wait_prompt()
        err_at = word(m, 0x300)                     # BASIC error vector (initialised now)
        m.bp(err_at)
        res['interp'] = line() == 5
        if res['interp']:
            feed(' ')
            wait_prompt()                           # menu
        # menu prompt: title and font in the invisible VRAM and the visible title (R0), all must equal 1.0f
        m.cmd('bank vdc')
        m.cmd(f'bsave "{tmpf}" 0 0000 ffff')
        m.cmd('bank default')
        v = open(tmpf, 'rb').read()
        os.unlink(tmpf)
        res['menu'] = dict((k, v[a:b]) for k, (a, b) in MENU_AREAS.items())
        m.cmd('> 0c44 00')                          # hook off
        feed('\r')
        wait_prompt()                               # game prompt, start picture
        if res['interp'] and line() != 4040:
            res['errors'].append(f'expected line 4040, found {line()}')
        dump('start', '')
        for i, k in enumerate(keys, 1):
            feed(k)
            wait_prompt()
            dump(f'walk{i:02d}', k)
        if scenes is not None:
            feed('M')
            wait_prompt()
            dump('map', 'M')
            feed(' ')
            wait_prompt()
            dump('after_map', ' ')
            for i, sc in enumerate(scenes):
                p, d, g, gd = sc['pose']
                for k, b in enumerate((165, p & 255, p >> 8, d, g & 255, g >> 8, gd)):
                    m.cmd(f'> {HOOK_IN + k:04x} {b:02x}')
                feed(' ')
                wait_prompt()
                dump(f'scene{i:02d}', ' ')
        m.cmd(f'screenshot "{os.path.join(out, "last.png")}" 2')
        m.s.sendall(b'quit\n')                     # own VICE process only
        return 0

    try:
        vm.run_vice(['-default', '-80col', '-VDC64KB', '-warp', '-sounddev', 'dummy', '-8', disk, '-autostart', disk,
                     '-limitcycles', '4000000000'], port, tmo, script)
    except (RuntimeError, vm.Exited, TimeoutError) as e:
        res['errors'].append('run aborted: ' + repr(e))
    return res


# ---------------------------------------------------------------- scenes from the map

def make_env(work):
    import crawl01
    import crawlconv
    d = os.path.join(work, 'in')
    files = crawlconv.read_d81(DISK_1_0F, d)
    return crawl01.Env(files), crawl01


def collected_cells(env, hooks):
    """Cell values after the given hook positions (gem on the player cell is taken, exit opens)."""
    import dbemap
    cells = list(env.cells0)
    ex = [e.cell for e in env.m.events if e.type == dbemap.EVENT_TYPES['exit']]
    left = sum(1 for c in cells if c == 2)
    for pos in hooks:
        if cells[pos] == 2:
            cells[pos] = 0
            left -= 1
            if left <= 0:
                for x in ex:
                    cells[x] = 42
    return cells


def make_scenes(env, cells):
    """32 scenes: list of dict(label, pose=(player, dir, ghostcell, ghostdir)). Poses from the map after the walk."""
    w, h = env.w, env.h
    FORE = ((0, -1), (1, 0), (0, 1), (-1, 0))
    RIGHT = ((1, 0), (0, 1), (-1, 0), (0, -1))

    def cell(pos, v, d, s):
        x, y = pos % w + d * FORE[v][0] + s * RIGHT[v][0], pos // w + d * FORE[v][1] + s * RIGHT[v][1]
        return y * w + x if 0 <= x < w and 0 <= y < h else None

    def kind(c):
        return None if c is None else ('wall' if cells[c] & 1 else 'gem' if cells[c] == 2 else 'free')

    poses = [(p, v) for p in range(w * h) for v in range(4) if kind(p) in ('free', 'gem') and cells[p] != 40]

    def score(p, v):
        return sum(kind(cell(p, v, d, s)) in ('free', 'gem') for d in range(1, 4) for s in (-1, 0, 1))

    out = []

    def pick(ok):
        c = [(score(p, v), -p, -v, p, v) for p, v in poses if ok(p, v)]
        if not c:
            return None
        c.sort(reverse=True)
        return c[0][3], c[0][4]

    for d in (1, 2):
        for s in (-1, 0, 1):
            pv = pick(lambda p, v: kind(cell(p, v, d, s)) in ('free', 'gem'))
            for gd in range(4):
                out.append(dict(label=f'ghost d={d} s={s:+d} dir={gd}', pose=(pv[0], pv[1], cell(pv[0], pv[1], d, s), gd)))
    for d, s in ((1, 0), (1, 1), (1, -1), (2, 1), (2, -1)):
        pv = pick(lambda p, v: kind(cell(p, v, d, s)) == 'gem')
        out.append(dict(label=f'ghost on gem d={d} s={s:+d}', pose=(pv[0], pv[1], cell(pv[0], pv[1], d, s), (pv[1] + 2) & 3)))
    pv = pick(lambda p, v: kind(cell(p, v, 0, 1)) == 'wall' and kind(cell(p, v, 1, 1)) in ('free', 'gem'))
    out.append(dict(label='ghost (1,+1), side wall (0,+1) in front', pose=(pv[0], pv[1], cell(pv[0], pv[1], 1, 1), (pv[1] + 3) & 3)))
    pv = pick(lambda p, v: kind(cell(p, v, 1, 0)) == 'wall' and kind(cell(p, v, 1, -1)) in ('free', 'gem'))
    out.append(dict(label='ghost (1,-1) behind front (1,0)', pose=(pv[0], pv[1], cell(pv[0], pv[1], 1, -1), (pv[1] + 1) & 3)))
    pv = pick(lambda p, v: all(kind(cell(p, v, d, 0)) in ('free', 'gem') for d in (1, 2, 3)))
    out.append(dict(label='ghost d=3 (invisible)', pose=(pv[0], pv[1], cell(pv[0], pv[1], 3, 0), (pv[1] + 2) & 3)))
    return out


# ---------------------------------------------------------------- compare

def unmark(vram, pos, w):
    """blank the blinking player marker of the automap (2 bytes)"""
    v = bytearray(vram)
    a = MAPADDR + (pos // w) * EI + (pos % w) * 2
    v[a] = v[a + 1] = 0
    return bytes(v)


def compare(runs, scenes, env, crawl01, control=None, log=print):
    problems = []
    ref = runs['ref']['prompts']
    if control is not None:
        p = dict(ref[control])
        v = bytearray(p['vram'])
        v[1234] ^= 1
        p['vram'] = bytes(v)
        ref = list(ref)
        ref[control] = p
    rep = {}
    tol = {}
    # 1/2: runs against ref
    for name in ('interp', 'comp', 'orig'):
        r = runs.get(name)
        if not r:
            continue
        bad, n = [], 0
        for i, p in enumerate(r['prompts']):
            if i >= len(ref):
                break
            q = ref[i]
            n += 1
            a, b = p['vram'], q['vram']
            ra, rb = p['regs'], q['regs']
            if p['tag'] == 'map':
                if name == 'orig':
                    continue
                a, b = unmark(a, p['hook'][0], env.w), unmark(b, q['hook'][0], env.w)
            d = [k for k in range(len(a)) if a[k] != b[k]]
            rd = [k for k in range(37) if ra[k] != rb[k] and k not in POINTER_REGS]
            for k in range(37):
                if ra[k] != rb[k] and k in POINTER_REGS:
                    tol.setdefault((name, k), set()).add((rb[k], ra[k]))
            hd = p['hook'] != q['hook'] if name != 'orig' else False
            if d or rd or hd:
                bad.append((i, p['tag'], len(d), d[:3], rd, p['hook'], q['hook'] if hd else None))
        rep[name] = (n, bad)
        if len(r['prompts']) != len(ref) and name != 'orig':
            problems.append(f'{name}: {len(r["prompts"])} prompts, ref {len(ref)}')
        if name == 'orig':
            nw = min(len(r['prompts']), 40)
            bad = [b for b in bad if b[0] < nw]
        for b in bad:
            problems.append(f'{name} != ref at prompt {b[0]} ({b[1]}): {b[2]} VRAM bytes {b[3]}, registers {b[4]}')
        log(f'{name}: {n} prompts compared with ref, {len(bad)} differ')
    for (name, k), vals in sorted(tol.items()):
        log(f'tolerated: {name} register {k} differs from ref: (ref, {name}) = {sorted(vals)}'
            + ('' if len(vals) == 1 else '  CHANGES between prompts'))
        if len(vals) > 1:
            problems.append(f'{name}: register {k} (pointer register) is not constant')
    # 2b: menu prompt: visible title, title picture and font in VRAM equal 1.0f (ref run and the raw files of the 1.0f disk)
    import tempfile
    exp_menu = {}
    with tempfile.TemporaryDirectory() as t:
        for key, fn in (('title', 'title.vdc'), ('font', 'font3o.vdc')):
            f = os.path.join(t, fn)
            sh(['c1541', DISK_1_0F, '-read', fn, f])
            exp_menu[key] = open(f, 'rb').read()[2:]
    for name in ('ref', 'orig', 'interp', 'comp'):
        mn = runs.get(name, {}).get('menu')
        if not mn:
            continue
        bad = []

        def masked(key, data):                      # the version text on the menu ("1.0" / "1.1", rows 93-97, columns 72-79) differs by intent
            d = bytearray(data)
            if key == 'screen':
                for r_ in range(93, 98):
                    d[r_ * 80 + 72:r_ * 80 + 80] = bytes(8)
            return bytes(d)
        for key in MENU_AREAS:
            if name != 'ref' and masked(key, mn[key]) != masked(key, runs['ref']['menu'][key]):
                bad.append(key + ' != ref')
            if key in exp_menu and mn[key] != exp_menu[key]:
                bad.append(key + ' != raw file of the 1.0f disk')
        log(f'menu {name}: screen/title/font VRAM ' + ('identical to 1.0f' if not bad else 'DIFFER: ' + ', '.join(bad)))
        for b in bad:
            problems.append(f'menu prompt {name}: {b}')
    # 3: crawl01 model against the real 1.0f window
    hooks = [p['hook'] for p in runs['ref']['prompts']]
    nbad, nchk = [], 0
    cells = list(env.cells0)
    left = sum(1 for c in cells if c == 2)
    import dbemap
    ex = [e.cell for e in env.m.events if e.type == dbemap.EVENT_TYPES['exit']]
    for i, p in enumerate(ref):
        pos, pf, gp, gf = p['hook']
        if p['tag'] in ('map',):
            continue
        if cells[pos] == 2 and not p['tag'].startswith('scene'):
            cells[pos] = 0
            left -= 1
            if left <= 0:
                for x in ex:
                    cells[x] = 42
        if p['tag'].startswith('scene') and scenes[int(p['tag'][5:])]['label'].startswith('ghost on gem') \
                and cells[gp] != 2:
            log(f'warning: {p["tag"]}: the walk has already taken the gem under the ghost')
        vis, err = env.model.view(cells, env.w, env.h, pos, pf, [(gp, 0, gf)])
        base = bytearray(env.base1)                 # assets in place, random elsewhere
        base[8000:8080] = b'\xa5' * 80              # row 100: only the bytes the model writes count
        env.model.render(base, vis)
        nchk += 1
        got = p['vram']
        diff = []
        for r in range(5, 101):
            for c in range(6, 74):
                a = r * 80 + c
                if r == 100 and (base[a] == 0xA5 or p['tag'] == 'start'):
                    continue                        # row 100: model writes 0 only where walls are; start: text "GO!!!" is drawn after the first view
                if r == 5 and 63 <= c <= 70:
                    continue                        # HUD step counter (crawl.bas 5530, AP+63) overlaps window row 5
                if got[a] != base[a]:
                    diff.append((r, c, got[a], base[a]))
        if diff:
            nbad.append((i, p['tag'], len(diff), diff[:3]))
            problems.append(f'crawl01 model != real 1.0f at prompt {i} ({p["tag"]}): {len(diff)} bytes {diff[:3]}')
    log(f'crawl01 vs real 1.0f window: {nchk} prompts, {len(nbad)} differ')
    rep['crawl01'] = (nchk, nbad)
    # 4: automap = whole map
    exp = bytearray()
    for y in range(env.h):
        for x in range(env.w):
            exp += bytes([17 if env.cells0[y * env.w + x] & 1 else 255] * 2)
    for name in ('ref', 'interp', 'comp'):
        r = runs.get(name)
        if not r:
            continue
        mp = [p for p in r['prompts'] if p['tag'] == 'map']
        if not mp:
            continue
        p = mp[0]
        # screen area: offset in the saved [0,9600) range
        pos = p['hook'][0]
        bad = 0
        for y in range(env.h):
            for x in range(env.w):
                if y * env.w + x == pos:
                    continue
                a = MAPADDR + y * EI + x * 2
                if p['vram'][a:a + 2] != exp[(y * env.w + x) * 2:(y * env.w + x) * 2 + 2]:
                    bad += 1
        log(f'automap {name}: {env.w * env.h - 1} cells checked, {bad} differ from the whole-map expectation')
        if bad:
            problems.append(f'automap {name}: {bad} cells differ')
    for name, r in runs.items():
        for e in r['errors']:
            problems.append(f'{name}: {e}')
    return problems, rep


# ---------------------------------------------------------------- timing (P7d, spec 7.2)

def build_timing(work):
    """Unchanged release builds (no hook): {1.0f, 1.1} x {comp, interp} -> {name: disk}."""
    os.makedirs(work, exist_ok=True)
    disks = {'100f-comp': DISK_1_0F}
    src = os.path.join(work, 'crawl_100f.bas')
    open(src, 'w', encoding='utf-8').write(sh(['git', '-C', ROOT, 'show', 'main:game/crawl.bas']).stdout)
    prg = os.path.join(work, 'crawl_100f_1c01.prg')
    sh([sys.executable, os.path.join(ROOT, 'tools', 'bas2prg.py'), src, prg])      # tokenised, $1C01
    d = os.path.join(work, '100f-interp.d81')
    shutil.copy(DISK_1_0F, d)
    sh(['c1541', d, '-delete', 'crawl128', '-write', prg, 'crawl128'])
    disks['100f-interp'] = d
    for name, extra in (('110-comp', []), ('110-interp', ['--interp'])):
        d = os.path.join(work, name + '.d81')
        sh([sys.executable, os.path.join(ROOT, 'tools', 'mkdisk.py'), *extra, d])
        disks[name] = d
    return disks


def sw_read(m):
    return int(re.search(r'Stopwatch:\s+(\d+)', m.cmd('stopwatch')).group(1))


def drive_timing(name, disk, port, slow, tmo, nirq=20):
    """One timing run. Per key: stopwatch reset when the key is fed, read at the next game prompt (before the two
    interrupts that settle the picture). Calibration: stopwatch cycles between consecutive IRQ stops (one VIC frame,
    PAL 50.125 Hz) at the start picture, after SLOW when slow, and again after the walk.
    -> dict(keys=[cycles]*39, calib=[delta]*nirq, calib_end=[...], errors=[], interp=bool)"""
    res = dict(name=name, keys=[], calib=[], calib_end=[], errors=[], interp=None)

    def word(m, a):
        b = m.mem(a, 2)
        return b[0] | b[1] << 8

    def script(m):
        err_at = None
        bp_get = m.bp(0xFFE4)

        def wait_prompt():
            while True:
                pc, _ = m.go()
                if pc == err_at:
                    res['errors'].append(f'BASIC error in line {word(m, 0x3B)}, X={m.reg_x()}')
                    raise RuntimeError(res['errors'][-1])
                if pc == 0xFFE4 and m.mem(0xD0)[0] == 0:
                    return

        def feed(ch):
            m.cmd(f'> 034a {ord(ch):02x}')
            m.cmd('> 00d0 01')

        def calibrate():
            bp_irq = m.bp(word(m, 0x314))
            m.cmd(f'disable {bp_get}')
            m.go()
            m.cmd('stopwatch reset')
            out, last = [], 0
            t = m.mem(0xA0, 3)
            res.setdefault('ti_calib', []).append([t[0] << 16 | t[1] << 8 | t[2]])
            for _ in range(nirq):
                m.go()
                v = sw_read(m)
                out.append(v - last)
                last = v
            t = m.mem(0xA0, 3)
            res['ti_calib'][-1].append(t[0] << 16 | t[1] << 8 | t[2])     # jiffies over nirq IRQs
            m.cmd(f'delete {bp_irq}')
            m.cmd(f'enable {bp_get}')
            return out

        wait_prompt()
        err_at = word(m, 0x300)
        m.bp(err_at)
        res['interp'] = word(m, 0x3B) == 5
        if res['interp']:
            feed(' ')
            wait_prompt()
        feed('\r')
        wait_prompt()                                   # start picture
        if slow:
            feed('1')                                   # line 4240 SLOW, not counted
            wait_prompt()
        res['calib'] = calibrate()
        for k in WALK:
            feed(k)
            m.cmd('stopwatch reset')
            wait_prompt()
            res['keys'].append(sw_read(m))
        res['calib_end'] = calibrate()
        m.s.sendall(b'quit\n')
        return 0

    try:
        vm.run_vice(['-default', '-80col', '-VDC64KB', '-warp', '-sounddev', 'dummy', '-8', disk, '-autostart', disk,
                     '-limitcycles', '4000000000'], port, tmo, script)
    except (RuntimeError, vm.Exited, TimeoutError) as e:
        res['errors'].append('run aborted: ' + repr(e))
    return res


TIMING_CONFIGS = [f'{v}-{k}-{mhz}' for v in ('100f', '110') for k in ('comp', 'interp') for mhz in ('2mhz', '1mhz')]
TIMING_RESULTS = os.path.join(HERE, 'timing-results.json')     # recorded states (1.0f, P6i, P6j, P2f ...)


def timing_compare(results, record=None):
    """Compare the measured 1.1 sums with the recorded states in test/timing-results.json (VICE is deterministic,
    the baselines are not measured again). record: add the run as a new state with this name."""
    import json, hashlib
    db = json.load(open(TIMING_RESULTS))
    sums = {}
    for key, r in results.items():
        c = key.split('#')[0]
        if c.startswith('110-') and not r['errors'] and len(r['keys']) == len(WALK):
            sums.setdefault(c[4:], []).append(sum(r['keys']))
    if not sums:
        return
    for c, v in sums.items():
        if len(set(v)) > 1:
            print(f'note: {c} repeats differ: {v}')
    refs = [st for st in db['states'] if 'vice_cycles' in st]
    print('VICE cycles, 1.1 now against recorded states:')
    for c in ('comp-2mhz', 'comp-1mhz', 'interp-2mhz', 'interp-1mhz'):
        if c not in sums:
            continue
        now = sum(sums[c]) / len(sums[c])
        cmp = '  '.join(f'{st["name"]} {st["vice_cycles"][c]} ({(now / st["vice_cycles"][c] - 1) * 100:+.1f} %)'
                        for st in (refs[0], refs[-1]) if c in st['vice_cycles'])
        print(f'  {c:12} {now:12.0f} ({now / 985248:.2f} s)  {cmp}')
    if record:
        sha = lambda f: hashlib.sha256(open(os.path.join(ROOT, 'libs', f), 'rb').read()).hexdigest()
        db['states'].append(dict(name=record, date=time.strftime('%F'),
                                 lib_size=os.path.getsize(os.path.join(ROOT, 'libs', 'dbe0.2.lib.prg')),
                                 lib_sha256=sha('dbe0.2.lib.prg'), stub_sha256=sha('dbe0.2.stub.prg'),
                                 vdcbasic_size=os.path.getsize(os.path.join(ROOT, 'libs', 'vdcbasic3.prg')),
                                 vdcbasic_sha256=sha('vdcbasic3.prg'),
                                 vice_cycles={c: round(sum(v) / len(v)) for c, v in sums.items()}))
        json.dump(db, open(TIMING_RESULTS, 'w'), indent=1)
        print(f'recorded as "{record}" in {TIMING_RESULTS} (add the Z64K jiffies by hand)')


def timing_main(a):
    import json
    out = os.path.abspath(a.out if a.out != os.path.join(ROOT, 'build', 'test', 'crawl')
                          else os.path.join(ROOT, 'build', 'timing'))
    os.makedirs(out, exist_ok=True)
    disks = build_timing(out)
    # default: only 1.1; the baselines (1.0f, earlier 1.1 states) come from test/timing-results.json
    configs = a.configs.split(',') if a.configs else [c for c in TIMING_CONFIGS if c.startswith('110')]
    if a.only:
        configs = [c for c in configs if c.startswith(a.only)]
    import hashlib
    lib = os.path.join(ROOT, 'libs', 'dbe0.2.lib.prg')
    libinfo = dict(path=lib, size=os.path.getsize(lib), mtime=time.strftime('%F %T', time.localtime(os.path.getmtime(lib))),
                   sha256=hashlib.sha256(open(lib, 'rb').read()).hexdigest())
    print('lib (1.1):', libinfo, flush=True)
    ports = [vm.choose_port(int(p)) for p in (a.ports or os.environ.get('DBE_VICE_PORT', '6641')).split(',')]
    jobs = [(c, r) for r in range(a.reps) for c in configs]
    results = {}

    def one(job, port):
        c, r = job
        v, k, mhz = c.split('-')
        res = drive_timing(f'{c}#{r}', disks[f'{v}-{k}'], port, mhz == '1mhz', a.timeout)
        print(f'{c} rep {r}: {len(res["keys"])} keys, sum {sum(res["keys"])} cycles, errors {res["errors"]}', flush=True)
        return res

    with cf.ThreadPoolExecutor(len(ports)) as ex:
        free, futs, q = list(ports), {}, list(jobs)
        while q or futs:
            while q and free:
                j, pt = q.pop(0), free.pop(0)
                futs[ex.submit(one, j, pt)] = (j, pt)
            done, _ = cf.wait(list(futs), return_when=cf.FIRST_COMPLETED)
            for f in done:
                j, pt = futs.pop(f)
                free.append(pt)
                results[f'{j[0]}#{j[1]}'] = f.result()
    results['_lib'] = libinfo
    json.dump(results, open(os.path.join(out, 'timing.json' if not a.only else f'timing_{a.only}.json'), 'w'), indent=1)
    results.pop('_lib')
    bad = [k for k, r in results.items() if r['errors'] or len(r['keys']) != len(WALK)]
    print('PROBLEMS in', bad if bad else 'none')
    timing_compare(results, a.record)
    return 1 if bad else 0


# ---- ghost-near-sideways scene (P7a review): whole picture time 1.0f against 1.1

GHOST_SCENES = [('ghost 86 dir %d' % gd, (67, 3, 86, gd)) for gd in range(4)] + [('no ghost (cell 1)', (67, 3, 1, 0))]


def drive_ghost(name, disk, port, tmo, reps=3):
    """Hooked disk (test/patchbas.py), 2 MHz compiled: from the start picture, per scene the hook marker is set (player
    67, direction 3, ghost cell 86 ...), a space is fed (-> render), stopwatch from feed to the next prompt (VIEW + VCL +
    BASIC of one picture, hook overhead identical in both versions). Each scene `reps` times in a row.
    -> dict(scenes={label: [cycles]*reps}, errors)"""
    res = dict(name=name, scenes={}, errors=[])

    def script(m):
        err_at = None
        m.bp(0xFFE4)

        def word(a):
            b = m.mem(a, 2)
            return b[0] | b[1] << 8

        def wait_prompt():
            while True:
                pc, _ = m.go()
                if pc == err_at:
                    res['errors'].append('BASIC error')
                    raise RuntimeError('BASIC error')
                if pc == 0xFFE4 and m.mem(0xD0)[0] == 0:
                    return

        def feed(ch):
            m.cmd(f'> 034a {ord(ch):02x}')
            m.cmd('> 00d0 01')
        wait_prompt()
        err_at = word(0x300)
        m.bp(err_at)
        m.cmd('> 0c44 00')
        feed('\r')
        wait_prompt()
        for label, (p, d, g, gd) in GHOST_SCENES:
            for k, b in enumerate((165, p & 255, p >> 8, d, g & 255, g >> 8, gd)):
                m.cmd(f'> {HOOK_IN + k:04x} {b:02x}')
            for _ in range(reps):
                feed(' ')
                m.cmd('stopwatch reset')
                wait_prompt()
                res['scenes'].setdefault(label, []).append(sw_read(m))
        m.s.sendall(b'quit\n')
        return 0
    try:
        vm.run_vice(['-default', '-80col', '-VDC64KB', '-warp', '-sounddev', 'dummy', '-8', disk, '-autostart', disk,
                     '-limitcycles', '4000000000'], port, tmo, script)
    except (RuntimeError, vm.Exited, TimeoutError) as e:
        res['errors'].append('run aborted: ' + repr(e))
    return res


def ghost_main(a):
    import json
    out = os.path.abspath(a.out if a.out != os.path.join(ROOT, 'build', 'test', 'crawl')
                          else os.path.join(ROOT, 'build', 'timing'))
    disks, _ = build_all(os.path.join(out, 'hooked'))
    port = vm.choose_port(int(a.ports.split(',')[0]) if a.ports else None)
    res = {}
    for n, key in (('1.0f', 'ref'), ('1.1', 'comp')):
        if a.only and not n.startswith(a.only.replace('110', '1.1').replace('100f', '1.0f')):
            continue
        res[n] = drive_ghost(n, disks[key], port, a.timeout)
        print(n, res[n], flush=True)
    json.dump(res, open(os.path.join(out, 'ghost.json' if not a.only else f'ghost_{a.only}.json'), 'w'), indent=1)
    return 1 if any(r['errors'] for r in res.values()) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ghost', action='store_true', help='P7a review: ghost-near-sideways scene, whole picture time')
    ap.add_argument('--timing', action='store_true', help='P7d: cycle timing of the unchanged release builds')
    ap.add_argument('--reps', type=int, default=2)
    ap.add_argument('--record', default=None, help='timing: add the 1.1 result as a new state to test/timing-results.json')
    ap.add_argument('--only', default=None, help='timing: only configs starting with this (e.g. 110 for a 1.1 repeat)')
    ap.add_argument('--configs', default=None, help='timing: comma list of ' + ','.join(TIMING_CONFIGS))
    ap.add_argument('--runs', default='ref,orig,interp,comp')
    ap.add_argument('--ports', default=None)
    ap.add_argument('--reuse', action='store_true', help='use saved run results if present')
    ap.add_argument('--control', action='store_true')
    ap.add_argument('--no-build', action='store_true')
    ap.add_argument('--out', default=os.path.join(ROOT, 'build', 'test', 'crawl'))
    ap.add_argument('--timeout', type=int, default=3000)
    ap.add_argument('--scenes-only', action='store_true', help='no walk keys (debug)')
    a = ap.parse_args()
    if a.timing:
        return timing_main(a)
    if a.ghost:
        return ghost_main(a)
    t0 = time.time()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    names = a.runs.split(',')
    env, crawl01 = make_env(out)
    # scenes need the cells after the walk: walk positions come from the reference run -> the 1.0f run goes first
    pk = {n: os.path.join(out, n + '.pkl') for n in names}
    runs = {}
    disks = None

    def run_one(n, port, scenes):
        nonlocal disks
        r = drive(n, disks[n], port, scenes if n != 'orig' else None, WALK, a.timeout, os.path.join(out, n))
        pickle.dump(r, open(pk[n], 'wb'))
        print(f'run {n}: {len(r["prompts"])} prompts, errors {r["errors"]}, {time.time() - t0:.0f} s', flush=True)
        return r

    if a.reuse and all(os.path.exists(pk[n]) for n in names):
        runs = {n: pickle.load(open(pk[n], 'rb')) for n in names}
        scenes = pickle.load(open(os.path.join(out, 'scenes.pkl'), 'rb'))
        notes = pickle.load(open(os.path.join(out, 'notes.pkl'), 'rb'))
    else:
        if a.no_build and all(os.path.exists(os.path.join(out, n + '.d81')) for n in ('ref', 'interp', 'comp')):
            disks = {n: os.path.join(out, n + '.d81') for n in ('ref', 'interp', 'comp')}
            disks['orig'] = DISK_1_0F
            notes = pickle.load(open(os.path.join(out, 'notes.pkl'), 'rb'))
        else:
            disks, notes = build_all(out)
            pickle.dump(notes, open(os.path.join(out, 'notes.pkl'), 'wb'))
        print('build:', notes, f'{time.time() - t0:.0f} s', flush=True)
        ports = [int(x) for x in a.ports.split(',')] if a.ports else [vm.choose_port(None)]
        ports = [vm.choose_port(p) for p in ports]
        # phase 1: the walk without scenes decides which gems are gone -> scene list; but the scenes run in the
        # same VICE run, so the list is computed from the positions of the walk in the model beforehand
        scenes = make_scenes(env, walk_cells(env))
        pickle.dump(scenes, open(os.path.join(out, 'scenes.pkl'), 'wb'))
        print(f'{len(scenes)} scenes:', flush=True)
        for i, s in enumerate(scenes):
            print(f'  scene{i:02d}: {s["label"]}  player {s["pose"][0]} dir {s["pose"][1]} ghost {s["pose"][2]} dir {s["pose"][3]}')
        with cf.ThreadPoolExecutor(len(ports)) as ex:
            futs = {}
            q = list(names)
            free = list(ports)
            while q or futs:
                while q and free:
                    n = q.pop(0)
                    pt = free.pop(0)
                    futs[ex.submit(run_one, n, pt, scenes)] = (n, pt)
                done, _ = cf.wait(list(futs), return_when=cf.FIRST_COMPLETED)
                for f in done:
                    n, p = futs.pop(f)
                    free.append(p)
                    runs[n] = f.result()
    problems, rep = compare(runs, scenes, env, crawl01, control=(7 if a.control else None))
    print('1.0f rebuild identical to the disk original:', notes.get('rebuild_1.0f_identical'), notes.get('rebuild_sizes'))
    print(f'{time.time() - t0:.0f} s')
    if a.control:
        hit = [p for p in problems if p.startswith(('interp', 'comp', 'orig'))]
        print('control (reference byte of prompt 7 falsified):')
        for p in hit:
            print(' ', p)
        ok = len(hit) >= 2 and all(' at prompt 7 ' in p for p in hit if '!= ref' in p)
        print('CONTROL', 'OK' if ok else 'FAIL')
        return 0 if ok else 1
    for p in problems:
        print('PROBLEM', p)
    print('PASS' if not problems else 'FAIL')
    return 0 if not problems else 1


def walk_cells(env):
    """Cell values after the walk (the walk's gems and the opened exit are not needed to be exact: the scene gems
    are chosen among cells the walk cannot have visited: only the model positions of the 1.0f run would tell,
    so the scene run uses the initial cells; the check in compare() follows the recorded hook positions)."""
    return list(env.cells0)


if __name__ == '__main__':
    sys.exit(main())
