# Worked example: Moss Harbor saves

Moss Harbor is an invented offline fishing game; its `.mhs` save files are built by `make_samples.py` so you can replay every step. The numbers below are the real tool output on those files.

## 1. Case card

```
File:        *.mhs from Moss Harbor 1.4 (offline, single player), Windows
Ownership:   my own saves on my own PC
Question:    export my catch log to CSV; find where coins are kept
Done means:  READABLE for the catch log, EDITABLE for coins
Stop lines:  encryption, anything online, other players' data
```

## 2. Is it new?

```
$ python3 scripts/rosetta.py survey samples/*.mhs
== samples/s01_base_a.mhs  31 bytes  entropy 3.86 bits/byte
   0x000000-0x00001f  MIXED  31 bytes
...
== shared prefix across 6 samples: 7 bytes; sizes: [31, 37, 50, 56]
   sizes differ: look for counts, lengths or variable records
```

No known signature, nothing dense, sizes differ. A web search for the extension and the game name finds nothing. The format is new.

## 3. Specimen shelf

| sample | made by | prediction written first |
|---|---|---|
| s01_base_a | baseline save | - |
| s02_base_b | saved again one minute later, nothing changed | only clocks and seals move |
| s03_coins_125 | sold a perch: coins 120 to 125 | one number rises by 5 |
| s04_one_more_fish | caught an eel (910 g) | file grows by one record, a count goes 1 to 2 |
| s05_long_name | renamed "Ina" to "Ina of the Reeds" | a length goes 3 to 16, later bytes shift by 13 |
| s06_new_rod | bought a rod (coins 125 to 98), caught a pike with it | count 3, a rod id 2 appears |

## 4. Twins first

```
$ python3 scripts/rosetta.py diff s01_base_a.mhs s02_base_b.mhs
CHANGE 0x00000f len   1  80 -> bd  le 128->189 (delta +61)
CHANGE 0x00001b len   4  b4 86 8b a1 -> 5e b1 0d 2b
```

One byte moved by 61 in a save made 61 seconds later. Reading 0x0f to 0x12 as a 32-bit little-endian number:

```
$ python3 scripts/rosetta.py find s01_base_a.mhs 1792828800
u32le          1 hit(s): 0xf
```

That is the save time in Unix seconds, matching the clock in all six samples: `saved_at`, P2. The last four bytes change chaotically: a seal candidate.

## 5. Dial turns

```
$ python3 scripts/rosetta.py diff s02_base_b.mhs s03_coins_125.mhs --twins s01_base_a.mhs s02_base_b.mhs
SIGNAL 0x00000b len   1  78 -> 7d  le 120->125 (delta +5)
NOISE? 0x00000f len   2  bd 65 -> ac 66
NOISE  0x00001b len   4  5e b1 0d 2b -> da ab 0b 5f
```

Exactly one signal, at 0x0b, up by 5 as predicted: `coins`, P3. The clock moved across two bytes this time, which is why it shows `NOISE?`.

Longer name:

```
$ python3 scripts/rosetta.py diff s04_one_more_fish.mhs s05_long_name.mhs
! sizes differ (37 vs 50): ...
CHANGE 0x000007 len   1  03 -> 10  le 3->16 (delta +13)
CHANGE 0x00000b len  39  ...
```

Byte 0x07 went from 3 to 16 and the file grew by 13: a one-byte length, then the name as UTF-8 (P3). That also moves coins: they sit right after the name, not at a fixed offset.

One more fish: the file grows by 6 bytes and a 16-bit number right after `saved_at` goes from 1 to 2. Each record is 6 bytes: species (u16), grams (u16), rod (u8), and one byte that is always 0.

## 6. Tie card

`name_len` could be a one-byte length or a varint: every name so far is under 128 bytes. The game caps names at 24 characters, so no sample can break the tie. Keep the one-byte reading, note the tie in FORMAT.md.

## 7. Seal

```
$ python3 scripts/rosetta.py seal samples/*.mhs --at -4 --width 4
FITS  crc32              over before-field               stored little-endian
```

Six differing samples, one recipe left: CRC-32 of every byte before the seal.

## 8. Spec and checks

`moss-harbor.spec.json` describes the layout. With the label sheet:

```
$ python3 scripts/rosetta.py check moss-harbor.spec.json samples/*.mhs --labels labels.csv
PASS samples/s01_base_a.mhs: 31 bytes, named 29 (94%), gaps 2, proof bytes P0:1 P1:7 P2:8 P3:11 P4:4
...
PASS samples/s06_new_rod.mhs: 56 bytes, named 52 (93%), gaps 4, proof bytes P0:1 P1:9 P2:16 P3:26 P4:4
6/6 samples pass
```

## 9. Steer on a copy

```
$ python3 scripts/rosetta.py set moss-harbor.spec.json samples/s01_base_a.mhs coins 999 --out edits/s01_coins999.mhs
refreshed seal seal
wrote edits/s01_coins999.mhs (31 bytes); spec check PASS
```

The user backs up the save folder, puts the copy in place with the game offline, and the game shows 999 coins. `coins` becomes P4.

## 10. Rosetta handed over

```
Verdict: READABLE (catch log), EDITABLE (coins)

0x00  4  magic       'MHSV'                      P1
0x04  2  version     3                           P1
0x06  1  unk_flags   always 0                    P0
0x07  1  name_len                                P3  (tie: u8 vs varint, unbreakable under the 24-char cap)
0x08  n  name        UTF-8                       P3
+0    4  coins       u32                         P4
+4    4  saved_at    u32 Unix seconds            P2
+8    2  catch_count u16                         P3
+10   6×count  catches: species u16, weight_g u16, rod u8, gap_pad u8
end-4 4  seal        CRC-32 of all bytes before it, little-endian   P3

Open: unk_flags (try a save with the tutorial skipped); species ids beyond 4.
Re-check after every game update.
```

CSV export of the catch log:

```bash
python3 scripts/rosetta.py dump moss-harbor.spec.json save.mhs --json \
  | python3 -c "import json,sys; t=json.load(sys.stdin); print('species,weight_g,rod'); [print(f\"{c['species']},{c['weight_g']},{c['rod']}\") for c in t['catches']]"
```
