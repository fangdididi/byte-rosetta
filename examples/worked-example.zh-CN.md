# 完整示例：Moss Harbor 存档

Moss Harbor 是一款虚构的离线钓鱼游戏；它的 `.mhs` 存档由 `make_samples.py` 生成，你可以复现每一步。下面的数字都是工具在这些文件上的真实输出。

## 1. 案件卡

```
文件：      Moss Harbor 1.4（离线单机）的 *.mhs，Windows
归属：      我自己电脑上的我自己的存档
问题：      把渔获记录导出成 CSV；找到金币存在哪
完成标准：  渔获记录 READABLE，金币 EDITABLE
停止线：    加密、任何联网内容、其他玩家的数据
```

## 2. 是新格式吗？

```
$ python3 scripts/rosetta.py survey samples/*.mhs
== samples/s01_base_a.mhs  31 bytes  entropy 3.86 bits/byte
   0x000000-0x00001f  MIXED  31 bytes
...
== shared prefix across 6 samples: 7 bytes; sizes: [31, 37, 50, 56]
   sizes differ: look for counts, lengths or variable records
```

没有已知签名，没有高密度区，大小各不相同。用扩展名加游戏名搜索，没有找到任何资料。这是新格式。

## 3. 样本架

| 样本 | 制作方式 | 事先写下的预测 |
|---|---|---|
| s01_base_a | 基线存档 | - |
| s02_base_b | 一分钟后什么都不改再存一次 | 只有时钟和封印会变 |
| s03_coins_125 | 卖掉一条鲈鱼：金币 120→125 | 某个数字增加 5 |
| s04_one_more_fish | 钓到一条鳗鱼（910 克） | 文件多一条记录，某个计数 1→2 |
| s05_long_name | 把 "Ina" 改名为 "Ina of the Reeds" | 某个长度 3→16，后面字节后移 13 |
| s06_new_rod | 买新鱼竿（金币 125→98），用它钓到一条狗鱼 | 计数为 3，出现鱼竿编号 2 |

## 4. 先看双胞胎

```
$ python3 scripts/rosetta.py diff s01_base_a.mhs s02_base_b.mhs
CHANGE 0x00000f len   1  80 -> bd  le 128->189 (delta +61)
CHANGE 0x00001b len   4  b4 86 8b a1 -> 5e b1 0d 2b
```

晚 61 秒的存档里，有一个字节恰好增加了 61。把 0x0f–0x12 按 32 位小端读：

```
$ python3 scripts/rosetta.py find s01_base_a.mhs 1792828800
u32le          1 hit(s): 0xf
```

这是 Unix 秒表示的保存时间，在六个样本里都与时钟吻合：`saved_at`，P2。最后四个字节乱变：封印候选。

## 5. 拨盘

```
$ python3 scripts/rosetta.py diff s02_base_b.mhs s03_coins_125.mhs --twins s01_base_a.mhs s02_base_b.mhs
SIGNAL 0x00000b len   1  78 -> 7d  le 120->125 (delta +5)
NOISE? 0x00000f len   2  bd 65 -> ac 66
NOISE  0x00001b len   4  5e b1 0d 2b -> da ab 0b 5f
```

只有一个信号，在 0x0b，如预测般增加 5：`coins`，P3。这次时钟变化跨了两个字节，所以显示为 `NOISE?`。

更长的名字：

```
$ python3 scripts/rosetta.py diff s04_one_more_fish.mhs s05_long_name.mhs
! sizes differ (37 vs 50): ...
CHANGE 0x000007 len   1  03 -> 10  le 3->16 (delta +13)
CHANGE 0x00000b len  39  ...
```

0x07 从 3 变 16，文件增长 13：一个单字节长度，后接 UTF-8 名字（P3）。这也意味着金币紧跟在名字后面，并不在固定偏移。

多一条鱼：文件增长 6 字节，`saved_at` 之后的一个 16 位数从 1 变 2。每条记录 6 字节：品种（u16）、克数（u16）、鱼竿（u8）、一个恒为 0 的字节。

## 6. 平局卡

`name_len` 可能是单字节长度，也可能是变长整数：目前所有名字都短于 128 字节。游戏把名字限制在 24 个字符，没有样本能打破平局。保留单字节读法，并在 FORMAT.md 中注明。

## 7. 封印

```
$ python3 scripts/rosetta.py seal samples/*.mhs --at -4 --width 4
FITS  crc32              over before-field               stored little-endian
```

六个不同样本，只剩一个配方：对封印之前所有字节计算 CRC-32。

## 8. 说明与检查

`moss-harbor.spec.json` 描述了布局。带上标签表：

```
$ python3 scripts/rosetta.py check moss-harbor.spec.json samples/*.mhs --labels labels.csv
PASS samples/s01_base_a.mhs: 31 bytes, named 29 (94%), gaps 2, proof bytes P0:1 P1:7 P2:8 P3:11 P4:4
...
PASS samples/s06_new_rod.mhs: 56 bytes, named 52 (93%), gaps 4, proof bytes P0:1 P1:9 P2:16 P3:26 P4:4
6/6 samples pass
```

## 9. 在副本上操控

```
$ python3 scripts/rosetta.py set moss-harbor.spec.json samples/s01_base_a.mhs coins 999 --out edits/s01_coins999.mhs
refreshed seal seal
wrote edits/s01_coins999.mhs (31 bytes); spec check PASS
```

用户先备份存档目录，在离线状态下放入副本，游戏显示 999 金币。`coins` 升为 P4。

## 10. 交付罗塞塔

```
结论：READABLE（渔获记录），EDITABLE（金币）

0x00  4  magic       'MHSV'                      P1
0x04  2  version     3                           P1
0x06  1  unk_flags   恒为 0                      P0
0x07  1  name_len                                P3（平局：u8 或变长整数，24 字符上限下无法打破）
0x08  n  name        UTF-8                       P3
+0    4  coins       u32                         P4
+4    4  saved_at    u32 Unix 秒                 P2
+8    2  catch_count u16                         P3
+10   6×count  catches：species u16, weight_g u16, rod u8, gap_pad u8
末尾-4 4 seal        之前所有字节的 CRC-32，小端  P3

待解：unk_flags（试试跳过新手教程的存档）；4 以上的品种编号。
每次游戏更新后重新检查。
```

导出渔获 CSV：

```bash
python3 scripts/rosetta.py dump moss-harbor.spec.json save.mhs --json \
  | python3 -c "import json,sys; t=json.load(sys.stdin); print('species,weight_g,rod'); [print(f\"{c['species']},{c['weight_g']},{c['rod']}\") for c in t['catches']]"
```
