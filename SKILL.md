---
name: byte-rosetta
description: Decode an undocumented data file you own (game save, device or app export, proprietary project or settings file, logger dump, captured message) into a tested format spec and a small reader. Uses copies only, baseline twins to expose noise, one-change-at-a-time samples, field cards with a five-step proof ladder, checksum recipe search, and a spec that must cover every byte and rebuild every sample byte-for-byte. Use when someone says "what is inside this .dat/.bin/.sav", "where does the game store my gold", "convert this export to CSV", "write a parser for this file", or "can I safely edit this setting". Not for encryption, DRM, licence checks, anti-cheat, online games, or other people's private data.
---

# Byte Rosetta

## What this skill is

A file with no documentation is a page in a language nobody wrote a dictionary for. Byte Rosetta builds that dictionary the slow, honest way: by producing pairs of files that differ in one known way, watching which bytes move, and refusing to call anything a field until the evidence says so.

The end product is a **rosetta**: a short written spec of the format, a machine-readable `spec.json`, and a reader that turns the file into plain values. Every field in it carries a proof level, and the spec must pass four checks on every sample you own before anyone relies on it:

1. **Coverage**: every byte of every sample is described (unknown bytes are allowed, but they must be named as gaps).
2. **Constants**: values the spec says never change really never change.
3. **Seals**: every checksum the spec declares recomputes to the stored value.
4. **Mirror**: reading a sample and writing it back produces the exact same bytes.

## The problem it solves

When people point an agent at a mystery file, the usual result is a confident layout table built from one sample and pattern-matching. It looks right, reads one file, and quietly misreads the next one: a "length" that was really an ID, a "level" that was a timestamp, a field that moves when a name gets longer. Editing a file on that basis breaks saves and corrupts exports. Byte Rosetta replaces "looks like" with "was steered", keeps a running tally of what is proven versus guessed, and always works on copies.

## When to use

- Reading values out of a file an app writes but will not export (game saves, fitness or sensor exports, old project files, settings blobs, instrument logs).
- Converting a proprietary export to CSV or JSON so you can keep your own data.
- Finding where one value lives (gold, a setting, a counter) and changing it safely on a copy.
- Writing an interoperable reader for a legacy format you are migrating away from.
- Documenting a format that is "known" but has unexplained reserved or padding bytes.

## When not to use

- The file is a known format (zip, SQLite, gzip, protobuf, msgpack, plist, JSON with a binary wrapper). Use the existing library; the verdict is **NOT NEW**.
- The data looks encrypted, or the goal is to bypass DRM, a licence or activation check, anti-cheat, paywalls, or the rules of an online or competitive game. The verdict is **STOPPED**. Compression is fine; protection is not.
- The files belong to someone else, or hold other people's private data you have no right to read.
- You only have one sample and cannot make more. You can survey, but stay at P0 and say so.

## Hard lines

- Work on copies. Never write to the original file or the app's live save folder. `rosetta.py set` refuses to overwrite its input.
- If a region stays high-entropy after every standard unpacker, treat it as sealed. Do not guess keys, brute-force passwords, or patch the app to skip checks.
- Private values (health, money, messages) stay local. Show only what the user asked for.
- Respect the user's rights and local law. Reading your own data and building interoperable tools is the goal; redistributing someone's protected content is not.

## The proof ladder

Every field card gets one level. Report the level, not your confidence.

| Level | Name | What it takes |
|---|---|---|
| P0 | GUESS | It looks like something (a run of zeros, a plausible number). |
| P1 | STEADY | Its reading is consistent across every sample (a constant, a count that matches the records that follow). |
| P2 | MATCHED | It equals a value the app shows, in at least three samples where that value differs. |
| P3 | STEERED | You changed one thing in the app, predicted in writing which bytes would change and how, and they did. |
| P4 | WRITTEN | You changed the bytes on a copy, the app loaded it, and showed the value you predicted. |

A field at P0 or P1 can be named `unk_*` or `gap_*`. Only P3 and P4 fields should be edited by tools.

## Verdicts

- **NOT NEW**: a known format or an existing reader was found. Hand over the reader and stop.
- **READABLE**: the spec passes all four checks; the fields the user cares about are P2 or higher.
- **EDITABLE**: READABLE, plus the fields to be edited are P4 and every seal recipe is known.
- **PARTIAL**: the spec passes, but some fields the user needs are still below P2. List them.
- **SEALED**: the interesting part is encrypted or signed with an unknown key. Stop and say so.
- **STOPPED**: a hard line was reached (ownership, protection, private data).

## Steps

Keep everything in a `rosetta/` folder next to the copies: `CASE.md`, `SHELF.md`, `FIELDS.md`, `spec.json`, `FORMAT.md`.

