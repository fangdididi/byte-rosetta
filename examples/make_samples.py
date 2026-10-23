#!/usr/bin/env python3
"""Build the fictional Moss Harbor save files used in the worked example and the tests.

Moss Harbor is an invented offline fishing game. Nothing here comes from a real product.
Run:  python3 examples/make_samples.py [outdir]
"""
import os, struct, sys, zlib

SPECIES = {"perch": 1, "eel": 2, "pike": 3, "carp": 4}


def save(name, coins, catches, saved_at, flags=0):
    body = bytearray(b"MHSV")
    body += struct.pack("<HBB", 3, flags, len(name.encode()))
    body += name.encode()
    body += struct.pack("<II", coins, saved_at)
    body += struct.pack("<H", len(catches))
    for sp, grams, rod in catches:
        body += struct.pack("<HHBB", SPECIES[sp], grams, rod, 0)
    body += struct.pack("<I", zlib.crc32(bytes(body)) & 0xFFFFFFFF)
    return bytes(body)


SAMPLES = {
    # baseline twins: same game state, saved twice a minute apart
    "s01_base_a.mhs": ("Ina", 120, [("perch", 340, 1)], 1792828800),
    "s02_base_b.mhs": ("Ina", 120, [("perch", 340, 1)], 1792828861),
    # one dial turned at a time
    "s03_coins_125.mhs": ("Ina", 125, [("perch", 340, 1)], 1792829100),
    "s04_one_more_fish.mhs": ("Ina", 125, [("perch", 340, 1), ("eel", 910, 1)], 1792829400),
    "s05_long_name.mhs": ("Ina of the Reeds", 125, [("perch", 340, 1), ("eel", 910, 1)], 1792829700),
    "s06_new_rod.mhs": ("Ina of the Reeds", 98, [("perch", 340, 1), ("eel", 910, 1), ("pike", 2210, 2)], 1792830000),
}


def main(out):
    os.makedirs(out, exist_ok=True)
    for fn, (name, coins, catches, ts) in SAMPLES.items():
        with open(os.path.join(out, fn), "wb") as f:
            f.write(save(name, coins, catches, ts))
    print(f"wrote {len(SAMPLES)} samples to {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "samples"))
