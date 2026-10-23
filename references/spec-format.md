# spec.json: the small format language

`rosetta.py` reads one JSON file that describes the format from the first byte to the last. Fields are read in order; there are no jumps. That keeps the language small and makes coverage and mirror checks exact. Formats with offset tables or random-access chunks can still be described in order when the chunks are stored in order; otherwise describe the part you need and mark the rest as a `rest` gap.

## Top level

```json
{
  "name": "moss-harbor-save",
  "endian": "le",
  "fields": [ ... ]
}
```

`endian` is `le` (little-endian) or `be` (big-endian). Any field or record can override it with its own `"endian"`.

## Field keys

| key | required | meaning |
|---|---|---|
| `name` | yes | Field name. Start with `unk_`, `gap_` or `maybe_` for bytes whose meaning is not known; they are counted as gaps. |
| `type` | yes | `u8 u16 u32 u64 i8 i16 i32 i64 f32 f64`, `bytes`, `str`, or `struct`. |
| `size` | for `bytes`/`str` | A number, the name of an earlier integer field (a length), or `"rest"` (everything left). |
| `enc` | for `str` | `utf-8` (default), `utf-16le`, `utf-16be`, `latin-1`, `ascii`, or any Python codec name. |
| `fields` | for `struct` | A list of fields: a record. |
| `repeat` | no | A number or the name of an earlier integer field (a count). The value becomes a list. |
| `const` | no | Expected value. Integer for numbers, text for `str`, hex for `bytes` (spaces allowed). A mismatch is a CONST error. |
| `seal` | no | On an integer field: `{"algo": "crc32", "from": 0, "to": "here"}`. See below. |
| `proof` | no | `P0`..`P4`; used for the byte tally. Default `P0`. |
| `note` | no | Free text; ignored by the tool, useful in FORMAT.md. |

Length and count references are looked up in the current record first, then in enclosing records. They must be read before they are used.

## Seals

`from` and `to` accept:

- a byte offset (negative counts from the end of the file),
- `"here"`: the first byte of the seal field itself,
- `"after"`: the byte after the seal field,
- `"end"`: the end of the file.

Algorithms: `sum8`, `xor8`, `twos8`, `sum16`, `fletcher16`, `crc16-ccitt-false`, `crc16-xmodem`, `crc16-arc`, `crc16-modbus`, `sum32`, `crc32`, `adler32`, `fnv1a32`. The stored value is read with the field's endianness.

Seals that cover themselves zeroed, nested seals, and seals over unpacked data are not modelled. Describe them in FORMAT.md and check them by hand.

## The four checks

`rosetta.py check SPEC FILE... [--labels CSV]` prints one line per sample:

```
PASS s06_new_rod.mhs: 56 bytes, named 52 (93%), gaps 4, proof bytes P0:1 P1:9 P2:16 P3:26 P4:4
```

followed by any problems:

- `COVERAGE n byte(s) after 0x.. are not described`: the spec ends early. Add fields or a `rest` gap.
- `CONST path at 0x..`: a "constant" is not constant.
- `SEAL path: stored .. , algo[a:b] = ..`: wrong recipe or range.
- `MIRROR rebuild differs ... at 0x..`: a value does not survive read-then-write (text encoding, float, a field read with the wrong type).
- `LABEL field: app shows X, spec reads Y`: the label sheet disagrees with the spec.
- `FAIL file: path: needs n bytes at 0x..`: the spec runs past the end of the file, usually a length or count read from the wrong place.

## Labels CSV

```csv
file,field,value
s01_base_a.mhs,coins,120
s06_new_rod.mhs,catches[2].weight_g,2210
```

`file` is matched by base name. `field` uses dots for records and `[i]` for list items.

## Limits

No conditional fields, no switch on a tag, no bit fields, no varints, no jumps to offsets. When a format needs them, keep `spec.json` for the fixed parts, document the rest in FORMAT.md, and write a dedicated reader (Kaitai Struct is a good next step) that you test against the same samples and labels.
