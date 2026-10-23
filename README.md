**English** | [简体中文](README.zh-CN.md)

# Byte Rosetta

**Turn a mystery data file you own into a tested format spec and a working reader. An agent skill that decodes undocumented files by experiment, not by guesswork: twin saves to expose noise, one change per sample, a five-step proof ladder for every field, checksum recipe search, and a spec that must cover every byte and rebuild every sample exactly.**

Your game keeps saves in a `.sav` nobody documented. Your bike computer exports a `.dat` no other app reads. An old program left you a folder of project files you want to move to something else. Asking an AI "what is in this file" usually gets a confident table drawn from one sample. It reads that sample, then misreads the next one, and editing anything on that basis breaks the file.

Byte Rosetta makes the agent work like a careful lab partner:

- **Case card first.** What the file is, whose it is, the exact question, what "done" means, and the lines that end the job.
- **Is it new?** Known signatures, containers and compression are checked first, and existing readers are searched for. Often the answer is "it is a zip of JSON" and you are done.
- **Baseline twins.** The same state saved twice. Whatever differs is noise (clocks, counters, salts, seals) and is labelled so it cannot fool you later.
- **Dial turns.** One change per sample, with the prediction written down before looking at the diff.
- **Five-step proof ladder.** GUESS, STEADY, MATCHED, STEERED, WRITTEN. Every field carries its level; only steered fields get edited.
- **Tie cards.** When two readings fit the same bytes, both are written down with the sample that would break the tie.
- **Seal search.** Finds which common checksum recipe fits every sample, and warns when there are too few samples to trust a match.
- **Four checks.** Coverage of every byte, constants, seals, and a byte-for-byte mirror rebuild, on every sample, plus labels from the app.
- **Safe edits.** Edits go to a new file with seals refreshed; the user confirms in the app before a field counts as WRITTEN.
- **Clear verdicts.** NOT NEW, READABLE, EDITABLE, PARTIAL, SEALED, or STOPPED.

## Features

| | |
|---|---|
| Works for | game saves, fitness/sensor/instrument exports, settings blobs, legacy project files, logger dumps, captured messages, "reserved" bytes in known formats |
| Probes | region map with entropy and unpack attempts, twin-aware diff, value finder (ints both endians, floats, fixed-point, ASCII/UTF-8/UTF-16), checksum recipe search |
| Checksums | sum8, xor8, twos8, sum16, Fletcher-16, CRC-16 (CCITT-FALSE, XMODEM, ARC, MODBUS), sum32, CRC-32, Adler-32, FNV-1a |
| Spec | small JSON language: integers, floats, bytes, text, records, repeats, length/count references, constants, seals, proof levels |
| Reader | `dump` prints every field with offset and proof level, or JSON for CSV export |
| Editor | `set` writes a copy, updates text lengths, refreshes seals, re-checks, refuses to overwrite the input |
| Safety | copies only, stops at encryption, DRM, licence checks, anti-cheat, online games and other people's data |
| Helper | `scripts/rosetta.py`, Python standard library only, 19 tests |
| Bilingual | full English and Chinese skill files, references and worked example |

## Installation

The skill is the folder containing `SKILL.md` (English) and `SKILL.zh-CN.md` (Chinese). Copy the whole folder so `scripts/`, `references/` and `examples/` come with it.

**Claude Code**

```bash
git clone https://github.com/fangdididi/byte-rosetta.git ~/.claude/skills/byte-rosetta
```

**Codex / agents that read `~/.agents/skills`**

```bash
git clone https://github.com/fangdididi/byte-rosetta.git ~/.agents/skills/byte-rosetta
```

**Cursor** (project skills folder)

```bash
git clone https://github.com/fangdididi/byte-rosetta.git .cursor/skills/byte-rosetta
```

**Any other agent** (Gemini CLI, GitHub Copilot, OpenCode, Windsurf, Cline, Kimi, chat apps): paste `SKILL.md` into its instructions or project rules, or ask it to install the skill from this repository URL. For Chinese conversations use `SKILL.zh-CN.md`. Without a shell you lose the helper, but the method (twins, dial turns, proof ladder, four checks) works with any hex viewer.

