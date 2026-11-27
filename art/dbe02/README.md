# Assets for dungeonboringengine 0.2 (Crawl 128 1.1)

Made by `crawlconv` of the engine repository (Python until 2026-11-27, now `node tools/js/cli/dbe.js crawlconv`) (dungeonboringengine, branch `step2/textures-0.2`, P7a) from
the unchanged 1.0f data on `crawl128-100f.d81` (`walls.vdc`, `walls.wsm`, `ghost.spr`, `ghosts.vdc`, `gem.spr`,
`font3o.vdc`). The pictures are the same as in 1.0f. `crawlconv.md` is the converter's report (elements, anchors,
sizes, VRAM sum).

Rebuild: `python3 tools/mkdisk.py --rebuild-assets OUT.d81` (calls `dbe.js crawlconv --d81 crawl128-100f.d81 build/assets`
and copies the result here), or by hand: `node $DBE_DIR/tools/js/cli/dbe.js crawlconv --d81 crawl128-100f.d81 OUT_DIR`.

| File | Disk name | Loaded to | Content |
|---|---|---|---|
| `crawl.dmp` | `crawl.dmp` | bank 1, `$4000` | map (DMP); tile plane at `$4018` is the template `VE` of the game |
| `crawl.dvg` | `crawl.dvg` | bank 1, `$E800` | view geometry (DVG): 28 elements, 68 x 96 window |
| `walls.dts` | `walls.dts` | bank 1, `$8000` | wall textures (DTS), 19 pictures, cores only |
| `ghost.s2` | `ghost.s2` | bank 1, `$6000` | sprite set 0: ghost (S2) |
| `gem.s2` | `gem.s2` | bank 1, `$7000` | sprite set 1: gem (S2) |
| `walls.vrl` | `walls.vrl` | bank 0 at `BE`, stream at `BE+5`, `RXV` to VRAM `DA` | wall picture data (6050 bytes packed, 22354 unpacked) |
| `ghost.vrl` | `ghost.vrl` | bank 0 at `BE`, `RXV` to VRAM `GA(0)` | ghost pictures (1882 bytes unpacked) |
| `gem.vrl` | `gem.vrl` | bank 0 at `BE`, `RXV` to VRAM `GA(1)` | gem picture (36 bytes unpacked) |
| `font.vrl` | `font.vrl` | bank 0 at `BE`, `RXV` to VRAM `CA` | font 3x6 (1730 bytes unpacked, 1406 bytes file); made by `tools/vrlpics.py` from `font3o.vdc` of the 1.0f disk |
| `title.vrl` | `title.vrl` | bank 0 at 63493 (file), stream at 63498, `RXV` to VRAM `TA` each time the menu is shown | title picture (2338 bytes unpacked, file 1021 bytes, 1019 bytes in RAM after the load address); `tools/vrlpics.py` |

The wall VRL is not split (`--max-part` 0, N = 1): it is 6050 bytes and the load buffer `[BE, $D000)` is about 20 KB
(`RXV` cannot read from `$D000-$DFFF`).

The engine files `libs/dbe0.2.stub.prg`, `libs/dbe0.2.lib.prg` are `engine/build.sh` output (`build/dbe0.2.stub`,
`build/dbe0.2.lib`); `libs/vdcbasic3.prg` is `vdcbasic3.bin` of vdc-basic (branch `v3`, load address `$1C00`);
`libs/boot.prg` is `boot/boot.bas` of vdc-basic with line 50 `RUN"CRAWL128"`, tokenised for `$1C01`
(`tools/mkdisk.py --rebuild-libs` makes all of them again).

## How the data are made

1. **Wall, ghost and gem data** (`crawl.dmp`, `crawl.dvg`, `walls.dts`, `walls.vrl`, `ghost.s2`, `ghost.vrl`, `gem.s2`,
   `gem.vrl`, report `crawlconv.md`): `crawlconv` reads the unchanged 1.0f files from `crawl128-100f.d81` (`walls.vdc`,
   `walls.wsm`, `ghost.spr`, `ghosts.vdc`, `gem.spr`, `font3o.vdc`) and produces the 0.2 formats. The pictures are the same as
   in 1.0f: the wall data are the bytes of `walls.vdc` (same order), the gem is taken from the font characters of 1.0f, the ghost transparency mask is derived from what 1.0f
   draws (the converter renders the 1.0f `VMS` lists on two backgrounds). The gem now has its own 36 bytes in VRAM
   instead of using font characters (the same bytes, deduplicated: 36 instead of 72). The map comes from `CRAWL128.CD1`
   (`crawlmap.py`, items 2 and 4).
2. **Font and title** (`font.vrl`, `title.vrl`): `tools/vrlpics.py` packs `font3o.vdc` and `title.vdc` of the 1.0f disk with the
   VRL encoder of vdc-basic (`tools/vrl.py`, size-optimal). Font 1732 to 1406 bytes, title 2340 to 1021 bytes (both with load
   address).
3. **Engine and VDC-BASIC** (in `libs/`): see below.

An offline comparison (`crawl01`, engine repository, `tools/js/core/crawl/crawl01.js`) shows that the engine 0.2 draws the same bytes as 1.0f in all
19,136 views of the level; `test/vice_crawl.py` shows the same in VICE (see `test/README.md`).

## Commands

```sh
# all of art/dbe02/ again (needs ../dungeonboringengine; wall/ghost/gem/map data)
node $DBE_DIR/tools/js/cli/dbe.js crawlconv --d81 crawl128-100f.d81 OUT_DIR   # --max-part N splits walls.vrl if needed
python3 tools/mkdisk.py --rebuild-assets build/crawl128-110.d81            # the same, copied to art/dbe02/, and a disk

# font.vrl and title.vrl
python3 tools/vrlpics.py                                                   # reads crawl128-100f.d81, writes art/dbe02/

# the engine, VDC-BASIC v3 and the boot loader in libs/
python3 tools/mkdisk.py --rebuild-libs build/crawl128-110.d81
```

`--rebuild-libs` needs the engine built first (`engine/build.sh` in dungeonboringengine). `mkdisk.py` builds a disk from the
checked-in files; the rebuild options are only needed if the sources change.
