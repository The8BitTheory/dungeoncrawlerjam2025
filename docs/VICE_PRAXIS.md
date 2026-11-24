# VICE practice: known pitfalls and their solutions

Required reading before every VICE test. **Anyone who runs into a new, recurring problem and
solves it records the solution here** (problem, cause, solution, date). Time spent on timeouts and
failed attempts is more expensive than two lines of documentation.

## Basic rule: no waiting without work (as of 2026-11-21)

- **VICE only via `tools/vtest.py`** (example: `test/vice_toc_popup.py`, 6 s for startup, WiC64 fetch,
  popup, three keys, three screenshots). It waits only for events (breakpoint, monitor prompt,
  screenshot file); every wait has a fixed short limit and then aborts with a message.
- **Forbidden:** fixed `sleep` waits for "maybe it is done", `timeout … tail --pid=…`,
  watch/monitor loops that wait minutes for a test run, several parallel watches on
  the same run. If something takes longer than expected: look for the cause (log, process), do not keep waiting.
- A VICE scenario takes seconds, not minutes. If a step takes longer than its limit, that is
  an error (wrong option, breakpoint never reached), not a reason to raise the limit.

## Processes

- **Several VICE runs in parallel (other agents, 2026-11-23):** a global `pkill -x x128` and the shared
  monitor port 6510 kill or take over the runs of others ("Connection reset", foreign screenshots).
  **Solution:** `tools/vtest.py` no longer kills any x128; `close()` ends only its own process. The monitor port comes
  from `Vice(..., port=N)` or the environment variable `VTEST_PORT` (default 6510); if the port is already taken,
  `Vice()` stops with a message instead of connecting to the foreign emulation. Every agent uses its own port
  (e.g. `VTEST_PORT=6550`). Own scripts without `vtest.py`: no `pkill`/`killall`, end your own `Popen` with `kill()`.
  The rules below about `pkill -x` apply only when you are certainly alone on the machine.
- **`pkill -f x128` kills your own shell.** Cause: `-f` matches the whole command line,
  and the command line of the calling `bash -c "… pkill -f x128 …"` itself contains `x128`.
  The shell dies (exit code 143/144), and the tool call seems to hang or aborts.
  **Solution:** search by process name, not by command line:
  `pkill -x x128` or `pgrep -x x128`. If `-f` is needed: `pkill -f '[x]128 -default'`
  (the bracket keeps the pattern from matching itself). The same applies to
  `python3 test/wiki_server.py` (`pkill -f '[w]iki_server.py'`). **The bracket does not help either** if
  the same command text `wiki_server.py` appears elsewhere in the command line (e.g. in the
  start of the new server in the same `bash -c`): exit code 144, nothing ran. Start the server in a
  script (`srv.sh` with `exec python3 -u …`) and stop it in a separate call (`ps`, `kill <pid>`).
- **An old x128 instance holds port 6510.** Otherwise a new run connects to the old
  emulation. Before every start: `pkill -x x128; sleep 0.5`.
- **Never abort monitor scripts with `timeout`**, otherwise the monitor hangs or VICE stays stuck in the
  monitor. Instead use bounded loops in the script itself and `p.kill()` at the end
  (`tools/vmon.py` does this).
- Start long runs (WiC64 server, VICE) with `run_in_background`, not with `&` in a
  foreground shell, and stop them at the end specifically with `pkill -x`.

