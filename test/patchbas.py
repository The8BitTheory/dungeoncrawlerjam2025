#!/usr/bin/env python3
"""Add the test hook (P7c, docs/specs/P7-crawl.md 6.3) to a Crawl 128 BASIC source (text).

usage: patchbas.py IN.bas OUT.bas
       patchbas.py --timedemo [--slow] IN.bas OUT.bas

--timedemo (P7d, spec 7.3): Timedemo version for Z64K (no monitor): the walk of 39 keys is fed from TD$, T9 = jiffies
from the first prompt to the 40th prompt (= sum of key -> next prompt over the walk), written to the file TIMES on
drive 8, then POKE 55295 (= $D7FF, debugcart) ends Z64K. Line 5 (disk prompt) becomes REM, the menu is skipped
(3400 ... GOTO 3700). --slow adds `3701 SLOW` (1 MHz). The hook (4596/4597) is not added.

Lines 4596/4597 (free in 1.0f and 1.1) become a subroutine that is called at the start of line 4600
(`GOSUB4596:`), i.e. before every render, in both versions with the same text:
  * input (bank 0, $0C44-$0C4A): if $0C44 = 165 the player position (word) and direction ($0C45-$0C47) and
    the position (word) and direction of ghost 1 ($0C48-$0C4A) are taken over; PH%(0) = 9 (no KO by hits in
    scenes). The marker stays: it is overwritten by the harness for the next scene (sticky: every render of
    one key press shows the scene, even if the AI moves the ghost between two renders).
  * output (bank 0, $0CC0-$0CC5): PP%(0) (word), PF%(0), PP%(1) (word), PF%(1) as they are drawn.
$0C44-$0C4F is reserved for tests in the engine 0.2 parameter block, $0CB1-$0CFF is reserve (2.3); the 1.0f
disk (engine 0.1) does not use them either (checked by the 1.0f/1.0f repetition of the test).
The source in the repository is not changed.
"""
import re, sys

HOOK = {
    4596: 'BANK0:IF PEEK(3140)=165 THEN PP%(0)=PEEK(3141)+256*PEEK(3142):PF%(0)=PEEK(3143)'
          ':PP%(1)=PEEK(3144)+256*PEEK(3145):PF%(1)=PEEK(3146):PH%(0)=9',
    4597: 'POKE3264,PP%(0)AND255:POKE3265,INT(PP%(0)/256)AND255:POKE3266,PF%(0)'
          ':POKE3267,PP%(1)AND255:POKE3268,INT(PP%(1)/256)AND255:POKE3269,PF%(1):RETURN',
}
WALK = 'WWEWWEWWQWWQWWQWWWWWQAAAAAEAAWWWWWQWWWQ'
ADDR_IN, ADDR_OUT = 0x0C44, 0x0CC0


def patch(text):
    lines = text.splitlines()
    nums = [int(m.group(1)) for l in lines if (m := re.match(r'(\d+) ', l))]
    if any(n in nums for n in HOOK):
        raise SystemExit('patchbas: lines 4596/4597 are not free')
    out, done = [], False
    for l in lines:
        m = re.match(r'(\d+) ', l)
        if m and int(m.group(1)) == 4600:
            out += [f'{n} {s}' for n, s in HOOK.items()]
            l = '4600 GOSUB4596:' + l[5:]
            done = True
        out.append(l)
    if not done:
        raise SystemExit('patchbas: line 4600 not found')
    return '\n'.join(out) + '\n'


def timedemo(text, slow=False):
    """Timedemo patch (spec 7.3); inserts keep the ascending line order."""
    lines = text.splitlines()
    new = {115: 'TD$="%s"' % WALK,
           4041: 'IF TX>39 THEN T9=TI-T0:GOTO 63100',
           4042: 'I$=MID$(TD$,TX,1):TX=TX+1',
           63100: 'BANK15:OPEN2,DD,2,"@0:TIMES,S,W":PRINT#2,T9:CLOSE2:POKE55295,0'}
    if slow:
        new[3701] = 'SLOW'
    repl = {5: '5 REM', 3400: None, 4040: '4040 IF TX=1 THEN T0=TI'}
    nums = [int(m.group(1)) for l in lines if (m := re.match(r'(\d+) ', l))]
    if any(n in nums for n in new):
        raise SystemExit('patchbas: timedemo lines %s are not free' % [n for n in new if n in nums])
    out, pend, seen = [], sorted(new), set()
    for l in lines:
        m = re.match(r'(\d+) ', l)
        if m:
            n = int(m.group(1))
            while pend and pend[0] < n:
                out.append(f'{pend[0]} {new[pend[0]]}')
                pend.pop(0)
            if n in repl:
                seen.add(n)
                l = l if n == 3400 else repl[n]
                if n == 3400:
                    l = l.rstrip() + ':GOTO 3700'
        out.append(l)
    for n in pend:
        out.append(f'{n} {new[n]}')
    if seen != set(repl):
        raise SystemExit('patchbas: lines %s not found' % sorted(set(repl) - seen))
    return '\n'.join(out) + '\n'


def main():
    a = sys.argv[1:]
    td = '--timedemo' in a
    slow = '--slow' in a
    a = [x for x in a if not x.startswith('--')]
    if len(a) != 2:
        raise SystemExit(__doc__)
    t = open(a[0], encoding='utf-8').read()
    open(a[1], 'w', encoding='utf-8').write(timedemo(t, slow) if td else patch(t))


if __name__ == '__main__':
    main()
