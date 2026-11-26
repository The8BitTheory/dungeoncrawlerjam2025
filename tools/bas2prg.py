#!/usr/bin/env python3
"""Tokenise game/crawl.bas into game/crawl.prg (BASIC 7.0 + VDC-BASIC, load address $1C01).

usage: bas2prg.py [--start ADDR] crawl.bas crawl.prg [path/to/bastok.py]

--start ADDR: address of the first BASIC line (default $1C01, input for the Blitz! compiler;
$4001 for the interpreted version under VDC-BASIC v3). Passed on to bastok.py --start.

Uses the tokeniser of the vdc-basic repository (test/bastok.py, default ../../vdc-basic/test/bastok.py
next to this repository) with two changes that make the result byte-identical to the PRG that
C64 Studio / RetroDevStudio writes:
  - PETSCII characters stored by the IDE as U+EE00 + screen code are converted back to PETSCII
    (inside strings as bytes, outside strings as characters, e.g. the arrow up becomes the ^ token);
  - spaces outside strings, REM and DATA are dropped.
Lines starting with '#' and empty lines are skipped (bastok.py).
Check: the 1.0e source gives exactly the 1.0e crawl.prg.
"""
import importlib.util, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
START = None
if len(sys.argv) > 2 and sys.argv[1] == '--start':
    START = sys.argv[2]
    del sys.argv[1:3]
BASTOK = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, '..', '..', 'vdc-basic', 'test', 'bastok.py')


def sc2pet(s):
    """Screen code (as shown by the IDE) -> PETSCII."""
    if s < 0x20: return s + 0x40
    if s < 0x40: return s
    if s < 0x60: return s + 0x80
    if s < 0x80: return s + 0x40
    if s < 0xa0: return s - 0x80          # reverse 0-31: control codes $00-$1F
    if s < 0xc0: return s
    if s < 0xe0: return s - 0x40          # reverse $40-$5F: control codes $80-$9F
    return s


def convert(path):
    out = []
    for raw in open(path, encoding='utf-8'):
        line, q = '', False
        for c in raw:
            o = ord(c)
            if 0xEE00 <= o <= 0xEEFF:
                p = sc2pet(o - 0xEE00)
                line += '{%d}' % p if q else chr(p)
            else:
                if c == '"':
                    q = not q
                line += c
        out.append(line)
    return ''.join(out)


def load_bastok():
    spec = importlib.util.spec_from_file_location('bastok', BASTOK)
    bt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bt)
    src = open(BASTOK).read()
    new = src.replace('if c == " ":\n            out.append(32)', 'if c == " ":\n            pass')
    if new == src:
        sys.exit('bas2prg: bastok.py has changed, cannot drop spaces')
    exec(compile(new, BASTOK, 'exec'), bt.__dict__)
    return bt


def main():
    src, dst = sys.argv[1], sys.argv[2]
    bt = load_bastok()
    with tempfile.NamedTemporaryFile('w', suffix='.bas', delete=False, encoding='utf-8') as f:
        f.write(convert(src))
        tmp = f.name
    try:
        sys.argv = [BASTOK] + (['--start', START] if START else []) + [tmp, dst]
        bt.main()
    finally:
        os.unlink(tmp)


if __name__ == '__main__':
    main()