- **Several VICE users at the same time** (parallel agents, 2026-11-23): `tools/vtest.py` kills every
  `x128` and always uses monitor port 6510, so parallel runs kill or take over each other ("Connection
  reset by peer", breakpoints never reached). Use an own port per user and kill only the own process
  (`apps/sidsfx/editor/test/vhelp.py`: port 6530, no pkill). Leftover `x128` of an aborted run still hold
  their port: check with `pgrep -a x128` and kill only your own.

## Monitor connection

- **Every disconnect resumes the emulation.** `tools/vmon.py` reconnects for each command and
  then sends `x`. For anything that must stay halted (breakpoint, filling memory, setting
  state, then resuming), hold a single connection in a dedicated Python script.
- A breakpoint hit is recognized by the prompt with the target address, e.g. `(C:$1ce6)`, **not**
  by the text "Stop on exec" (that is already in the confirmation of `break`). Wait for that instead of
  fixed `sleep`s.
- **Drain the socket before every monitor command**, otherwise the replies arrive offset by one command
  (old prompts).
- **A breakpoint on `main_loop` halts again immediately** (every round). To "keep running for N s":
  `del <nr>`, `x`, close the socket, sleep N s, reconnect (connecting halts VICE).
- **VDC RAM in the monitor:** `bank vdc`, then `m 3e80 3fff`, `f 6000 7fff a5`,
  `save "/path/v.bin" 0 0 ffff` (file with 2 bytes of load address, 65,538 bytes). Afterwards
  `bank default` for CPU addresses. VDC RAM is not zero at startup.
- **Label file without repo changes** (byte-identical to `wikipedia.prg`):
  `cd apps/wikipedia && ca65 -t none -I ../../runtime -I .. -g -o $S/w.o wikipedia.s && ld65 -C ../../demo_mac/demo.cfg -Ln $S/w.lbl -o $S/w.prg $S/w.o`
- **`main_loop` is never reached while idle**, only after an event (every handler ends with
  `jmp main_loop`). A breakpoint set after startup otherwise waits forever (timeout). Procedure per event:
  `break <main_loop>`, set the event via the monitor, `x`, wait for `(C:$xxxx)` (the handler is done; this
  includes a synchronous network load), then `del` (without a number = delete all; after `del 1` and
  a new `break` the breakpoint is called 1 again) and `run_for` 3-6 s to keep running/rasterize.
- **Mouse click on a link in the canvas: only `K_MDOWN`**, after that the handler no longer returns to
  `main_loop` (waiting for it runs into the timeout). Buttons (back/forward arrows, "Suchen", QR): `K_MDOWN` and
  then `K_MUP`, wait for `main_loop` after each. Back button (Mac look) at (28, 29).
- **Start Python scripts for VICE** in the background with `python3 -u … > file` (a
  foreground call is moved to the background after 120 s and shows nothing, buffered).
  Wait with a bounded loop and `grep` for the target line; afterwards always `pkill -x x128`.
  From the warp start to `main_loop` takes about 2 s.

## Keyboard (`keybuf`)

- **Only one key press per `keybuf` call reliably reaches the GUI.** Send keys one at a time,
  then wait for the `main_loop` breakpoint (handler done).
- **Identical keys in a row arrive only once** (the GUI IRQ discards
  key repeats, cursor/DEL/space). Send them one at a time, letting it run in between.
- A leading space is cut off: write `\x20`.
- **ALT cannot be sent**: open menus via the mouse state (see below) or via
  function-key shortcuts (F4 = `\x8a`).
- **The search field does not reliably receive `keybuf`**: write the title to `$0C60` (`WN_TITLE`)
  and set `r pc=<h_fetch>` (address from the label file).
- `keybuf` right after a breakpoint hangs on the first key press in about every second run.
  Then repeat the run, do not wait long (short time limit of its own in the script).
- At most 10 characters per `keybuf` call.
- **Bank-1 programs (8 KB common RAM, `oscar/`, `apps/sidsfx/editor/`): every `keybuf` key arrives twice**
  (2026-11-23). Keys put straight into the GUI key queue arrive once: write the PETSCII code to
  `kq_buf` (`$0B00` + `kq_head`) and increase `kq_head`, like the mouse codes (`qkey()` in
  `apps/sidsfx/editor/test/vhelp.py`). Not yet known whether real hardware is affected (it is not
  expected: the Kernal puts each key in the buffer once).
- **The first `keybuf` key after the start can arrive twice, and the event reported afterwards may belong to the
  previous key** (oscar/vice_spike.py, 2026-11-23): checking each key against the expected state fails at random.
  Solution: read the key the program actually received (here `b1p.evp`, `$1.193B`) and check against a model
  that follows the received keys.

- **Keys are occasionally lost (as of 2026-11-21):** about every 5th-10th `keybuf` call does not arrive,
  `until("main_loop")` then runs into its limit. Solution: `press(code, limit)` in `test/vice_toc_popup.py`
  (send the key, on limit `v.stop()` and retry once; on a second failure screenshot `fehler.png`).
  After a failed `until` the emulation keeps running: before the next monitor command use `v.stop()`.
- **ESC in the "Inhalt" popup does not reliably reach `main_loop`:** use only `v.key(0x1B)` and `v.settle(1.0)`,
  not `until`. (The popup is closed afterwards; checked in the test, no difference old/new.)
- **TAB skips `[[#anchor]]` links** (old and new): link focus via TAB only reaches links with a target other
  than an anchor in the same article. So open anchor links with the mouse (`click()` in `test/vice_toc_popup.py`).
- **After `screenshot()` prompts are still in the socket:** the next `m` then returns only the old prompt
  (empty list, IndexError). Drain the socket before `peek` (`peek()` in the test script). The screenshot itself
  fails in about every 10th run (empty file): retry once (`shot()`).
- **Simulating a fully loaded start article / "truncated" (since 7c-new):** The small test article always arrives completely (`WK_LOADED` = `$FF`, no
  size query, `--size` no longer exists). "Entry outside the loaded range" is tested via the monitor with `WK_LOADED` = 0, then
  open the popup, cursor, RETURN: the server sees `section=N`, `cap_buf` (`$07A0`: length, `$FF`, text; truncated to
  window width) contains "Wikipedia am C128 - Jensen Huang - <section>". A real truncated article is provided by `zürich.json` (`test/vice_big.py`).
- **Own test article for `Jensen Huang`:** `wiki_server.py --dir <folder>` with your own `jensen_huang.json`
  (the file on the disk stays untouched; in VICE the start article comes via the WiC64). Reload without the search field:
  write `WN_TITLE` (`$0C60`), `r pc=<h_fetch>`, `until main_loop`. Scroll position: `dv_pos` = `$1A86`.

- **Counting calls: `trace exec` reports nothing via the remote monitor** (count always 0, even where the call
  certainly runs). Instead use `break exec <adr>`, send `x` and count each prompt with this address and send `x` again, until
  no prompt arrives for a few seconds; then `del`. Do a control check with the old build (2026-11-22).

## Mouse (headless, no host mouse)

**Holding the left button through the real IRQ (dragging, 2026-11-23):** Port 1 without a mouse reads bit 4 = 1
("not pressed"). In `ms_buttons` (`gui_irq.s`, IRQ block from `$0.1300`) the sequence `lda ms_raw / and #$10 / eor #$10`
turns it into `ms_lb`; patch the operand of `eor` (`ms_buttons` + 29, check `49 10` at +28 first) to `$00`: the IRQ then
sees the button pressed, puts `K_MDOWN` with the position from `ms_x`/`ms_y` into the ring and keeps `ms_lb` set; `$10`
again releases it (`K_MUP`). Move the pointer meanwhile with `ms_x` (2 bytes), `ms_y`, `ms_seen` = 1 and `settle()`.
After `settle()` drain the socket before `peek` (old prompts). Example: `test/vice_draw.py`.

Set the GUI state via the monitor as the mouse IRQ produces it: `ms_x` (2 bytes), `ms_y`,
`ms_seen` = 1, entry `x, y, $55` in `ms_ring` (`$0B20` + `ms_wi`, then `ms_wi` += 4,
index 0-15; **only together with `K_MDOWN`**), `K_MDOWN` (`$81`) or `K_MUP` (`$82`) in
`kq_buf` (`$0B00` + `kq_head`, then `kq_head` += 1, index 0-31). Addresses from the
label file. Screenshot pixel = screen pixel + (112, 35).

**Simulating real 1351 movement (also tests the IRQ path):** x128 with `-controlport1device 3`, after startup
`bank ram00` (IRQ block `$0.1300`-`$0.1550`; the default view often shows bank 1 when halted, which holds something else) and in
`irq_entry` redirect the read instructions: `lda $D419` → `lda $0BF0` (`> <irq_entry> ad f0 0b`), `lda $D41A` → `lda $0BF1`
(`irq_entry`+6). Then increase `$0BF0` step by step (7 bits, each step < 64; +20 = 20 pixels to the right) and let it run
briefly: `ms_x` and `ms_seen` change, the pointer appears in the screenshot. If `ms_tick` (`$0.1547`) stands still, the IRQ is not
running: `io d000` shows the IRQ line (511 = never, see HANDOVER 27, `$D011` raster bit). (2026-11-22)

Menus and menu entries react to `K_MDOWN` alone; **buttons need `K_MDOWN` and then
`K_MUP`**. Screen coordinates (Mac look): "Hilfe" menu (125,15), entry "Über" (178,54),
QR button (611,30).

## Screenshots

- `screenshot` writes the file with a delay: only continue once it has content (`Vice.screenshot`
  does this), otherwise an empty PNG remains after x128 exits.

- Before a screenshot let it run for about 2 s, otherwise you get a half-built frame.
- Without `-warp` the startup of the Wikipedia reader takes about 100 s.
- Mac look only with 64 KB VDC (`-default` gives 64 KB, `vmon.py <d81>@64k`).

## Drive

- Written files are only completely in the image after `detach 8` (or exit).

## Network (WiC64 simulation)

- **`-userportdevice 23` must come AFTER `-default`**, otherwise `-default` switches the WiC64 off again
  (`x128.log`: "WiC64 enabled", then "WiC64 disabled"; the server sees not a single request).

- `x128 … -userportdevice 23` and `test/wiki_server.py` locally; build the parser image with
  `make WIKI_API=http://127.0.0.1:8080/w/api.php?`.
  **Without changing the checked-in .prg files:** copy the repo to the scratchpad (there is no `rsync` here:
  `cp -r` per entry except `.git`), overwrite `apps/wikipedia/wikiurl.inc` there with `.byte "http://127.0.0.1:8080/w/api.php?", 0`,
  call `ca65 -t none … wikiparse.s` and `ld65 -C wikiparse.cfg`, plus `wikipedia.s` with `-g`
  and `ld65 -C ../../demo_mac/demo.cfg -Ln w.lbl` (label file; `wikipedia.prg` is byte-identical to the checked-in one),
  `tools/mkd81.py` with these PRGs. Everything in the repo stays unchanged.
- **The start article has been "Hauptseite" since 2026-11-22** (`action=expandtemplates`, `test/wiki_server.py` answers with `hauptseite.json`
  from `--dir`, otherwise `apps/wikipedia/hauptseite.json`; disk: `JSON,S` = `hauptseite.json`). The "Inhalt" popup does not exist for it.
  Tests that need an article load it themselves after startup: write `WN_TITLE` (`$0C60`), `r pc=<h_fetch>`, `until main_loop`
  (`test/vice_toc_popup.py` loads "Jensen Huang" this way). "Zurück" (back) to the start page reloads the Hauptseite. `jensen_huang.json` remains for tests.
- `test/wiki_server.py` supports `section=N` (the Nth section including subsections, headings counted in
  order) and `--sections FILE` (section list for every title). Generate test wikitext with the headings of
  a fixture (`test/fixtures/sections/*.sections.json`), then `section=N` and the list match.
- Link coordinates (Mac look, article at the top): line 0 is at screen y = 46; read x from a screenshot
  (screenshot pixel - 112). One click takes about 25-30 s in wall-clock time (connect/disconnect, `run_for`).
- **The parser PRG in the repo points to `de.wikipedia.org`** (`wikiparse.prg` is built with the `WIKI_API` of the Makefile). The local server then gets no request (log empty, the reader nevertheless appears "loaded", then from `JSON,S`). Network tests: build the parser in a copy with `wikiurl.inc` = `http://127.0.0.1:8080/w/api.php?` (2026-11-21).
- **`tools/vtest.py` kills every `x128` and the server on port 8080** (`pkill -x x128`, `pkill -f "[w]iki_server.py --port 8080"`). A run therefore disturbs parallel VICE/server runs of other agents, and vice versa. Only start if no other `x128` is running (`pgrep -x x128`). Another run active: wait, do not kill (2026-11-21).
- **WIKITEXT in VICE (2026-11-21):** own D81 with `tools/mkd81.py img "WIKIPEDIA" WI w.prg=WIKITEXT wikiparse.prg=WIKIPARSE,S wic64drv.prg=WIC64DRV,S jensen_huang.json=JSON,S`
  (WIKITEXT as the first file, `vtest.Vice` starts the first PRG). Label file: `ca65 -g wikipedia_t.s` and `ld65 -C ../../demo/demo.cfg -Ln w.lbl`
  (byte-identical to `wikipedia_t.prg`). 16 KB: `Vice(..., vdc64=False)`; without WiC64: `server=None` (fallback to `JSON,S`, message "WiC64 antwortet nicht.").
  Search as in the Mac look: title to `WN_TITLE` ($0C60), `r pc=h_fetch`, wait for `main_loop`.
- **guic assigns handler numbers by first occurrence in the file** (menu items count too): a text-mode menu item with its
  own handler (e.g. `MemoryInfo` in "Hilfe") gets the number at its position, not at the end. That is why
  `wikipedia.s` has `HX = WIKI_TEXT`: in the text build `h_memory_info` is no. 6 after About and all following numbers are +1.
  Hotkeys (`&S`) must be unique per form (label "&Suche:" and button "Suchen" without `&`).
- The real Wikipedia answers many rapid requests with HTTP 429.

## History in text mode (2026-11-21)
- **Mouse: K_MUP does not write a ring entry.** Advance `ms_ring`/`ms_wi` only together with `K_MDOWN`
  (`gui_mouse` fetches the entry only on press, `ms_ri`). If you also write the ring for `K_MUP` (button: DOWN, then UP),
  the next click reads the old position: the menu then seemingly does not open.
- Text build, pixel = cell * 8: button "<" (20, 20), menu "Verlauf" (history) (100, 12), entry 1 in the dropdown (110, 31).
  `hist_count`/`hist_cur` are equates (`$1BF0`/`$1BF1`), not in the label file.
- **Text driver: `gui_setcaption($FF)` redrew only " Titel " (title), not the frame line** (remnants of the old title, `Wi … rs`).
  Since phase 6 it first draws the top frame line (`gc_topline`, `gui_core.s`); the padding to 70 characters in
  `set_article_caption` is gone.

## "Inhalt" popup in text mode (2026-11-21)
- `test/vice_toc_popup.py` also drives the text build: `WIKI_TEXT=1` (click on "Ende" at (60, 36)), `WIKI_VDC16=1` for 16 KB.
  `dv_pos` is at `$1A86` in both builds (`DV_VB` area, not in the label file).
- **Text build, mouse row:** row 0 = window title, 1 = menu bar, controls with `Top = 0` are in screen row 2
  (search row: y = 20, not 12). "Inhalt" button (columns 62-71): `K_MDOWN` and `K_MUP` at (528, 20).
- `cap_buf` is no longer padded in the text build (since phase 6); the `.strip()` in the tests does no harm.
- After `v.settle()` the emulation is already halted; an additional `v.stop()` before `peek` swallows the prompt
  (empty list, `IndexError`). After `screenshot()`, on the other hand, call `v.stop()` once before `peek`.

## QR for images in text mode (2026-11-21)
- **Checking a QR screenshot without a decoder:** `pyzbar`/`zbarimg`/`cv2` are not installed (venv/pip is rejected by auto mode).
  Read the module grid from the screenshot and compare it against `test/qr_ref.encode(url)`: the text QR has 8 pixels per module in
  width and 4 in height (half block), dialog `frmQR` in the screenshot at about x 240-620, y 55-215. For a phone scan, stretch the
  screenshot vertically by a factor of 2 (on a real 4:3 monitor the modules are approximately square).
- **Clicking an image link in text mode:** `[[Datei:Name.jpg|thumb|x]]` at the very top of the test article (`jensen_huang.json` via `--dir`), the
  link is called `[Bild: x]`, click at (40, 36) as with "Ende" in the Inhalt test. The file name may have at most about 74 characters
  (base `http://127.0.0.1:8080/wiki/File:` = 32 of 106 bytes), otherwise "Link zu lang für den QR-Code."; 65 characters give V5.
- **Button click to close via mouse state** (`K_MDOWN` then `K_MUP`) did not trigger the OK button of `frmQR` in the attempt, RETURN was
  also lost (known key losses); closing is not verified in VICE (Python test `wiki_click.py` calls `gui_close`).

## Phase 7a/7b and remaining points, text mode (2026-11-21)
- **`test/vice_big.py`** loads titles against the local server (`--dir`) or the real Wikipedia (`WIKI_NOSERVER=1`, then
  `-userportdevice 23` without a server; HTTPS works via the WiC64 simulation), measures `mw_text_len` (`$10`), `dv_count` (`$0C18`),
  `dv_source_end`/`dv_raster_next`/`dv_dir_next` (`$0C1E`/`$0C1C`/`$0C1A`), `WK_LOADED`, `dv_maxpos` (`$1A84`). **One title per run**: a
  second title after a screenshot/scroll hangs (swallowed prompt, `until` runs into the limit).
- **Scrolling to the end of the document without a key:** stub in the buffer `$0700`: `lda #8 (FRMMAIN_VSBDOCUMENT)`, `ldx #$10 (PROP_VALUE)`,
  `jsr gui_set`, `jsr document_view_scroll`, `jmp main_loop`; beforehand `zp_val` (`$69`) = `dv_maxpos`, `r pc=0700`, then
  `settle(4)` (not `until main_loop`: it is not reached afterwards). With `$FFFF` as the value it does not work. Against the real Wikipedia
  `dv_pos` stayed 0 (not clarified).
- **Monitor text in the text screenshot:** After `r`/`break` the monitor output (cyan) appears in the VDC screenshot if the screenshot
  comes directly afterwards: only a display artifact, not a program error.
- **Text build, keys in dialogs:** `keybuf` with RETURN/TAB is lost in the dialog (`frmQR`) or does not reach `main_loop`. Write the key directly into `kq_buf`
  (`$0B00 + kq_head`, `kq_head` += 1, then `settle(1.5)`): RETURN closes `frmQR`, background fully restored.
  A test problem, not a program error.
- **Mouse on OK in `frmQR` (text):** click at (490, 88) (K_MDOWN, `settle`, K_MUP) closes the dialog; (488, 96) is one row
  too low. Screenshot row 131 = screen y 96 is the row *below* the OK text; pixel y of the text row = (screenshot y - 35) - 8.
- **Other agents' x128 runs:** `pgrep -x x128` can be occupied again between two calls; put the wait loop and the start in one command.

## Color dialog and color styles in text mode (2026-11-21)
- Script: `test/vice_text_colors.py <d81> <labels> <folder>` (without WiC64, article from disk; `WIKI_VDC16=1`, `WIKI_SAVED=1` with
  `GUICOLTXT` on the D81 (Mac look: `GUICOLORS`): `printf 'GC\001\002\015\002' > g.seq`, in `mkd81.py` as `g.seq=GUICOLTXT,S`).
- **An open dialog does not reach `main_loop`** (`gui_dlgcolor` waits itself in `gui_wait`): after every key use `v.settle()` and read the
  state (`gui_colflags`, `gui_colfg`, `gui_colbg` are consecutive; `stack_n` = 2 means dialog open), if needed repeat the key
  once (`key()` in the script). Only RETURN/ESC leads back to `main_loop`.
- **Lists in the dialog via the initial letter** instead of many cursor keys (identical keys in a row get lost): `W` = white,
  `D` = next entry with D (dark gray, dark blue, …). TAB switches the control. On the second opening the focus is where it was.
- **Checking the window title without network:** write `WN_TITLE` (`$0C60`), place `jsr set_article_caption : jmp main_loop` at `$0A40`,
  `r pc=0a40`, wait for `main_loop` (`caption()` in the script).
- **Emulator (`test/wiki_text.py`):** `App.call` puts its code at `$0B00` (= `kq_buf`). So write keys for an open dialog directly into
  `kq_buf`/`kq_head` and keep running until `gui_idle` = 1 and the buffer is empty (`App.key`); call `App.call` again only when the dialog is closed.
  The kernal substitute of the wiki tests cannot write: `KernalW` in `wiki_text.py` adds CKOUT/CHROUT for `gui_colsave`.

## Phase 7c: loading sections on demand (2026-11-21)
- **`test/vice_big.py` waits by itself** (at most `WIKI_WAIT` s, default 120) until no foreign `x128` is running any more, and then starts
  immediately. New: `WIKI_TOC=1` (after loading F3, screenshot `<title>_toc.png`, loaded range `tc_lo`..`tc_hi`-1 from `$0E66`/`$0E67`),
  `WIKI_SRV="--busy 4"` (options for the server), `WIKI_REALTIME=1` (load without warp), duration via the stopwatch of the monitor
  (`sw reset` before `r pc=`, `sw` after the breakpoint: emulation cycles, 985,248 per second; the wall clock says nothing in warp).
- **`test/wiki_server.py` computes the section list itself** from the wikitext of the file (`level`, `number`, `index`, `byteoffset`,
  `anchor`) if no `--sections` is given: list and `section=N` then match (needed for loading on demand).
  `--busy N` answers every Nth article/section/list request with HTTP 429.
- **Message of the WiC64 simulation on HTTP errors: "http response: 429"** (not "429 Too Many Requests"). The parser therefore searches
  only for the digits "429" in `WN_MSG`.
- **Which URLs went to the real Wikipedia?** `-wic64tracelevel 1` (set by `vice_big.py` with `WIKI_NOSERVER=1`): `x128.log` in the folder
  of the D81 contains "got N bytes, URL: '…', http code = 200" for each fetch. The last lines are missing if `x128` is terminated before the
  log is written.
- **Loading against the real Wikipedia without warp:** monitor command `warp off` before loading, `warp on` afterwards. In warp the requests follow
  each other within milliseconds (the parser's pauses are counting loops), then HTTP 429 threatens. Zürich: 8 requests in 12-14 s, no 429.
- **F3 after loading is sometimes lost twice in a row** (2 of 7 runs, with and without warp switching; `until` runs into the
  limit, `vice_big.py` then reports the PC and writes `fehler.png`). Repeat the run: the next time the key arrived.
  Once the monitor also did not respond right after startup ("kein Monitor-Prompt nach 5 s", no monitor prompt after 5 s): also repeat.
- **Reading parser variables in bank 1:** `bank ram1`, then `m <address>` returned a wrong value for `wk_lhi` (133 instead of 7; cause
  not clarified). Better to check via the shared RAM: F3 opens the popup, afterwards `tc_count`/`tc_lo`/`tc_hi` are in `$0E65`-`$0E67`.
- **Responses from 64 KB up only with protocol "E" (2026-11-21, 7c-new):** With "R" the WiC64 simulation sends the length as
  `len & 0xffff` (`send_reply_revised` in `userport_wic64.c`), but the data completely: Zürich (216 KB) would arrive as a "complete"
  7 KB response. The driver therefore fetches articles with "E" (6-byte header, 5-byte response header with 32-bit length).
- **Ending a fetch early:** If the host stops reading after `WN_LIM` bytes (`wic64_finalize`), VICE discards the rest
  as soon as PA2 goes high again (log "discarding N bytes"), the next request goes out without a wait. The transfer timeout of the
  WiC64 plays no role in VICE here; not verified on real hardware.
- **Several titles in one run (7c-new):** loading, F3, ESC, loading a second title worked in one run if the
  socket is drained before every `peek` (also directly after `until`), ESC only with `key` + `settle` (script modeled on `test/vice_big.py`).
- **WIKITEXT: F3 directly after loading did not arrive in two runs in a row** (focus in the search field, no request, `tc_*` unchanged).
  Solution: "Inhalt" button via mouse state at (528, 20), `K_MDOWN`, `settle`, `K_MUP`, then `settle(6)`: the open dialog waits in
  text mode in `wait_round`, `main_loop` is only reached after closing (so not `until`). ESC afterwards with `key` + `settle` (2026-11-21).
  In the Mac look, F3 after loading was also lost once (the server saw no list request): there too, rather click the button
  or send F3 with a retry.
- **Test article:** `zürich.json` (203 KB, format `{"parse":{"wikitext":{"*":…}}}`) in the data folder of `--dir`; the file name is the
  title in lowercase, umlauts as UTF-8.

## Stage 7d: VDC RAM from $4000 (2026-11-21)
- **Text mode + 64 KB VDC: the kernal does not set VDC register 28 bit 4** (`$2F`). Without the bit, $4000 mirrors the screen $0000.
  If you set it afterwards, the mapping of the addresses to the chips changes (VICE: screen/attributes start differently from byte 256).
  For tests: set bit 4 at the `drv_init` breakpoint (stub `r28_stub` in `test/vice_xs.py`, jumps back to `drv_init`), then everything is created in 64 KB mode.
  A restart via `jmp start` hung (main_loop not reached).
- **Monitor lines are cut off at about 85 bytes:** split `>` with more than about 24 bytes per command into pieces (stubs, URL in the buffer).
- **Bank 1 cannot be displayed in the monitor** (`bank ram1` does not exist; banks: default cpu ram rom io ram00-01 intfunc extfunc cart c64rom vdc).
  Compute a checksum (Fletcher) in a stub and read it. VDC RAM: `bank vdc`, `save "file" 0 4000 ffff` (2 bytes of load address in front).
- **Stubs without `stx`:** `ldx #28` followed by `sta $D600` writes A, not X, into the register (it clobbered VDC registers without an error message).
- Shared scratchpad: create your own files in a subfolder (`mk.sh`, `t.sh`, `wt` belonged to other runs).
## 7c-new: tests and popup (2026-11-21)
- **The "Inhalt" button keeps the focus:** After a click on the button (mouse state `K_MDOWN`, `K_MUP`) the keyboard focus is on the button.
  A later RETURN (e.g. "Öffnen" in the popup via `keybuf`) then opens the popup again after loading (follow-up tests see it as an open
  dialog, `dv_pos` stays 0). Solution: after closing, click once into the canvas (`click(300, 100)` in `test/vice_toc_popup.py`), then F3.
  The first call of the popup after startup goes via the button (F3 is often lost there), `open_popup()` in the script.
- **Popup in `test/vice_big.py`:** `WIKI_TOC=1` clicks the button (Mac look (540, 30), text (528, 20); `WIKI_TEXT=1`), waits `settle(6)` (the open dialog
  does not reach `main_loop`), reads `tc_*`, counts the requests for the popup (1: only `prop=sections`), ESC with `key` + `settle`. After that the
  second title runs in the same run (Zürich, then Jensen Huang: 1 request each). `WIKI_MARK=1`: instead of ESC set `tc_sel` (`$0E68`) to the last entry, RETURN
  in `kq_buf`: for Zürich "Liste gekürzt", no request, the text scrolls to the last loaded entry.
- **VICE startup sometimes fails** ("kein Monitor-Prompt nach 30/40 s", no monitor prompt after 30/40 s, empty `x128.log`) if a CPU-heavy Python test is running at the same time
  (`wiki_wic64.py` needs a good 3 minutes). Not a program error: repeat the run, do not start VICE runs in parallel with the emulator tests.
- **`test/wiki_wic64.py` takes a good 3 minutes** (Mac as well as text): start it with `run_in_background`, do not wait in the foreground.

## Stage 7d built in: testing window switches (2026-11-21)
- **Script:** `test/vice_xs_view.py <d81> <labels> <data folder> <output>` (WIKITEXT 64 KB with Zürich; `WIKI_VDC16=1`, `WIKI_MAC=1`
  with the Mac image only loads). Since `GUI_TVRAM64`, WIKITEXT sets R28 bit 4 itself: no `r28_stub` needed any more.
- **Do not put stubs at `$0700`:** that is `dv_textbuf`, drawing overwrites the stub before its `jmp main_loop` is reached. That was the cause
  of "`until(main_loop)` is not reached here" with the stub for the document end (section 7a/7b above). Put stubs at `$0A40` (16 bytes per `>` command),
  then `until("main_loop")` works and the stopwatch measures the switch.
- **Key without `keybuf`:** call the OnKey handler directly: stub `ldy #$11` (cursor down) or `ldy #$91`, `jmp h_document_key`; beforehand set the scrollbar
  to the end via `gui_set` (`zp_val` = `dv_maxpos`, `lda #8 : ldx #$10 : jsr gui_set : jsr document_view_scroll`). Ends in `main_loop`.
- **RETURN in the popup via `kq_buf`, then `until("main_loop")`:** after `tc_close`, `h_toc_open` (including the window switch) runs to `main_loop`, waiting
  for it worked (fallback `settle`). Set `tc_sel` (`$0E68`) beforehand.
- **Startup with stage 7d takes longer** (start article via the WiC64 into VDC RAM, copying the window). The first run reported "`main_loop` not reached
  after 40 s" and the server saw no request while two Python emulator tests were running at the same time; without load it worked immediately. As above:
  not VICE in parallel with the emulator tests.
- **`screenshot` directly after `settle`** failed twice in a row in one run (empty file): with `shot()` (retry after `v.stop()`)
  it worked; the second attempt is enough.
- **VDC registers in the monitor:** `io d600` lists all VDC registers (R28 = register `$1C` = 13th byte of the line `10:`); after
  quitting, R28 must be `$2F` again. `r pc=h_quit` (jump from the middle of `gui_wait`) ends with "?TYPE MISMATCH ERROR IN 10" (stack does not match
  the `SYS` return): only a test artifact, screen and character set are fine afterwards.

## Stage 7d and test scripts (2026-11-22)

- **`test/vice_toc_popup.py` in WIKITEXT with 64 KB:** the check "exactly one section=N request after RETURN" always fails
  (also on `main`): with stage 7d the whole article is in VDC RAM, the jump from the popup goes via `TCOP_BOFS` without network.
  Test the network path with text mode and `WIKI_VDC16=1`, and use `test/vice_xs_view.py` for 7d.
- **`test/vice_xs.py`:** "xs_probe with bit 4 off (kernal state)" also fails on `main` (C = 1). An old error, do not attribute it to
  your own rework; the other checks are valid.
- **Checking bank 0 RAM under the ROM:** in the monitor `bank ram00`, then `f c000 feff a5` at the breakpoint on `start`, later
  read with `m` in blocks of 1 KB (`bank default` afterwards). Bank 0 is correctly selected if the pattern is there after filling
  (the ROM would show other values, bank 1 would have the parser at `$C800`).


## Loader with splash screen (2026-11-22)
- **Breakpoint in the address range of the loader:** If the disk starts via the loader `WIKIPEDIA` (`$1C01`-`$1E3A`), low
  labels of the program (e.g. `main_loop` = `$1CE4`) lie in the middle of the loader: `until("main_loop")` already stops there, an `r PC=…`
  afterwards jumps into empty memory. First `until("splash_take")` (Mac) or `until(0x0B30)` (loading part) and only then
  `until("main_loop")`.
- **`until()` directly after `screenshot()`** ran into the time limit twice in a row (`main_loop` not reached after 60 s) although
  the program started normally without breakpoints: the remaining prompts in the socket mix up command and reply. After the
  screenshot wait briefly and call `v.stop()` once, then `until()`; with that it worked immediately.


## PRG injection, sound, sim65 (2026-11-23, `apps/sidsfx`)
- **No monitor stop while a PRG is being injected (`-autostartprgmode 1`):** `until()` right after the start never reached
  its breakpoint (limit 40 s), and stopping every 0.5 s to look at the PC kept the program from ever starting, although it
  ran to its end within 4 s when left alone. Solution: let it run first (`v.settle(4)` or `go`, `sleep(3)`, `stop` in a
  bounded loop that compares the PC with the end label), only then use the monitor (`test/vice_timing.py`).
- **The default memory view shows the BASIC ROM at `$4000`-`$BFFF`** whenever the emulation happens to be stopped inside
  the Kernal (`$FF00 = $00`), also for a program that itself runs with `$FF00 = $0E`: reads of program data there were
  right in most runs and ROM text in others. Always `bank ram00` before reading RAM, `bank io` for `$D030` and other
  registers (`peek()` in `test/vice_demo.py`).
- **Draining:** after `settle()`/`stop()` every reply came one command late (`r` printed nothing, `save` seemed to do
  nothing). Read the socket empty (timeout 0.3 s) before each command whose reply is needed.
- **Recording sound:** `-sounddev wav -soundarg file.wav` writes nothing in warp mode (44 bytes). Run without `-warp` and
  end with `-limitcycles` (8,000,000 cycles = start, autostart and about 3 s of the program). The file is 48 kHz mono;
  a frequency can be measured by counting zero crossings (`test/vice_timing.py`, no numpy on this machine).
- **"t_done not reached" although the program had finished long ago (2026-11-23):** `test/vice_timing.py` polled with
  `go`, `sleep(3)`, `stop` and compared the PC of the prompt. `go` sent while the emulation runs and every `stop` leave
  one or two prompts in the socket, `stop` returns the first one it finds, so the PC it reported was that of an earlier
  stop and fell further behind with every round; on a machine under load (other agents, load 9) that failed every
  time, also with the unchanged code. Longer waits did not help. **Solution:** read the socket empty before the `stop`
  whose PC is used (`drain()` in `test/vice_timing.py`); the program was at its end label after the first 3 s.
- **A fixed `settle(4)` after the start is too short on a loaded machine:** with load 9 the Oscar64 example was not
  even injected after 4 s (memory still `00 FF FF ...`), so all its checks failed. `test/vice_demo.py` now repeats the
  4 s (at most four times) until the program has hooked the IRQ vector; a stop during boot did not keep it from
  starting.
- **What is in a recorded WAV:** the autostart runs in warp mode and is not recorded, so the file starts about 0.1 s
  before the first sound of the program (not with the reset); its length is the run minus about 5 s. The offset
  differs by 20 ms between runs: take times relative to an event in the recording, never absolute. Recording is
  cycle exact also on a loaded machine (the log is full of "Sound buffer overflow", the samples are right).
  x128 uses reSID 8580 by default, `-sidenginemodel 256` is the 6581.
- **The envelope of a new note starts 33 ms late (ADSR delay of the SID, emulated by reSID):** a recording shows the
  first sound of a note with attack 0 about 33-35 ms after the register write whenever the old decay or release
  period was longer than the counter value, i.e. almost always. Anything that has to happen "in the first tick" of a
  note (a different waveform, a different sustain) is over before the envelope opens. A few notes start at once
  instead, always the same ones for a given timing (the rate counter is locked to the frame): in one run 3 of 7 snare
  notes. `apps/sidsfx/FORMAT.md` 3.9; measure with `apps/sidsfx/test/vice_volume.py`.
- **Gate off and on again at envelope level 255 gives a silent note** (attack counts 255 -> 0 and freezes; reSID
  emulates it): seen with a note retriggered out of sustain 15 when no release step fell between the two writes.
- **"No waveform" is not silence:** control `$01`/`$09` with the gate on puts the voice's DC level times the envelope
  on the output, a click as large as a full-level triangle when the attack runs (8580).
- **Time base that does not change in FAST mode:** the CIA timers keep counting 1 MHz cycles at 2 MHz. Timer B of CIA 2
  counting the underflows of timer A (`$DD0F = $51`, `$DD0E = $11`) gives a 32-bit cycle counter (`test/timing.s`).
- **`x128 -ntsc`** switches the machine to NTSC (263 lines of 65 cycles, clock 1,022,727 Hz), `-pal` back.
- **sim65 2.18 executes `ROL abs,X` (`$3E`) with the wrong length** (continues in the middle of the operand: "Illegal
  opcode" somewhere else). `ASL`/`LSR`/`ROR`/`INC`/`DEC abs,X` are right. Avoid the opcode in code tested with sim65
  (macro `rolx` in `apps/sidsfx/player/player.s`).
- **cl65 deletes `name.s` after compiling `name.c`:** an assembler file of the same name in the same directory is gone
  afterwards. Use different names.

## Several agents on one machine (2026-11-23)
- **`pkill -x x128` and the shared monitor port 6510 end or take over the runs of other agents** (`tools/vtest.py` did
  both in `Vice.__init__`). Symptoms: "Broken pipe" / "Connection reset" in the middle of a run, a monitor that answers
  with the state of a different program. **Solution:** `VICE_PORT=<own port>` (e.g. 6540): `vtest.Vice` then uses that
  port and kills nothing but its own process in `close()`. Never `pkill`/`killall` by hand while others are testing.
- **Protection against the `pkill -x x128` of others:** `VICE_X128=<path>` names the emulator binary. A symbolic link to
  `x128` under another name (`ln -s $(which x128) $SCRATCH/bin/x128sfx`) gives the process that name, VICE still finds its
  ROMs, and `pkill -x x128` no longer matches it. `apps/sidsfx/test/vice_timing.py` honours both variables too.
- **A key that toggles something cannot be retried:** `keybuf` loses keys now and then, so tests send a key again if its
  effect is not seen; with a toggle a late first key plus the retry switches twice. Give test-relevant functions one key
  per direction (`apps/sidsfx/oscar/game.c`: N = note on, B = note off).

## Startup wait, bank 1 writes, half-drawn frames (2026-11-23, `test/vice_blank.py`)
- **`until("main_loop")` right after `Vice()` can miss the startup:** `main_loop` is passed only once, and the emulation
  may already be past it when the monitor attaches (the run then waits for its limit). Wait for the idle loop instead:
  `until("wait_round")` is hit again and again once the GUI idles.
- **Writing bank 1 from the monitor:** `bank ram01` (not `ram1`; `bank` lists the names), then `> 1000 ...`, then `bank default`.
  Example: replacing the JSON at `$1.1000` at the `wiki_decode_json` breakpoint.
- **A screenshot at a breakpoint shows a half-drawn frame** (new content at the top, old at the bottom, so "canvas blank"
  looks wrong). Put `4C 34 03` (`jmp *`) in the cassette buffer `$0334`, `r pc=0334`, `settle(0.3)`, screenshot, `stop()`,
  then set `pc` back to the breakpoint address (`shot_halted()` in `test/vice_blank.py`). VDC RAM is not touched by the loop.
- **Network error without a special server:** `v.srv.kill()` (the WiC64 then answers "Unhandled http response", `wn_fetch` returns C = 1).

## Presses queued during a load (2026-11-23, `test/vice_dblclick.py`)
- **Simulating a second click while a download/layout runs:** click 1 with ring entry + `K_MDOWN` as usual, then `until("document_view_init")`
  (inside the load, interrupts are on again there), `stop()`, write the second ring entry (`ms_ring` + `ms_wi`, with the current `ms_tick`)
  and `K_MDOWN` into `kq_buf`, add a key (`$11`) behind it, then `until("wait_round")` and `settle(1.5)`. The new page must have a link at the
  second position, otherwise the press hits nothing and the test shows no difference. Link positions: Mac look screen x = 5.3 px/char
  from x = 16, text build 8 px/char; check once with a screenshot (pixel = screen pixel + (112, 35)).

## Calling a routine from the monitor, busy pointer (2026-11-23, `test/vice_busy_col.py`, `test/vice_busy.py`)
- **Run a routine of the program on demand** (e.g. `gui_busy`): `until("wait_round")`, poke a stub `20 lo hi ... 4C end end` (JSR per routine, then
  `jmp *`) at `$02B0`, `r pc=02b0`, `until(end)`, check, then `r pc=<wait_round>` and continue. Stack and registers stay valid because the JSRs are balanced.
- **Check pointer pixels in VDC RAM, not in a screenshot:** `bank vdc`, `m <y*80+col> ...` (bitmap: 80 bytes per pixel row) or `save "f" 0 0 ffff` for a
  whole dump (compare before/after). A screenshot at a breakpoint is stale (see above: `jmp *` loop at `$0334`, `shot_halted()` in `test/vice_busy.py`).
- **First start of a bare PRG (no D81) sometimes does not reach `wait_round` within 30 s** (once in about 10 runs, `vice_busy_col.py`); a rerun works.

- **Screenshot after a `keybuf` fails ("nicht geschrieben")** (2026-11-24): the emulation is halted at the monitor without a finished frame.
  **Solution:** after the key(s) `v.until("wait_round")`, then `v.settle(0.8)`, then the screenshot; on `ViceError` once `v.stop()` and retry.
  Cursor down (`$11`) scrolls about one line per key, one `keybuf` call takes 9-10 keys: loop key + `until("wait_round")` to scroll further.
- **`Vice(server=...)` runs `pkill -f "[w]iki_server.py --port 8080"`** (2026-11-24): it ends the WiC64 simulation of other agents on port 8080 even
  though the x128 itself is not touched. Run only one server user at a time.
- **`expandtemplates` start-page URL: count the full URL** (2026-11-24): `WD_URL_MAX` = 250 applies to base (35 characters) plus remainder; the
  README quotes the full length. Without `prop=wikitext` the answer has no `"wikitext"` key (legacy `"*"`).

## curl and `{}` in test URLs (2026-11-24)
- The start page URL contains `{{` and `}}`. `curl` treats them as URL globbing and fails or sends a different request. Use `curl -g` (`--globoff`) when trying a `wk_home` query by hand.
- **Mac look from the D81: `until("main_loop")` stops inside the splash loader** (2026-11-24): the loader `WIKIPEDIA` also runs at `$1C01`
  and its code covers `$1CE2` (`main_loop` of `WIKIPEDIA.APP`), so the breakpoint fires before the app is loaded (screenshot shows the splash).
  **Solution:** first `v.until("set_article_caption", limit=120)` (`$1F0A`, beyond the loader), then `v.until("main_loop")`.