### 1. Write the case card

Before touching bytes, write five lines in `CASE.md`:

- **File**: name, extension, which app and version writes it, which device or OS.
- **Ownership**: whose data it is and why the user may read it.
- **Question**: what the user actually wants (read three values, export everything, edit one setting).
- **Done means**: the verdict that would satisfy them (usually READABLE or EDITABLE for named fields).
- **Stop lines**: what would end the job (encryption, online play, someone else's data).

A narrow question saves hours. "Where is my coin count" needs one field; "a full parser" needs all of them.

### 2. Check whether it is new

Run `python3 scripts/rosetta.py survey FILE`. It reports known signatures, a region map (FLAT, TEXT, SPARSE, MIXED, DENSE), and tries standard unpackers on dense regions. Then:

- A known signature or container: open it with the normal tool (unzip, sqlite3, a plist reader). Often the "mystery" file is a zip of JSON.
- Search the web and code hosts for the extension plus the app name plus words like "format", "parser", "save editor", "spec". Format galleries (Kaitai format gallery, ImHex patterns, 010 Editor templates, file-format wikis) are worth one look.
- If a working reader exists, the verdict is NOT NEW. Verify it on the user's samples and stop.

### 3. Build the specimen shelf

Copy the originals to a working folder. Log each sample in `SHELF.md` with a short hash, size, and how it was made. Then make more samples on purpose:

- **Baseline twins**: save the same state twice, a minute apart, with nothing changed. Every byte that differs between twins is **noise** (clocks, save counters, random salts, seals that cover them). You need this before any other diff makes sense.
- **Dial turns**: change exactly one thing in the app, save, and log it. Before diffing, write down your prediction: "coins 120 to 125, expect one small number to rise by 5." Predictions written after the diff do not count toward P3.
- **Stretchers**: a much longer name, an empty list, a list with one more item, a negative or very large value. These reveal lengths, counts and signedness.
- **Labels**: a small CSV of values the app shows for each sample (`file,field,value`). The checker uses it.

Aim for at least six samples. Seals need four or more that differ.

### 4. Read the map

From the survey:

- **TEXT** regions: read them; names, keys and paths often sit next to the fields they describe.
- **FLAT** runs: padding, reserved space, or an empty table.
- **SPARSE / MIXED**: structured binary, where most fields live.
- **DENSE** with `PACKED (...)`: compressed data. Unpack it to a new file and repeat the process on that file.
- **DENSE** with `SEALED?`: no standard unpacker fits. Try a few more container ideas (raw deflate at another offset, a zstd or lz4 block), then stop that region. Do not try to decrypt it.

When sizes differ between samples, something variable is inside: look for counts and lengths. When sizes are identical, the layout is probably fixed.

### 5. Diff and anchor

- `rosetta.py diff A B --twins T1 T2` lists changed ranges: `NOISE` if every byte also moves between the twins, `NOISE?` if it overlaps them (a clock that rolled over a wider span), `SIGNAL` if it never moves on its own. Without twins every range is just `CHANGE`.
- `rosetta.py find FILE VALUE` searches for a known value in common encodings: 8/16/32/64-bit integers in both byte orders, floats, scaled fixed-point (x10, x100, x1000), ASCII, UTF-8 and UTF-16. Use `--float` for decimals.
- A value that turns up once in a sample, and moves to the predicted new value in the next sample, is your anchor. Small numbers (under 256) hit everywhere; only anchor them with a second sample.
- If an insertion shifts everything after it, the inserted bytes tell you where the variable part is, and a byte before it that grew by the same amount is the length or count.

### 6. Write field cards

For each field, add a row to `FIELDS.md`:

| offset | width | type | endian | name | meaning | proof | kill test |
|---|---|---|---|---|---|---|---|

The **kill test** is the observation that would prove you wrong, for example "if the count is not 3 in the sample with three items." Run it.

When two readings fit the same bytes (a one-byte length versus a varint when every length is under 128; a NUL-terminated string versus a length-prefixed one; signed versus unsigned when every value is small), write a **tie card**: both readings, and the sample that would break the tie (a 200-character name, a negative balance). Make that sample if the user can. Otherwise keep the more general reading and mark it P1.

Common shapes are listed in `references/field-patterns.md`: lengths, counts, offsets, tag-length-value chunks, varints, timestamps, fixed-point numbers, bit flags, alignment padding and string styles.

### 7. Find the seals

A field of 1, 2, 4 or 8 bytes that changes chaotically whenever anything changes (including between twins) is usually a checksum or hash. Usually it sits in the header or the last few bytes. Run:

```bash
python3 scripts/rosetta.py seal samples/*.bin --at -4 --width 4
```

It tries common recipes (byte sum and two's-complement sum, XOR, Fletcher-16, four CRC-16 variants, CRC-32, Adler-32, FNV-1a, 32-bit sum) over likely ranges, in both byte orders, and reports recipes that fit **every** sample. Rules:

- A match from fewer than four differing samples can be a coincidence. Add samples until exactly one recipe remains.
- If nothing fits: try the checksum over unpacked data, per-block checksums, a different width, or a CRC parameter search tool. If it is a keyed hash or a signature, the verdict for editing is SEALED (reading may still be fine).

### 8. Write the spec and run the four checks

Write `spec.json` in the small language described in `references/spec-format.md` (numbers, bytes, text, nested records, repeats, length references, constants, seals, proof levels). Then:

```bash
python3 scripts/rosetta.py check rosetta/spec.json samples/* --labels rosetta/labels.csv
```

Fix the **first** error and run it again. Typical fixes: a wrong width shifts everything after it (COVERAGE or a nonsense value later on); a CONST failure means the field is not constant after all; a MIRROR failure means a text encoding or float does not round-trip; a SEAL failure means the range is wrong. Do not delete a failing sample to make the check pass.

### 9. Prove the steering (only if editing is wanted)

```bash
python3 scripts/rosetta.py set rosetta/spec.json samples/s03.bin coins 999 --out edits/s03_coins999.bin
```

`set` writes a new file, updates the matching length field for text, recomputes the seals and re-checks the result. Then the **user** loads that copy in the app (backed up, offline). If the app shows the predicted value, the field becomes P4. If the app rejects the file, there is a seal or a second copy of the value you have not found yet: go back to step 7.

### 10. Hand over the rosetta

Write `FORMAT.md` with:

- The verdict and one sentence on what can be read or edited safely.
- The layout table with proof levels, and a byte tally (named bytes, gap bytes, bytes by proof level, from the `check` output).
- Seal recipes.
- How to read a file: `python3 scripts/rosetta.py dump rosetta/spec.json FILE` (or `--json`).
- Open questions and the samples that would settle them.
- Which app versions the samples came from. A new app version can change the format; rerun `check` on a new sample after every update.

## Example

**User**: "My offline fishing game Moss Harbor keeps saves as `.mhs`. I want my catch log as a CSV and I'd like to know where the coins are."

1. **Case card**: own saves, offline single-player, done = READABLE for the catch log, EDITABLE for coins.
2. **Survey**: no known signature, 31 to 56 bytes, no dense regions, sizes differ, shared prefix of 7 bytes (`MHSV`, then 3, then 0, ...).
3. **Shelf**: two twins, then coins 120 to 125, one more fish, a longer name, a new rod.
4. **Diff** of the twins: one byte at 0x0f and the last four bytes change, so they are noise. Read as a 32-bit number, 0x0f to 0x12 equals the Unix time of each save (P2).
5. **Diff** of 120 to 125 coins: apart from the noise, one byte at 0x0b rises by exactly 5, as predicted (P3).
6. **Longer name**: everything after 0x08 shifts by 13 and the byte at 0x07 goes from 3 to 16: a one-byte length followed by UTF-8 text (P3).
7. **One more fish**: file grows by 6 bytes and a 16-bit number goes from 1 to 2: a catch count followed by 6-byte records (species, grams, rod, one zero byte).
8. **Seal**: `seal --at -4 --width 4` over six samples gives one recipe: CRC-32 of everything before the field, stored little-endian.
9. **Check**: 6/6 samples pass, 92 to 94% of bytes named, gaps are one flag byte and the record padding.
10. **Steer**: `set ... coins 999` on a copy; the game loads it and shows 999 coins, so coins become P4. Verdict: READABLE for the catch log, EDITABLE for coins. The CSV comes from `dump --json`.

The whole worked case, with commands and output, is in `examples/worked-example.md`; the files can be rebuilt with `examples/make_samples.py`.

## Tips

- Make the twins first. Nothing else makes sense until you know which bytes move on their own.
- Change one thing per sample, and write the prediction down before you look.
- A field's name is a claim. If you are not sure, call it `unk_*` and keep going; full coverage matters more than full meaning.
- Sizes that differ by the length of a string, or by a record size times a count, are free evidence.
- Little-endian is the common default on PCs and phones, but count both. Network protocols and older consoles often use big-endian.
- Timestamps give themselves away: they change between twins and fall in a plausible date range when read as Unix seconds, milliseconds, or Windows FILETIME.
- When you hit an app update, save one new sample and run `check` before trusting the old spec.
- Without a shell the helper is not available, but the method still works with any hex viewer: the twins, dial turns, proof ladder and four checks are what matter.
