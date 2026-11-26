#!/usr/bin/env python3
"""Font and title picture of Crawl 128 as VRL (RLE for RXV, VDC-BASIC v3).

usage: vrlpics.py [--d81 DISK] [OUT_DIR]

Reads font3o.vdc and title.vdc (raw, without load address) from the 1.0f disk and writes font.vrl and title.vrl
with the canonical vrl.py of vdc-basic (VDCBASIC_DIR). The VRL encoder is size-optimal and independent of the
RXV threshold T ($1C04, default 14), which only changes the speed.
"""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VB3 = os.environ.get('VDCBASIC_DIR', os.path.expanduser('~/git/vdc-basic'))
sys.path.insert(0, os.path.join(VB3, 'tools'))
import vrl  # noqa: E402


def main():
    a = sys.argv[1:]
    disk = os.path.join(ROOT, 'crawl128-100f.d81')
    if a[:1] == ['--d81']:
        disk, a = a[1], a[2:]
    out = a[0] if a else os.path.join(ROOT, 'art', 'dbe02')
    os.makedirs(out, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        for src, dst in (('font3o.vdc', 'font.vrl'), ('title.vdc', 'title.vrl')):
            p = os.path.join(t, src)
            subprocess.run(['c1541', disk, '-read', src, p], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            raw = open(p, 'rb').read()[2:]  # c1541 keeps the PRG load address
            stream = vrl.encode(list(raw))
            data = vrl.pack_file(stream)
            open(os.path.join(out, dst), 'wb').write(data)
            print('%s: %d bytes raw -> %d bytes VRL' % (dst, len(raw), len(data)))


if __name__ == '__main__':
    main()
