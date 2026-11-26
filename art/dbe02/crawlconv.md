# crawlconv: Crawl 128 auf Engine 0.2

DVG: 68 x 96, D = 3, S = 1, stride 80, origin 406, Geometrie-ID 0x5a82, Horizont [0, 95), 28 Elemente

## Elemente

| # | Art | d | s | Flags | x | y | w | h | c0 | c1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Seite | 0 | -1 | 1 | 0 | 0 | 9 | 96 | 0 | 9 |
| 1 | Seite | 0 | +1 | 1 | 59 | 0 | 9 | 96 | 59 | 68 |
| 2 | Front | 1 | +0 | 9 | 9 | 0 | 50 | 96 | 9 | 59 |
| 3 | Obj | 1 | +0 | - | p2 (34,75), p3 (30,48) | | | | | |
| 4 | Front | 1 | -1 | 9 | 0 | 0 | 9 | 96 | 0 | 9 |
| 5 | Seite | 1 | -1 | 1 | 9 | 0 | 10 | 96 | 9 | 19 |
| 6 | Obj | 1 | -1 | - | p2 (6,69), p3 (3,48) | | | | | |
| 7 | Front | 1 | +1 | 9 | 59 | 0 | 9 | 96 | 59 | 68 |
| 8 | Seite | 1 | +1 | 1 | 49 | 0 | 10 | 96 | 49 | 59 |
| 9 | Obj | 1 | +1 | - | p2 (56,69), p3 (53,48) | | | | | |
| 10 | Front | 2 | +0 | 9 | 19 | 0 | 30 | 96 | 19 | 49 |
| 11 | Obj | 2 | +0 | - | p2 (34,59), p3 (25,39) | | | | | |
| 12 | Front | 2 | -1 | 9 | 0 | 0 | 9 | 96 | 0 | 9 |
| 13 | Front | 2 | -1 | 0 | 9 | 0 | 10 | 85 | 0 | 0 |
| 14 | Seite | 2 | -1 | 1 | 19 | 0 | 5 | 96 | 19 | 24 |
| 15 | Obj | 2 | -1 | - | p2 (16,56), p3 (15,39) | | | | | |
| 16 | Front | 2 | +1 | 9 | 49 | 0 | 10 | 96 | 49 | 59 |
| 17 | Front | 2 | +1 | 9 | 59 | 0 | 9 | 96 | 59 | 68 |
| 18 | Seite | 2 | +1 | 1 | 44 | 0 | 5 | 96 | 44 | 49 |
| 19 | Obj | 2 | +1 | - | p2 (46,56), p3 (45,39) | | | | | |
| 20 | Front | 3 | +0 | 9 | 24 | 0 | 20 | 96 | 24 | 44 |
| 21 | Obj | 3 | +0 | - | p2 (34,59), p3 (25,39) | | | | | |
| 22 | Front | 3 | -1 | 9 | 9 | 0 | 10 | 96 | 9 | 19 |
| 23 | Front | 3 | -1 | 9 | 19 | 0 | 5 | 96 | 19 | 24 |
| 24 | Obj | 3 | -1 | - | p2 (16,56), p3 (15,39) | | | | | |
| 25 | Front | 3 | +1 | 9 | 44 | 0 | 5 | 96 | 44 | 49 |
| 26 | Front | 3 | +1 | 9 | 49 | 0 | 10 | 96 | 49 | 59 |
| 27 | Obj | 3 | +1 | - | p2 (46,56), p3 (45,39) | | | | | |

Anker: p = 2 (Mitte) Edelstein, p = 3 (vorne links) Geist, Byte-Spalte und Zeile relativ zum Fenster; Tiefe 3 = Werte der Tiefe 2.

## Dateien

| Datei | Bank / Ziel | Byte |
|---|---|---|
| crawl.dmp | Bank 1 $4000 | 818 |
| crawl.dvg | Bank 1 $E800 | 506 |
| gem.s2 | Bank 1 $7000 | 69 |
| gem.vrl | Bank 0 bei BE, per RXV | 33 |
| ghost.s2 | Bank 1 $6000 | 1254 |
| ghost.vrl | Bank 0 bei BE, per RXV | 393 |
| walls.dts | Bank 1 $8000 | 545 |
| walls.vrl | Bank 0 bei BE, per RXV | 6050 |

VRL-Teile der Wandbilder: N = 1 (--max-part 0).

## VRAM (2.3)

| Name | Adresse | Byte |
|---|---|---|
| CA Zeichensatz | 19200 | 1732 |
| DA Wand-DTS-Daten | 20932 | 22354 |
| GA(0) Geist | 43286 | 1882 |
| GA(1) Edelstein | 45168 | 36 |
| GA(2) = MA Automap | 45204 | 440 |

Ende 45644, Grenze 46335, Reserve 691 Byte.