Requirements: Python 3.8 or newer for the helper. No packages to install.

## Usage

Ask in plain words and point at the files:

```
What's inside these .sav files from my offline game? Use byte-rosetta.
My weather station exports .wsx files. I want them as CSV.
Where does this app store the "auto-backup" setting in settings.bin? I'd like to switch it off on a copy.
Write a reader for these old .prj files before I uninstall the program.
用 byte-rosetta 看看这个记账软件的 .dat 文件里存了什么，我想导出成表格。
```

The agent will:

1. Write the case card and check ownership and stop lines.
2. Survey the files and look for a known format or an existing reader.
3. Ask you for twin saves and one-change-at-a-time samples, with predictions written first.
4. Diff, anchor values, and write field cards with proof levels and kill tests.
5. Find the checksum recipe, if there is one.
6. Write `spec.json` and run the four checks on every sample until they pass.
7. If you want edits: change a copy, and ask you to confirm it in the app.
8. Hand over `FORMAT.md`, the reader command and a verdict.

Helper commands:

```bash
python3 scripts/rosetta.py survey samples/*                       # region map, signatures, shared prefix
python3 scripts/rosetta.py diff A B --twins T1 T2                 # SIGNAL / NOISE / NOISE? ranges
python3 scripts/rosetta.py find FILE 125                          # where could 125 be stored
python3 scripts/rosetta.py find FILE 12.5 --float                 # floats and fixed-point
python3 scripts/rosetta.py seal samples/* --at -4 --width 4       # checksum recipe search
python3 scripts/rosetta.py check spec.json samples/* --labels labels.csv   # the four checks
python3 scripts/rosetta.py dump spec.json FILE [--json]           # read a file through the spec
python3 scripts/rosetta.py set spec.json FILE coins 999 --out copy.bin     # edit a copy, refresh seals
python3 -m unittest discover -s tests                             # run the tests
```

`check` exits with 0 when every sample passes and 1 otherwise.

## Example

`examples/` holds a full case on an invented offline fishing game, Moss Harbor (rebuild the files with `python3 examples/make_samples.py`):

- Twins show one clock byte and the last four bytes moving on their own.
- Selling a fish moves exactly one byte, 120 to 125: coins, steered.
- A longer name shifts the rest of the file by 13 and turns a 3 into a 16: a one-byte length before UTF-8 text.
- One more fish adds a 6-byte record and bumps a count.
- `seal` over six samples leaves one recipe: CRC-32 of everything before the last four bytes.
- `check` passes 6/6 with 92 to 94% of bytes named; `set coins 999` on a copy loads in the game.

Verdict: READABLE for the catch log (exported to CSV with `dump --json`), EDITABLE for coins.

## File structure

```
byte-rosetta/
├── SKILL.md                       # skill instructions (English)
├── SKILL.zh-CN.md                 # skill instructions (Chinese)
├── README.md
├── README.zh-CN.md
├── LICENSE
├── scripts/
│   └── rosetta.py                 # survey, diff, find, seal, check, dump, set
├── references/
│   ├── spec-format.md             # the spec.json language and check messages
│   ├── spec-format.zh-CN.md
│   ├── field-patterns.md          # lengths, counts, chunks, time, text, seals...
│   └── field-patterns.zh-CN.md
├── examples/
│   ├── make_samples.py            # builds the Moss Harbor sample saves
│   ├── samples/                   # six .mhs files
│   ├── moss-harbor.spec.json
│   ├── labels.csv
│   ├── worked-example.md
│   └── worked-example.zh-CN.md
└── tests/
    └── test_rosetta.py
```

## Limits

The spec language reads fields in order: no jumps, conditional fields, bit fields or varints. Formats that need them get a partial spec plus notes, and a dedicated reader tested against the same samples. A checksum recipe that fits is evidence, not proof of the producer's algorithm. Meaning is only as good as the samples: fields that never changed in your samples stay guesses. The skill does not decrypt, crack, or bypass any protection, and is not for online or competitive games.

## License

[MIT](LICENSE) © fangdididi
