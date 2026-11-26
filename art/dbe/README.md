# Assets for dungeonboringengine 0.1 (Crawl 128 1.0f)

Generated with the tools of the engine repository (dungeonboringengine, tag v0.1),
byte-identical to its `build/` output:

| File | Disk name | Loaded to | Made with |
|---|---|---|---|
| `walls.wsm` | `walls.wsm` | bank 1, `$E000` | `tools/wallconv.py WALLS.VDC walls.wsm` |
| `ghost.spr` | `ghost.spr` | bank 1, `$E200` | `tools/crawlsprites.py red.vdc red1.vdc <dir>` |
| `gem.spr` | `gem.spr` | bank 1, `$EA00` | same call |
| `ghosts.vdc` | `ghosts.vdc` | bank 0 at BE, then `RTV` to VRAM `GA(0)` | same call |

Inputs: `WALLS.VDC` from `crawl128-100c.d81` (unchanged on the 1.0e/1.0f disks),
`red.vdc`/`red1.vdc` = `art/ghost-opaque/` (the opaque ghosts of 1.0c).

The engine itself: `libs/dbe0.1.stub.prg` and `libs/dbe0.1.lib.prg` = `engine/build.sh` output
`build/dbe0.1.stub` and `build/dbe0.1.lib` (on disk `dbe0.1.stub`, `dbe0.1.lib`).

These are the engine 0.1 data of Crawl 128 1.0f. Version 1.1 uses engine 0.2; its data are in `art/dbe02/`.
