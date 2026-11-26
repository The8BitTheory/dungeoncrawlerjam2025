#!/usr/bin/env python3
"""Smoke test for Crawl 128 1.1 (P7b): start from a disk image in VICE x128 (80 columns, 64 KB VDC),
play the walk of 39 keys, open the automap, report memory.

usage: test/crawl_smoke.py DISK.d81 [--name NAME] [--port N] [--timeout S] [--keys KEYS] [--out DIR]

Event driven, no fixed waits: breakpoint on GETIN ($FFE4; keyboard buffer $D0 = 0: the program waits) and on
the BASIC error vector (($0300)); the cycle limit and --timeout are only guards. After the game prompt
appears, two interrupts are waited for (breakpoint on the IRQ vector), then a screenshot is written.
Prompts with an empty keyboard buffer, in order:
  interpreted: line 5 disk prompt (space), menu GET loop (RETURN), then game prompts (line 4040)
  compiled:    menu GET loop (RETURN), then game prompts
(an interpreted program is recognised by the BASIC line $3B/$3C; the compiled one does not keep it.)
Port rule: --port, else DBE_VICE_PORT, else 6631 (range 6631-6649), bind check; only the own VICE process is
ended. Neighbour repository VDCBASIC_DIR (vdc-basic, v3): test/vicemon.py is used, nothing is changed there.
Exit code 0 = whole walk and automap without BASIC error.
"""
import argparse, os, re, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VB3 = os.environ.get('VDCBASIC_DIR', os.path.expanduser('~/git/vdc-basic'))
sys.path.insert(0, os.path.join(VB3, 'test'))
import vicemon as vm

WALK = 'WWEWWEWWQWWQWWQWWWWWQAAAAAEAAWWWWWQWWWQ'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('disk')
    ap.add_argument('--name', default='run')
    ap.add_argument('--port', type=int)
    ap.add_argument('--timeout', type=int, default=900)
    ap.add_argument('--keys', default=WALK)
    ap.add_argument('--out', default=os.path.join(ROOT, 'build', 'test'))
    a = ap.parse_args()
    port = vm.choose_port(a.port)
    disk = os.path.abspath(a.disk)
    out = os.path.abspath(os.path.join(a.out, a.name))
    os.makedirs(out, exist_ok=True)
    res = {'errors': [], 'shots': [], 'prompts': 0}

    def shot(m, tag):
        p = os.path.join(out, f'{tag}.png')
        m.cmd(f'screenshot "{p}" 2')
        res['shots'].append(p)

    def line(m):
        b = m.mem(0x3B, 2)
        return b[0] | b[1] << 8

    def word(m, a):
        b = m.mem(a, 2)
        return b[0] | b[1] << 8

    def mem_report(m, tag):
        be = word(m, 0x1210)
        p = {n: word(m, x) for n, x in (('VARTAB', 0x2D), ('ARYTAB', 0x2F), ('STREND', 0x31), ('FRETOP', 0x33),
                                        ('MEMSIZ', 0x39))}
        res[tag] = dict(BE=be, **p)
        print(f'{tag}: BE=${be:04X} ({be}) ' + ' '.join(f'{k}=${v:04X}' for k, v in p.items()), flush=True)

    def script(m):
        ev = m.mem(0x300, 2)
        err_at = ev[0] | ev[1] << 8
        bp_err = m.bp(err_at)
        bp_get = m.bp(0xFFE4)

        def wait_prompt():
            """run to the next GETIN with an empty keyboard buffer; BASIC error -> raise"""
            while True:
                pc, _ = m.go()
                if pc == err_at:
                    res['errors'].append(f'BASIC error in line {line(m)}, X={m.reg_x()}')
                    raise RuntimeError(res['errors'][-1])
                if pc == 0xFFE4 and m.mem(0xD0)[0] == 0:
                    return

        def feed(ch):
            m.cmd(f'> 034a {ord(ch):02x}')
            m.cmd('> 00d0 01')

        def settle():
            """two interrupts, so that the picture is complete"""
            vec = word(m, 0x314)
            b = m.bp(vec)
            m.cmd(f'delete {bp_get}')
            for _ in range(2):
                pc, _ = m.go()
                if pc == err_at:
                    raise RuntimeError('BASIC error while settling')
            m.cmd(f'delete {b}')
            return m.bp(0xFFE4)

        step = 0
        wait_prompt()
        interp = line(m) == 5
        print('interpreted' if interp else 'compiled (or no BASIC line)', 'line', line(m), flush=True)
        mem_report(m, 'first_prompt')
        if interp:
            feed(' ')
            wait_prompt()                       # menu
            print('menu line', line(m), flush=True)
        # menu: first empty prompt after the picture
        mem_report(m, 'menu')
        feed('\r')
        wait_prompt()                           # game prompt (initial view)
        bg = settle()
        ln = line(m)
        print('game prompt, line', ln, flush=True)
        if interp and ln != 4040:
            res['errors'].append(f'expected line 4040, found {ln}')
        mem_report(m, 'game')
        shot(m, 'p00')
        bp_get = bg
        res['prompts'] = 1
        for i, k in enumerate(a.keys, 1):
            feed(k)
            wait_prompt()
            res['prompts'] += 1
            if i in (3, 10, len(a.keys)):
                bg2 = settle(); bp_get = bg2
                shot(m, f'p{i:02d}')
        # automap
        feed('M')
        wait_prompt()
        bg2 = settle(); bp_get = bg2
        if interp:
            print('map prompt, line', line(m), flush=True)
        shot(m, 'map')
        feed(' ')
        wait_prompt()
        bg2 = settle(); bp_get = bg2
        shot(m, 'after_map')
        mem_report(m, 'end')
        # bank 1 $0400-$3FFF: highest used byte from the bottom (variables, arrays) and lowest from the top (strings)
        m.cmd('bank ram01')
        d = m.mem(0x400, 0x3C00)
        m.cmd('bank default')
        nz = [0x400 + i for i, v in enumerate(d) if v]
        lo = max([x for x in nz if x < 0xB00] or [0])      # $0B00-$0FFF: engine, from $1300 buffer: not variables
        hi = min([x for x in nz if x >= 0x2000] or [0])
        print(f'bank 1: highest non-zero byte in $0400-$0AFF: ${lo:04X}; lowest non-zero byte in $2000-$3FFF: ${hi:04X}', flush=True)
        return 0

    try:
        r, rc = vm.run_vice(['-default', '-80col', '-VDC64KB', '-warp', '-sounddev', 'dummy', '-8', disk,
                             '-autostart', disk, '-limitcycles', '2000000000'], port, a.timeout, script)
    except (RuntimeError, vm.Exited, TimeoutError) as e:
        print('FAIL', repr(e), res['errors'])
        return 1
    print('PASS' if not res['errors'] else 'FAIL', f"prompts={res['prompts']}", 'shots:', *res['shots'])
    return 0 if not res['errors'] else 1


if __name__ == '__main__':
    sys.exit(main())
