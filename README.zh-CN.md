[English](README.md) | **简体中文**

# Byte Rosetta（字节罗塞塔）

**把你自己拥有的"神秘数据文件"变成一份经过测试的格式说明和一个能用的读取器。这个智能体技能靠实验而不是猜测来解读没有文档的文件：用双胞胎存档暴露噪声，每个样本只改一处，每个字段走五级证据阶梯，搜索校验和配方，最终的格式说明必须覆盖每一个字节，并能把每个样本逐字节原样重建。**

你的游戏把存档放在一个没人写过文档的 `.sav` 里；你的码表导出的 `.dat` 别的软件都打不开；一个旧程序留下一堆工程文件，你想把它们迁走。直接问 AI"这个文件里是什么"，通常会得到一张只基于一个样本、信心满满的表。它能读那一个样本，换一个就读错，照着它去改文件，文件就坏了。

Byte Rosetta 让智能体像一位细心的实验搭档那样工作：

- **先写案件卡。** 文件是什么、属于谁、具体问题是什么、怎样算完成、什么情况必须停手。
- **先查是不是新格式。** 先检查已知签名、容器和压缩，并搜索现成的读取器。很多时候答案是"这就是装着 JSON 的 zip"，直接结束。
- **基线双胞胎。** 同一状态保存两次。不同的地方都是噪声（时钟、计数器、盐值、校验），先标出来，免得之后被它骗。
- **拨盘样本。** 每个样本只改一处，看对比结果之前先写下预测。
- **五级证据阶梯。** 猜测、稳定、对上、操控、写入。每个字段都带着自己的等级；只有被操控验证过的字段才会被修改。
- **平局卡。** 两种读法都能解释同一批字节时，把两种都写下来，并写明能打破平局的样本。
- **封印搜索。** 找出对每个样本都成立的常见校验和配方；样本太少不足以信任时会提醒。
- **四项检查。** 在每个样本上检查字节全覆盖、常量、封印、逐字节镜像重建，并核对应用里显示的标签值。
- **安全修改。** 修改写入新文件并刷新封印；用户在应用里确认后，字段才算"写入"级。
- **明确结论。** NOT NEW、READABLE、EDITABLE、PARTIAL、SEALED 或 STOPPED。

## 功能

| | |
|---|---|
| 适用对象 | 游戏存档、运动/传感器/仪器导出、设置文件、老旧工程文件、记录仪转储、抓到的报文、已知格式里的"保留"字节 |
| 探测 | 带熵值和解压尝试的区域图、识别双胞胎噪声的对比、数值查找（大小端整数、浮点、定点数、ASCII/UTF-8/UTF-16）、校验和配方搜索 |
| 校验和 | sum8、xor8、twos8、sum16、Fletcher-16、CRC-16（CCITT-FALSE、XMODEM、ARC、MODBUS）、sum32、CRC-32、Adler-32、FNV-1a |
| 格式说明 | 精简 JSON 语言：整数、浮点、字节、文本、记录、重复、长度/计数引用、常量、封印、证据等级 |
| 读取器 | `dump` 逐字段输出偏移和证据等级，或输出 JSON 方便导出 CSV |
| 编辑器 | `set` 写出副本、更新文本长度、刷新封印、重新检查，拒绝覆盖输入文件 |
| 安全 | 只用副本；遇到加密、DRM、授权校验、反作弊、联网游戏和他人数据即停 |
| 辅助脚本 | `scripts/rosetta.py`，只用 Python 标准库，19 个测试 |
| 双语 | 完整的中英文技能文件、参考资料和完整示例 |

## 安装

技能就是包含 `SKILL.md`（英文）和 `SKILL.zh-CN.md`（中文）的整个文件夹。请完整复制，让 `scripts/`、`references/`、`examples/` 一起带上。

**Claude Code**

```bash
git clone https://github.com/fangdididi/byte-rosetta.git ~/.claude/skills/byte-rosetta
```

**Codex / 读取 `~/.agents/skills` 的智能体**

```bash
git clone https://github.com/fangdididi/byte-rosetta.git ~/.agents/skills/byte-rosetta
```

**Cursor**（项目技能目录）

```bash
git clone https://github.com/fangdididi/byte-rosetta.git .cursor/skills/byte-rosetta
```

**其他智能体**（Gemini CLI、GitHub Copilot、OpenCode、Windsurf、Cline、Kimi、各类聊天应用）：把 `SKILL.md` 粘贴进它的指令或项目规则，或让它从本仓库地址安装。中文对话请使用 `SKILL.zh-CN.md`。没有命令行时无法使用辅助脚本，但方法本身（双胞胎、拨盘、证据阶梯、四项检查）配合任何十六进制查看器都能用。

