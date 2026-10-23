# Field patterns: what common shapes look like in bytes

Use this as a list of hypotheses to test, not as answers. Every pattern here has a kill test.

## Lengths and counts

- **Length then data**: a small number, then exactly that many bytes. Kill test: change the text length; the number must change by the same amount.
- **Count then records**: a small number, then that many equal-size records. The file grows by one record size per extra item.
- **Total size**: a 32-bit number equal to the file size, or the file size minus the header. Check it in every sample.
- **Width**: lengths are usually 1, 2 or 4 bytes. A one-byte length and a varint look the same until a length passes 127; make a stretcher sample to tell them apart.

## Offsets and tables

- A number that, read as a position, points at the start of a recognisable structure (a string, a magic, a record) in every sample.
- Offset tables are often a list of increasing numbers. Differences between neighbours are the sizes of the things they point to.
- Offsets may be absolute, relative to the table, or relative to the field itself.

## Chunks (tag, length, value)

- A short ASCII or numeric tag, a length, then the payload, repeated until the end. PNG and RIFF work this way; many custom formats copy the idea.
- Unknown tags can be skipped using the length. That is why they are popular, and why a reader can stay useful across versions.

## Varints

- A byte with the top bit set means "more bytes follow". Values under 128 take one byte.
- Zigzag varints map small negative numbers to small positive codes (-1 to 1, 1 to 2, -2 to 3).

## Numbers that are not plain integers

- **Fixed point**: the app shows 12.5, the file stores 125 or 1250. Search for the value times 10, 100 and 1000.
- **Floats**: 32-bit floats for 1.0 look like `00 00 80 3f` in little-endian. Values near round numbers have many zero bytes at the low end.
- **Signed**: a number that becomes huge when you expect it to go below zero is signed. Make a sample with a negative value.
- **Bit flags**: a byte whose single bits switch when you toggle individual settings. Diff one toggle at a time and note which bit moved.
- **Enums**: small integers with only a few distinct values across samples. Map them to app labels one by one.

## Time

- **Unix seconds**: a 32-bit number around 1.7 to 1.9 billion for dates in 2024 to 2030.
- **Unix milliseconds**: a 64-bit number about 1000 times larger.
- **Windows FILETIME**: 64-bit count of 100-nanosecond steps since 1601; for 2024 to 2030 the top two bytes are `01 da` to `01 e0` (stored last in little-endian).
- **DOS date and time**: two 16-bit numbers packing year-1980, month, day and hours, minutes, seconds/2.
- **Counters**: numbers that rise by one per save are not time; they still count as noise between twins.

## Text

- **Length-prefixed**: see above.
- **NUL-terminated**: text followed by `00`; the next field starts right after.
- **Fixed slot**: text padded with zeros or spaces to a fixed width; the file size does not change when the name gets longer, until it is cut off.
- **UTF-16**: every other byte is `00` for Latin text. Search with `find` and a word the app shows.

## Padding and alignment

- Zero bytes that make the next field start at a multiple of 2, 4, 8 or 16. They appear and disappear as earlier variable parts grow.
- "Padding" that is not all zeros may be leftover memory. Treat it as a gap and avoid copying it into outputs that leave the device; it can contain stray private data.

## Seals

- Changes chaotically on any edit, including between twins: CRC or hash.
- Changes by the same amount as an edited byte: plain sum.
- Usually in the header or the last 2 to 8 bytes. Footers usually cover everything before them.
- CRC-32 stored little-endian over everything before the field is the most common recipe; test it first.

## Compression and protection

- High entropy that one of the standard unpackers opens: compression. Unpack, then repeat the whole process on the unpacked bytes.
- High entropy that nothing opens: likely encryption. Stop. Keyed hashes and signatures can also guard files; if a seal never fits any recipe and the app refuses edited copies, editing is SEALED even if reading works.
