#!/usr/bin/env python3
"""rosetta.py - small, offline helper for the byte-rosetta skill.

Standard library only. It never modifies an input file; `set` always writes a new file.

Commands
  survey  FILE...                       region map, magic, entropy, shared prefix
  diff    A B [--twins X Y]             changed byte ranges (twins mark noise)
  find    FILE VALUE [--float]          where a known value could be stored
  seal    FILE... --at OFF --width N    which checksum recipe fits every sample
  check   SPEC FILE... [--labels CSV]   parse, coverage, consts, seals, mirror, labels
  dump    SPEC FILE [--json]            read a file through the spec (the reader)
  set     SPEC FILE PATH VALUE --out NEW   edit one field on a copy, refresh seals
"""
import argparse, bz2, csv, json, lzma, math, os, struct, sys, zlib

# ---------------------------------------------------------------- basics

MAGIC = [
    (b"PK\x03\x04", "zip container"), (b"\x1f\x8b", "gzip"), (b"BZh", "bzip2"),
    (b"\xfd7zXZ\x00", "xz"), (b"(\xb5/\xfd", "zstd"), (b"\x04\x22\x4d\x18", "lz4 frame"),
    (b"7z\xbc\xaf\x27\x1c", "7z"), (b"SQLite format 3\x00", "sqlite3"),
    (b"\x89PNG\r\n\x1a\n", "png"), (b"%PDF", "pdf"), (b"RIFF", "riff (wav/avi/webp)"),
    (b"OggS", "ogg"), (b"\x7fELF", "elf executable"), (b"MZ", "windows executable"),
    (b"bplist00", "binary plist"), (b"<?xml", "xml text"), (b"\xff\xd8\xff", "jpeg"),
    (b"GIF8", "gif"), (b"\xca\xfe\xba\xbe", "java class / mach-o fat"),
]
ZLIB_HEADS = (b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda")


def read(path):
    with open(path, "rb") as f:
        return f.read()


def entropy(chunk):
    if not chunk:
        return 0.0
    counts = [0] * 256
    for b in chunk:
        counts[b] += 1
    n = len(chunk)
    return -sum(c / n * math.log2(c / n) for c in counts if c)


def printable_ratio(chunk):
    if not chunk:
        return 0.0
    ok = sum(1 for b in chunk if 32 <= b < 127 or b in (9, 10, 13))
    return ok / len(chunk)


def classify(chunk):
    if len(set(chunk)) == 1:
        return "FLAT"
    if printable_ratio(chunk) >= 0.85:
        return "TEXT"
    e = entropy(chunk)
    ceiling = math.log2(min(len(chunk), 256))
    if ceiling >= 6 and e >= ceiling - 1.2:
        return "DENSE"
    if e < 3.5:
        return "SPARSE"
    return "MIXED"


def try_unpack(data, off):
    tail = data[off:]
    for name, fn in (("zlib", zlib.decompress), ("gzip", lambda b: zlib.decompress(b, 47)),
                     ("raw-deflate", lambda b: zlib.decompressobj(-15).decompress(b)),
                     ("bzip2", bz2.decompress), ("xz/lzma", lzma.decompress)):
        try:
            out = fn(tail)
            if out and len(out) >= 8:
                return name, len(out)
        except Exception:
            pass
    return None


def magic_of(data):
    for sig, name in MAGIC:
        if data.startswith(sig):
            return name
    if data[:2] in ZLIB_HEADS:
        return "zlib stream"
    s = data[:64].lstrip()
    if s[:1] in (b"{", b"[") and printable_ratio(data[:512]) > 0.95:
        return "json-like text"
    return None


def regions(data, window):
    out = []
    for off in range(0, len(data), window):
        kind = classify(data[off:off + window])
        if out and out[-1][2] == kind:
            out[-1][1] = off + len(data[off:off + window])
        else:
            out.append([off, off + len(data[off:off + window]), kind])
    return out

# ---------------------------------------------------------------- survey

def cmd_survey(args):
    blobs = [(p, read(p)) for p in args.files]
    for p, d in blobs:
        print(f"== {p}  {len(d)} bytes  entropy {entropy(d):.2f} bits/byte")
        m = magic_of(d)
        if m:
            print(f"   KNOWN SIGNATURE: {m} -> look for an existing reader before going further")
        for a, b, kind in regions(d, args.window):
            line = f"   0x{a:06x}-0x{b:06x}  {kind:6s} {b - a} bytes"
            if kind == "DENSE":
                hit = None
                lo = max(a - args.window, 0)
                starts = sorted({a, max(a - 2, 0)} | {i for i in range(lo, min(b, a + args.window))
                                                      if d[i:i + 2] in ZLIB_HEADS or d[i:i + 2] == b"\x1f\x8b"})
                for start in starts[:64]:
                    hit = try_unpack(d, start)
                    if hit:
                        line += f"  -> PACKED ({hit[0]} at 0x{start:x}, {hit[1]} bytes out)"
                        break
                if not hit:
                    line += "  -> SEALED? (no standard unpacker fits; may be encrypted: stop rule)"
            if kind == "TEXT":
                line += f"  '{d[a:min(b, a + 40)].decode('latin-1')!s}'"
            print(line)
    if len(blobs) > 1:
        datas = [d for _, d in blobs]
        n = 0
        while all(len(d) > n for d in datas) and len({d[n] for d in datas}) == 1:
            n += 1
        sizes = sorted({len(d) for d in datas})
        print(f"== shared prefix across {len(datas)} samples: {n} bytes; sizes: {sizes}")
        if len(sizes) == 1:
            print("   all samples same size: fixed layout likely")
        else:
            print("   sizes differ: look for counts, lengths or variable records")
    return 0

# ---------------------------------------------------------------- diff

def changed_ranges(a, b, merge=2):
    n = max(len(a), len(b))
    idx = [i for i in range(n) if (a[i] if i < len(a) else None) != (b[i] if i < len(b) else None)]
    out = []
    for i in idx:
        if out and i - out[-1][1] <= merge:
            out[-1][1] = i + 1
        else:
            out.append([i, i + 1])
    return out


def cmd_diff(args):
    a, b = read(args.a), read(args.b)
    noise = set()
    if args.twins:
        x, y = read(args.twins[0]), read(args.twins[1])
        for s, e in changed_ranges(x, y):
            noise.update(range(s, e))
    if len(a) != len(b):
        print(f"! sizes differ ({len(a)} vs {len(b)}): bytes after the first insertion shift; "
              "diff the region before it, then re-align")
    rngs = changed_ranges(a, b)
    if not rngs:
        print("identical")
        return 0
    for s, e in rngs:
        span = set(range(s, e))
        if not args.twins:
            tag = "CHANGE"
        elif span <= noise:
            tag = "NOISE "
        elif span & noise:
            tag = "NOISE?"   # overlaps bytes that also move between twins (e.g. a wider clock change)
        else:
            tag = "SIGNAL"
        before, after = a[s:e], b[s:e]
        hint = ""
        if e - s <= 4 and len(before) == len(after) == e - s:
            va, vb = int.from_bytes(before, "little"), int.from_bytes(after, "little")
            hint = f"  le {va}->{vb} (delta {vb - va:+d})"
        print(f"{tag} 0x{s:06x} len {e - s:3d}  {before.hex(' ')[:47]:47s} -> {after.hex(' ')[:47]}{hint}")
    return 0

# ---------------------------------------------------------------- find

def encodings(value, as_float):
    out = []
    if as_float:
        v = float(value)
        out += [("f32le", struct.pack("<f", v)), ("f32be", struct.pack(">f", v)),
                ("f64le", struct.pack("<d", v)), ("f64be", struct.pack(">d", v))]
        for k, scale in (("x10", 10), ("x100", 100), ("x1000", 1000)):
            iv = round(v * scale)
            if 0 <= iv < 2 ** 32:
                out += [(f"u32le{k}", struct.pack("<I", iv)), (f"u16le{k}", struct.pack("<H", iv & 0xFFFF)) if iv < 65536 else None]
        return [o for o in out if o]
    try:
        v = int(value, 0)
    except ValueError:
        return [("ascii", value.encode("ascii", "ignore")), ("utf-8", value.encode("utf-8")),
                ("utf-16le", value.encode("utf-16le")), ("utf-16be", value.encode("utf-16be"))]
    for fmt, name, lo, hi in (("B", "u8", 0, 255), ("b", "i8", -128, -1), ("H", "u16", 0, 65535),
                              ("h", "i16", -32768, -1), ("I", "u32", 0, 2**32 - 1),
                              ("i", "i32", -2**31, -1), ("Q", "u64", 2**32, 2**64 - 1)):
        if lo <= v <= hi:
            if fmt in "Bb":
                out.append((name, struct.pack(fmt, v)))
            else:
                out += [(name + "le", struct.pack("<" + fmt, v)), (name + "be", struct.pack(">" + fmt, v))]
    return out


def find_all(data, needle):
    hits, i = [], data.find(needle)
    while i != -1 and len(hits) < 50:
        hits.append(i)
        i = data.find(needle, i + 1)
    return hits


def cmd_find(args):
    data = read(args.file)
    total = 0
    for name, needle in encodings(args.value, args.float):
        if not needle:
            continue
        hits = find_all(data, needle)
        if hits:
            total += len(hits)
            shown = ", ".join(f"0x{h:x}" for h in hits[:12])
            print(f"{name:12s} {len(hits):3d} hit(s): {shown}")
    if not total:
        print("no hits: try --float, a scaled value, another sample, or the value may be derived/packed")
    elif args.value.lstrip("-").isdigit() and abs(int(args.value, 0)) < 256:
        print("note: small numbers hit everywhere; anchor with a second sample where the value differs")
    return 0

# ---------------------------------------------------------------- checksums

def _crc16(data, poly, init, refin, xorout):
    crc = init
    for b in data:
        if refin:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ poly if crc & 1 else crc >> 1
        else:
            crc ^= b << 8
            for _ in range(8):
                crc = ((crc << 1) ^ poly) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc ^ xorout


def _fletcher16(data):
    a = b = 0
    for x in data:
        a = (a + x) % 255
        b = (b + a) % 255
    return (b << 8) | a


def _fnv1a32(data):
    h = 0x811C9DC5
    for x in data:
        h = ((h ^ x) * 0x01000193) & 0xFFFFFFFF
    return h


def _xor8(data):
    v = 0
    for x in data:
        v ^= x
    return v


ALGOS = {
    "sum8": (1, lambda d: sum(d) & 0xFF),
    "xor8": (1, _xor8),
    "twos8": (1, lambda d: (-sum(d)) & 0xFF),
    "sum16": (2, lambda d: sum(d) & 0xFFFF),
    "crc16-ccitt-false": (2, lambda d: _crc16(d, 0x1021, 0xFFFF, False, 0)),
    "crc16-xmodem": (2, lambda d: _crc16(d, 0x1021, 0x0000, False, 0)),
    "crc16-arc": (2, lambda d: _crc16(d, 0xA001, 0x0000, True, 0)),
    "crc16-modbus": (2, lambda d: _crc16(d, 0xA001, 0xFFFF, True, 0)),
    "fletcher16": (2, _fletcher16),
    "sum32": (4, lambda d: sum(d) & 0xFFFFFFFF),
    "crc32": (4, lambda d: zlib.crc32(d) & 0xFFFFFFFF),
    "adler32": (4, lambda d: zlib.adler32(d) & 0xFFFFFFFF),
    "fnv1a32": (4, _fnv1a32),
}


def seal_value(algo, data):
    return ALGOS[algo][1](bytes(data))


def candidate_ranges(n, off, width):
    """Named byte ranges a checksum stored at off..off+width could cover."""
    cands = {}
    if off > 0:
        cands["before-field"] = (0, off)
    if off + width < n:
        cands["after-field"] = (off + width, n)
    cands["whole-file-field-zeroed"] = ("zeroed", 0)
    for s in (2, 4, 6, 8, 12, 16, 32):
        if s < off:
            cands[f"from-0x{s:x}-to-field"] = (s, off)
        if off + width < s < n and off < 64:
            cands[f"from-0x{s:x}-to-end"] = (s, n)
    return cands


def cmd_seal(args):
    blobs = [(p, read(p)) for p in args.files]
    if len(blobs) < 4:
        print(f"! only {len(blobs)} sample(s): matches below may be coincidence; four or more differing samples are needed before trusting one")
    width = args.width
    found = []
    algos = [a for a, (w, _) in ALGOS.items() if w == width]
    if not algos:
        print(f"no built-in recipe has width {width}; try 1, 2 or 4, or a parameter search tool")
        return 1
    first = blobs[0][1]
    off0 = args.at if args.at >= 0 else len(first) + args.at
    for name, rng in candidate_ranges(len(first), off0, width).items():
        for algo in algos:
            for endian in ("little", "big") if width > 1 else ("little",):
                ok = True
                for _, d in blobs:
                    off = args.at if args.at >= 0 else len(d) + args.at
                    if rng[0] == "zeroed":
                        body = d[:off] + bytes(width) + d[off + width:]
                    else:
                        a, b = rng
                        if name.endswith("to-end") or name == "after-field":
                            b = len(d)
                        if name == "before-field" or name.endswith("to-field"):
                            b = off
                        body = d[a:b]
                    stored = int.from_bytes(d[off:off + width], endian)
                    if seal_value(algo, body) != stored:
                        ok = False
                        break
                if ok:
                    found.append((algo, name, endian))
    if not found:
        print("no recipe fits all samples: try another width or offset, per-block checksums, "
              "a checksum over unpacked data, or a CRC parameter search")
        return 1
    for algo, name, endian in found:
        print(f"FITS  {algo:18s} over {name:26s} stored {endian}-endian")
    if len(found) > 1:
        print("! several recipes fit: add samples until one remains")
    return 0

# ---------------------------------------------------------------- spec engine

INT = {"u8": "B", "i8": "b", "u16": "H", "i16": "h", "u32": "I", "i32": "i",
       "u64": "Q", "i64": "q", "f32": "f", "f64": "d"}


class SpecError(Exception):
    pass


def _resolve(ref, scope):
    if isinstance(ref, int):
        return ref
    for sc in reversed(scope):
        if ref in sc:
            v = sc[ref]
            if not isinstance(v, int):
                raise SpecError(f"size/repeat reference '{ref}' is not an integer")
            return v
    raise SpecError(f"unknown reference '{ref}' (it must be read before it is used)")


class Reader:
    def __init__(self, spec, data):
        self.spec, self.data, self.pos = spec, data, 0
        self.spans = []      # (path, start, end, field)
        self.seals = []      # (path, start, field)
        self.problems = []

    def take(self, n, path):
        if self.pos + n > len(self.data):
            raise SpecError(f"{path}: needs {n} bytes at 0x{self.pos:x} but only {len(self.data) - self.pos} remain")
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def one(self, f, path, scope, endian):
        t = f["type"]
        e = "<" if f.get("endian", endian) == "le" else ">"
        start = self.pos
        if t in INT:
            size = struct.calcsize(INT[t])
            v = struct.unpack(e + INT[t], self.take(size, path))[0]
        elif t in ("bytes", "str"):
            size = len(self.data) - self.pos if f.get("size") == "rest" else _resolve(f["size"], scope)
            raw = self.take(size, path)
            if t == "bytes":
                v = raw.hex()
            else:
                enc = f.get("enc", "utf-8")
                try:
                    v = raw.decode(enc)
                except UnicodeDecodeError:
                    raise SpecError(f"{path}: bytes at 0x{start:x} are not valid {enc}")
                if v.encode(enc) != raw:
                    raise SpecError(f"{path}: {enc} text does not re-encode to the same bytes")
        elif t == "struct":
            v = self.block(f["fields"], path, scope, f.get("endian", endian))
        else:
            raise SpecError(f"{path}: unknown type '{t}'")
        if "const" in f:
            want = f["const"]
            got = v
            if t == "bytes" and isinstance(want, str):
                want = want.replace(" ", "").lower()
            if got != want:
                self.problems.append(f"CONST {path} at 0x{start:x}: expected {want!r}, found {got!r}")
        if "seal" in f:
            self.seals.append((path, start, f))
        if t != "struct":
            self.spans.append((path, start, self.pos, f))
        return v

    def block(self, fields, prefix, scope, endian):
        out = {}
        scope = scope + [out]
        for f in fields:
            path = f"{prefix}.{f['name']}" if prefix else f["name"]
            if "repeat" in f:
                n = _resolve(f["repeat"], scope)
                out[f["name"]] = [self.one(f, f"{path}[{i}]", scope, endian) for i in range(n)]
            else:
                out[f["name"]] = self.one(f, path, scope, endian)
        return out

    def run(self):
        tree = self.block(self.spec["fields"], "", [], self.spec.get("endian", "le"))
        return tree


def seal_range(seal, start, n, width):
    def at(x):
        if x == "here":
            return start
        if x == "after":
            return start + width
        if x == "end":
            return n
        return x if x >= 0 else n + x
    return at(seal.get("from", 0)), at(seal.get("to", "here"))


def check_seals(rd):
    bad = []
    for path, start, f in rd.seals:
        width = struct.calcsize(INT[f["type"]])
        a, b = seal_range(f["seal"], start, len(rd.data), width)
        algo = f["seal"]["algo"]
        if algo not in ALGOS:
            bad.append(f"SEAL {path}: unknown algo '{algo}'")
            continue
        e = "little" if f.get("endian", rd.spec.get("endian", "le")) == "le" else "big"
        want = seal_value(algo, rd.data[a:b])
        got = int.from_bytes(rd.data[start:start + width], e)
        if want != got:
            bad.append(f"SEAL {path}: stored 0x{got:x}, {algo}[0x{a:x}:0x{b:x}] = 0x{want:x}")
    return bad


class Writer:
    def __init__(self, spec):
        self.spec, self.buf = spec, bytearray()

    def one(self, f, v, endian):
        t = f["type"]
        e = "<" if f.get("endian", endian) == "le" else ">"
        if t in INT:
            self.buf += struct.pack(e + INT[t], v)
        elif t == "bytes":
            self.buf += bytes.fromhex(v)
        elif t == "str":
            self.buf += v.encode(f.get("enc", "utf-8"))
        elif t == "struct":
            self.block(f["fields"], v, f.get("endian", endian))

    def block(self, fields, obj, endian):
        for f in fields:
            v = obj[f["name"]]
            if "repeat" in f:
                for item in v:
                    self.one(f, item, endian)
            else:
                self.one(f, v, endian)

    def run(self, tree):
        self.block(self.spec["fields"], tree, self.spec.get("endian", "le"))
        return bytes(self.buf)


def is_gap(path):
    leaf = path.split(".")[-1].split("[")[0]
    return leaf.startswith(("gap_", "unk_", "maybe_"))


def analyse(spec, data):
    rd = Reader(spec, data)
    tree = rd.run()
    problems = list(rd.problems)
    if rd.pos != len(data):
        problems.append(f"COVERAGE {len(data) - rd.pos} byte(s) after 0x{rd.pos:x} are not described")
    problems += check_seals(rd)
    rebuilt = Writer(spec).run(tree)
    if rebuilt != data[:rd.pos]:
        i = next((k for k in range(min(len(rebuilt), rd.pos)) if rebuilt[k] != data[k]), min(len(rebuilt), rd.pos))
        problems.append(f"MIRROR rebuild differs from the original at 0x{i:x}")
    named = sum(e - s for p, s, e, f in rd.spans if not is_gap(p))
    gap = sum(e - s for p, s, e, f in rd.spans if is_gap(p))
    proof = {}
    for p, s, e, f in rd.spans:
        lvl = f.get("proof", "P0")
        proof[lvl] = proof.get(lvl, 0) + (e - s)
    return tree, rd, problems, named, gap, proof


def get_path(tree, path):
    cur = tree
    for part in path.replace("]", "").split("."):
        name, _, idx = part.partition("[")
        cur = cur[name]
        if idx:
            cur = cur[int(idx)]
    return cur


def load_spec(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_check(args):
    spec = load_spec(args.spec)
    labels = {}
    if args.labels:
        with open(args.labels, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                labels.setdefault(os.path.basename(row["file"]), []).append((row["field"], row["value"]))
    failed = 0
    for p in args.files:
        data = read(p)
        try:
            tree, rd, problems, named, gap, proof = analyse(spec, data)
        except SpecError as e:
            print(f"FAIL {p}: {e}")
            failed += 1
            continue
        for field, want in labels.get(os.path.basename(p), []):
            try:
                got = get_path(tree, field)
            except (KeyError, IndexError, ValueError):
                problems.append(f"LABEL {field}: no such field")
                continue
            if str(got) != want and not (isinstance(got, float) and abs(got - float(want)) < 1e-3):
                problems.append(f"LABEL {field}: app shows {want}, spec reads {got}")
        n = len(data)
        status = "PASS" if not problems else "FAIL"
        failed += bool(problems)
        lv = " ".join(f"{k}:{v}" for k, v in sorted(proof.items()))
        print(f"{status} {p}: {n} bytes, named {named} ({100 * named / max(n, 1):.0f}%), gaps {gap}, proof bytes {lv}")
        for pr in problems:
            print(f"     {pr}")
    print(f"{len(args.files) - failed}/{len(args.files)} samples pass")
    return 1 if failed else 0


def cmd_dump(args):
    spec = load_spec(args.spec)
    tree, rd, problems, *_ = analyse(spec, read(args.file))
    if args.json:
        print(json.dumps(tree, ensure_ascii=False, indent=1))
    else:
        for path, s, e, f in rd.spans:
            v = get_path(tree, path)
            mark = f.get("proof", "P0")
            print(f"0x{s:06x} {e - s:5d}  {mark}  {path} = {v!r}")
    for pr in problems:
        print(f"! {pr}", file=sys.stderr)
    return 1 if problems else 0


def _find_field(fields, path):
    parts = path.replace("]", "").split(".")
    fl, f = fields, None
    for part in parts:
        name = part.split("[")[0]
        f = next((x for x in fl if x["name"] == name), None)
        if f is None:
            raise SpecError(f"no field '{name}' in spec")
        fl = f.get("fields", [])
    return f


def _parent(tree, path):
    head, _, leaf = path.rpartition(".")
    return (get_path(tree, head) if head else tree), leaf


def cmd_set(args):
    if os.path.abspath(args.out) == os.path.abspath(args.file):
        print("refusing to overwrite the input: write to a new file and test it on a copy")
        return 2
    spec = load_spec(args.spec)
    data = read(args.file)
    tree, rd, problems, *_ = analyse(spec, data)
    if problems:
        print("spec does not pass on this file; fix the spec first:")
        for pr in problems:
            print("  " + pr)
        return 1
    f = _find_field(spec["fields"], args.path)
    t = f["type"]
    if "repeat" in f and "[" not in args.path.split(".")[-1]:
        print("give an index for repeated fields, e.g. items[0].qty")
        return 2
    if t in INT:
        value = float(args.value) if t.startswith("f") else int(args.value, 0)
    elif t == "str":
        value = args.value
    elif t == "bytes":
        value = args.value.replace(" ", "").lower()
    else:
        print("only number, text or bytes fields can be set")
        return 2
    parent, leaf = _parent(tree, args.path)
    name, _, idx = leaf.replace("]", "").partition("[")
    if idx:
        parent[name][int(idx)] = value
    else:
        parent[name] = value
    if t in ("str", "bytes") and isinstance(f.get("size"), str) and f["size"] != "rest":
        new_len = len(value.encode(f.get("enc", "utf-8"))) if t == "str" else len(value) // 2
        if f["size"] in parent:
            parent[f["size"]] = new_len
            print(f"also updated length field '{f['size']}' to {new_len}")
        else:
            print("! the length field lives in another scope; update it with a second `set`")
    try:
        out = bytearray(Writer(spec).run(tree))
    except struct.error as e:
        print(f"value does not fit the field type: {e}")
        return 2
    rd2 = Reader(spec, bytes(out))
    rd2.run()
    for path, start, sf in rd2.seals:
        width = struct.calcsize(INT[sf["type"]])
        a, b = seal_range(sf["seal"], start, len(out), width)
        e = "little" if sf.get("endian", spec.get("endian", "le")) == "le" else "big"
        out[start:start + width] = seal_value(sf["seal"]["algo"], out[a:b]).to_bytes(width, e)
        print(f"refreshed seal {path}")
    with open(args.out, "wb") as fh:
        fh.write(out)
    _, _, problems2, *_ = analyse(spec, bytes(out))
    print(f"wrote {args.out} ({len(out)} bytes); spec check {'PASS' if not problems2 else 'FAIL'}")
    print("next: load the copy in the real app and confirm it shows the new value (proof P4)")
    return 0 if not problems2 else 1

# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(prog="rosetta.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("survey"); s.add_argument("files", nargs="+"); s.add_argument("--window", type=int, default=256)
    s.set_defaults(fn=cmd_survey)
    s = sub.add_parser("diff"); s.add_argument("a"); s.add_argument("b"); s.add_argument("--twins", nargs=2)
    s.set_defaults(fn=cmd_diff)
    s = sub.add_parser("find"); s.add_argument("file"); s.add_argument("value"); s.add_argument("--float", action="store_true")
    s.set_defaults(fn=cmd_find)
    s = sub.add_parser("seal"); s.add_argument("files", nargs="+"); s.add_argument("--at", type=int, required=True)
    s.add_argument("--width", type=int, required=True); s.set_defaults(fn=cmd_seal)
    s = sub.add_parser("check"); s.add_argument("spec"); s.add_argument("files", nargs="+"); s.add_argument("--labels")
    s.set_defaults(fn=cmd_check)
    s = sub.add_parser("dump"); s.add_argument("spec"); s.add_argument("file"); s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_dump)
    s = sub.add_parser("set"); s.add_argument("spec"); s.add_argument("file"); s.add_argument("path"); s.add_argument("value")
    s.add_argument("--out", required=True); s.set_defaults(fn=cmd_set)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except SpecError as e:
        print(f"spec error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
