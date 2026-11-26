# Tests

| Script | Purpose |
|---|---|
| `crawl_smoke.py DISK.d81` | Smoke test (P7b): boot a disk in VICE x128, play the walk of 39 keys, open the automap, report memory. |
| `vice_crawl.py` | Pixel test (P7c): Crawl 1.1 (interpreted, compiled) against 1.0f at every game prompt (see the docstring). |
| `patchbas.py IN.bas OUT.bas` | Adds the test hook (lines 4596/4597, called at the start of 4600) to a Crawl source; used by `vice_crawl.py`. The repository sources stay unchanged. |

`vice_crawl.py` needs the neighbour repositories `dungeonboringengine` (`DBE_DIR`, tools: `crawl01`, `crawlconv`), `vdc-basic`
branch `v3` (`VDCBASIC_DIR`, `test/vicemon.py`, boot loader) and `blitz-compiler` (`BLITZC`), VICE `x128`, `c1541`, node.
It builds three hooked disks (1.0f rebuilt from `git show main:game/crawl.bas`, 1.1 interpreted, 1.1 compiled) into
`build/test/crawl/`, runs the original `crawl128-100f.d81` as a fourth run and compares VDC RAM `[0,9600)` and
`[46335,65535)` plus registers 0-36 (R14/R15 text cursor and R32/R33 block copy source are pointer registers that
differ legitimately and are reported as "tolerated"). Whole run about 25 s (parallel on the monitor ports
6637/6638: `--ports 6637,6638`; the default is `DBE_VICE_PORT`, 6631-6649).

    test/vice_crawl.py --ports 6637,6638        # build, run, compare
    test/vice_crawl.py --reuse                  # compare saved runs again
    test/vice_crawl.py --reuse --control        # falsify one reference byte: exactly that prompt must be reported

Test hook (`$0C44-$0C4A` input, `$0CC0-$0CC5` output): with `$0C44` = 165 the player and ghost 1 are placed and `PH%(0)` = 9;
the current `PP%(0)/PF%(0)/PP%(1)/PF%(1)` are always written to `$0CC0`. Both versions use the same hook text.
Prompts are recognised by the BASIC line `$3B/$3C` only when available; the Blitz! compilation does not keep it, there the
order of the GETIN prompts is used (menu first, then game prompts).

## Timing (P7d)

| Command | Purpose |
|---|---|
| `test/vice_crawl.py --timing --ports 6641,6642 [--reps 2] [--record NAME]` | VICE: the 4 configs of 1.1 ({comp, interp} x {2 MHz, 1 MHz}) on the unchanged release builds, per key stopwatch cycles (monitor `stopwatch`), calibration by IRQ stops (cycles per frame, jiffies per frame via `TI`); result `build/timing/timing.json` (with the 1.1 lib size/sha). The baselines are not measured again (VICE is deterministic): the run is compared with the recorded states in `test/timing-results.json` (1.0f, old lib, P6i, variant A, P6j, P2f, with lib/VDC-BASIC sha and date); `--record NAME` adds it as a new state. `--configs 100f-comp-2mhz,...` measures 1.0f explicitly. |
| `test/vice_crawl.py --ghost [--only 110]` | VICE: whole picture time of the scene "ghost near, sideways" (player 67, dir 3, ghost cell 86) 1.0f against 1.1 (hooked builds); `build/timing/ghost.json`. |
| `test/z64k_crawl.py [--only 110] [--reps 2]` | Z64K timedemo (`patchbas.py --timedemo [--slow]`): T9 in jiffies from the file TIMES; `build/z64k/z64k.json`. |