环境要求：辅助脚本需要 Python 3.8 及以上，无需安装任何第三方包。

## 使用

用平常的话提问，并指明文件：

```
用 byte-rosetta 看看这个记账软件的 .dat 文件里存了什么，我想导出成表格。
我离线游戏的 .sav 存档里都有什么？金币存在哪？
我的气象站导出 .wsx 文件，想转成 CSV。
settings.bin 里哪个字节控制"自动备份"？我想在副本上把它关掉。
卸载这个老软件之前，帮我给这些 .prj 文件写个读取器。
```

智能体会：

1. 写案件卡，确认归属和停止线。
2. 概览文件，寻找已知格式或现成读取器。
3. 请你提供双胞胎存档和"每次只改一处"的样本，并先写下预测。
4. 做对比、锚定数值，写带证据等级和证伪测试的字段卡。
5. 如果有校验和，找出它的配方。
6. 写 `spec.json`，在每个样本上跑四项检查直到全部通过。
7. 如果你要修改：改一个副本，请你在应用里确认。
8. 交付 `FORMAT.md`、读取命令和结论。

辅助命令：

```bash
python3 scripts/rosetta.py survey samples/*                       # 区域图、签名、共同前缀
python3 scripts/rosetta.py diff A B --twins T1 T2                 # SIGNAL / NOISE / NOISE? 区段
python3 scripts/rosetta.py find FILE 125                          # 125 可能存在哪里
python3 scripts/rosetta.py find FILE 12.5 --float                 # 浮点与定点数
python3 scripts/rosetta.py seal samples/* --at -4 --width 4       # 校验和配方搜索
python3 scripts/rosetta.py check spec.json samples/* --labels labels.csv   # 四项检查
python3 scripts/rosetta.py dump spec.json FILE [--json]           # 按说明读取文件
python3 scripts/rosetta.py set spec.json FILE coins 999 --out copy.bin     # 改副本并刷新封印
python3 -m unittest discover -s tests                             # 运行测试
```

所有样本通过时 `check` 返回 0，否则返回 1。

## 示例

`examples/` 中是一个完整案例，对象是虚构的离线钓鱼游戏 Moss Harbor（用 `python3 examples/make_samples.py` 可重新生成文件）：

- 双胞胎显示一个时钟字节和最后四个字节会自己变化。
- 卖掉一条鱼，正好一个字节从 120 变 125：金币，已操控验证。
- 名字变长后，文件其余部分后移 13 字节，一个 3 变成 16：UTF-8 文本前的单字节长度。
- 多钓一条鱼，多出一条 6 字节记录，计数加一。
- 对六个样本运行 `seal`，只剩一个配方：对最后四个字节之前的全部内容计算 CRC-32。
- `check` 6/6 通过，92% 到 94% 的字节已命名；在副本上 `set coins 999` 后游戏能正常加载。

结论：渔获记录 READABLE（用 `dump --json` 导出 CSV），金币 EDITABLE。

## 文件结构

```
byte-rosetta/
├── SKILL.md                       # 技能说明（英文）
├── SKILL.zh-CN.md                 # 技能说明（中文）
├── README.md
├── README.zh-CN.md
├── LICENSE
├── scripts/
│   └── rosetta.py                 # survey、diff、find、seal、check、dump、set
├── references/
│   ├── spec-format.md             # spec.json 语言与检查信息说明
│   ├── spec-format.zh-CN.md
│   ├── field-patterns.md          # 长度、计数、块、时间、文本、封印……
│   └── field-patterns.zh-CN.md
├── examples/
│   ├── make_samples.py            # 生成 Moss Harbor 样本存档
│   ├── samples/                   # 六个 .mhs 文件
│   ├── moss-harbor.spec.json
│   ├── labels.csv
│   ├── worked-example.md
│   └── worked-example.zh-CN.md
└── tests/
    └── test_rosetta.py
```

## 局限

格式说明语言按顺序读取字段：不支持跳转、条件字段、位字段和变长整数。需要这些的格式只能得到部分说明加注释，并另写一个用同一批样本测试的专用读取器。配方匹配是证据，不能证明生产方真的用了那个算法。含义的可靠程度取决于样本：在你的样本里从未变过的字段，始终只是猜测。本技能不解密、不破解、不绕过任何保护，也不用于联网或竞技游戏。

## 许可证

[MIT](LICENSE) © fangdididi
