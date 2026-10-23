# spec.json：小型格式描述语言

`rosetta.py` 读取一个 JSON 文件，它从第一个字节到最后一个字节描述整个格式。字段按顺序读取，没有跳转。这让语言保持精简，也让覆盖检查和镜像检查可以做到精确。带偏移表或随机访问块的格式，只要块是按顺序存放的，仍可按顺序描述；否则描述你需要的部分，其余用 `rest` 空隙标出。

## 顶层

```json
{
  "name": "moss-harbor-save",
  "endian": "le",
  "fields": [ ... ]
}
```

`endian` 为 `le`（小端）或 `be`（大端）。任何字段或记录都可以用自己的 `"endian"` 覆盖。

## 字段键

| 键 | 必需 | 含义 |
|---|---|---|
| `name` | 是 | 字段名。含义未知的字节以 `unk_`、`gap_` 或 `maybe_` 开头，会计入空隙。 |
| `type` | 是 | `u8 u16 u32 u64 i8 i16 i32 i64 f32 f64`、`bytes`、`str` 或 `struct`。 |
| `size` | `bytes`/`str` 必需 | 数字、之前某个整数字段的名字（长度），或 `"rest"`（剩下的全部）。 |
| `enc` | `str` 用 | `utf-8`（默认）、`utf-16le`、`utf-16be`、`latin-1`、`ascii` 或任何 Python 编码名。 |
| `fields` | `struct` 必需 | 字段列表，即一条记录。 |
| `repeat` | 否 | 数字或之前某个整数字段的名字（计数）。值会变成列表。 |
| `const` | 否 | 期望值。数字类型写整数，`str` 写文本，`bytes` 写十六进制（可含空格）。不符即 CONST 错误。 |
| `seal` | 否 | 用于整数字段：`{"algo": "crc32", "from": 0, "to": "here"}`，见下文。 |
| `proof` | 否 | `P0`..`P4`，用于字节统计。默认 `P0`。 |
| `note` | 否 | 自由文本；工具忽略，写 FORMAT.md 时有用。 |

长度和计数引用先在当前记录中查找，再到外层记录查找。必须先读到，才能引用。

## 封印

`from` 和 `to` 可取：

- 字节偏移（负数表示从文件末尾倒数），
- `"here"`：封印字段自身的第一个字节，
- `"after"`：封印字段之后的那个字节，
- `"end"`：文件末尾。

算法：`sum8`、`xor8`、`twos8`、`sum16`、`fletcher16`、`crc16-ccitt-false`、`crc16-xmodem`、`crc16-arc`、`crc16-modbus`、`sum32`、`crc32`、`adler32`、`fnv1a32`。存储值按该字段的字节序读取。

把自身置零后再计算的封印、嵌套封印、对解压后数据计算的封印，目前不建模。请在 FORMAT.md 中写明并手工检查。

## 四项检查

`rosetta.py check SPEC 文件... [--labels CSV]` 每个样本输出一行：

```
PASS s06_new_rod.mhs: 56 bytes, named 52 (93%), gaps 4, proof bytes P0:1 P1:9 P2:16 P3:26 P4:4
```

后面跟着发现的问题：

- `COVERAGE n byte(s) after 0x.. are not described`：说明提前结束了。补字段或加一个 `rest` 空隙。
- `CONST path at 0x..`："常量"并不恒定。
- `SEAL path: stored .. , algo[a:b] = ..`：配方或范围不对。
- `MIRROR rebuild differs ... at 0x..`：某个值读出再写回后变了（文本编码、浮点数、类型读错）。
- `LABEL field: app shows X, spec reads Y`：标签表与说明不一致。
- `FAIL file: path: needs n bytes at 0x..`：说明读超出了文件末尾，通常是长度或计数读错了位置。

## 标签 CSV

```csv
file,field,value
s01_base_a.mhs,coins,120
s06_new_rod.mhs,catches[2].weight_g,2210
```

`file` 按文件名（不含路径）匹配。`field` 用点号表示记录层级，用 `[i]` 表示列表项。

## 局限

不支持条件字段、按标签分支、位字段、变长整数、跳转到偏移。格式需要这些时，`spec.json` 只描述固定部分，其余写进 FORMAT.md，另写一个专门的读取器（Kaitai Struct 是不错的下一步），并用同一批样本和标签测试它。
