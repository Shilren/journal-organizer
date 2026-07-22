<!-- 语言: 中文 | [English](README.en.md) -->
## 核心价值与产品理念见 [个人使用案例和产品价值观.md](docs/PHILOSOPHY.md)，飞书配置细节见 [feishu-bot/README.md](feishu-bot/README.md) 和 [knowledge-bot/README.md](knowledge-bot/README.md)更完整的项目总结见 [docs/PROJECT.md](docs/PROJECT.md)，
# Journal Organizer

> 把飞书里的随手想法沉淀成一个会持续生长、能够理解你的个人知识系统。

Journal Organizer 是一套本地优先的个人 AI 系统：一个 Bot 负责忠实记录，一个 Second Me 负责理解、内化和继续思考。所有长期记忆都保存在你自己的 Markdown / Obsidian 仓库里，Codex 只在需要时整理或检索材料。

它最初只是一个“口述想法自动归档”Skill，后来逐步补上了消息补抓、周复盘、Obsidian 看板、知识检索、长期自我模型和短期对话记忆，最终形成一套完整的个人知识 Agent。它想解决的已经不只是“如何记住更多”，而是“如何让长期积累的自我重新参与今天的判断”。

## 它不是第二大脑，而是两种自我能力

很多第二大脑产品把人理解成一个等待搜索的资料库：保存越多，链接越多，系统似乎就越聪明。但真正重要的个人知识，往往不是某条事实，而是一个人如何经历、如何解释、如何改变判断。

这个项目因此把个人 AI 拆成两种不同能力：

- **Journal Bot 是见证者**：它保护当时的我。它整理语言，却不抢走叙事权；保留迟疑、转折和原始顺序，让未来仍能看见认知是怎样发生的。
- **Second Me 是同行者**：它让过去的我重新进入现在。它不机械引用笔记，而是把长期经历、价值判断和当前上下文组成一个可以继续推断的视角。

前者回答“我当时究竟是怎么想的”，后者回答“带着这些经历，现在的我会怎么看”。一个保护记忆的真实性，一个延续人格的连续性。

Second Me 也不是静态数字克隆。人的价值观会演进，某次情绪不等于永久信念，一篇 AI 周复盘也不等于本人原话。系统保留不同材料的来源和时间，让人格可以变化，同时不被某一个瞬间随意重写。

## 价值理念

### 1. 叙事权属于用户

AI 可以修复表达，不能替用户决定“这段经历真正意味着什么”。记录 Bot 的第一责任是忠实，不是显得聪明。

### 2. 用户不是数据集

个人知识库保存的不只是可检索文本，也保存偏好、情绪、矛盾、认知变化和仍未完成的问题。Second Me 的目标不是给用户贴标签，而是在具体问题里保持对这个人的连续理解。

### 3. 内化比引用更接近真实交流

亲近的人不会在每句话后面列出“参考了你去年哪次谈话”。Second Me 默认把材料内化成回答方式，不展示检索过程；同时保留可追溯性，在用户需要核对时能够回到原始记录。

### 4. 支持主体性，而不是接管主体性

Second Me 可以更懂上下文、更有判断力，却不替用户垄断解释权和决定权。它的价值是扩大思考空间，让用户更清楚地成为自己，而不是制造新的外部权威。

### 5. 人格可以生长

长期自我模型描述稳定原则，原始记录保留现实变化，短期上下文负责此刻。三者共同工作，让 Agent 既有连续性，也不会把过去固化成牢笼。

## 产品理念

- **先降低记录摩擦，再追求知识结构**：最珍贵的想法往往只出现几十秒，先接住它，再谈整理。
- **原始材料优先于 AI 结论**：清洗正文保留原文；一手记录高于周复盘；具体事实发生冲突时回到源头。
- **模型负责语义，代码负责确定性**：理解、分类和表达交给模型；写入、日期、撤回、去重和权限交给程序。
- **写入与理解分离**：Journal Bot 能写但克制，Second Me 能推断但只读。职责边界比一段越来越长的 Prompt 更可靠。
- **本地拥有，模型可替换**：Vault、人格模型和历史留在用户设备；飞书只是入口，Codex 是当前推理引擎，都不是数据的最终归属。
- **默认自然，必要时可审计**：日常对话不做引用表演，底层仍保留原文、文件层级、材料类型和检索日志。

## 核心能力

| 模块 | 作用 |
|---|---|
| 记录 Bot | 接收飞书文字或富文本，保留原始思路整理、分类并写入 Obsidian |
| 消息补抓 | Mac 睡眠或网络断开后，从飞书历史补抓，按 `message_id` 去重 |
| 周复盘 | 每周日自动汇总一手记录，生成一篇第一人称成长复盘 |
| Second Me / Knowledge Bot | 只读检索知识库，结合长期自我模型和最近几轮对话回答 |
| 材料分层 | 原始记录是一手材料；AI 周复盘是二级材料，只在趋势问题中加权 |
| 分类优先检索 | 根据问题匹配分类、关键词、时间和标题，先找最可能相关的内容 |
| Obsidian 看板 | 自动统计周/月记录量、分类分布和时间趋势 |

## 为什么是两个 Bot

写入和回答是两种不同职责：

- 记录 Bot 必须忠实、克制、确定性强，不能把用户的话改成 AI 的观点。
- Second Me 需要检索、联想和推断，但必须保持只读，不能在回答时意外改写知识库。

两个飞书应用使用不同 `lark-cli profile`，因此可以同时运行，不会争抢同一条事件流。

```mermaid
flowchart LR
    U["用户 / 飞书"] --> W["记录 Bot"]
    W --> O["整理、分类、去重"]
    O --> V[("Markdown / Obsidian Vault")]
    V --> D["Dataview 看板"]
    V --> R["检索与材料分层"]
    S["长期自我模型"] --> A["Second Me"]
    H["短期对话上下文"] --> A
    R --> A
    A --> U
    V --> Q["每周复盘"]
    Q --> V
    Q --> U
```

## 知识检索逻辑

Second Me 不是把整个仓库塞给模型。它先在本地完成轻量检索：

1. 按 Markdown 二级标题拆成独立知识片段。
2. 用问题里的中英文词、中文二元/三元词组进行匹配。
3. 根据配置里的分类说明和关键词，提高相关分类权重。
4. 对近期材料增加少量权重。
5. 默认降低“周复盘”权重，因为它是 AI 生成的二级材料。
6. 当问题涉及变化、成长或时间线时，再提高周复盘权重。
7. 把筛出的材料、长期自我模型和最近对话交给 Codex 生成回答。

默认回复不会机械列出来源。材料的作用是帮助 Agent 形成上下文，而不是把聊天写成检索报告。需要审计时，日志仍会记录检索数量和来源类型。

## 快速开始

### 1. 准备依赖

- macOS（后台服务使用 `launchd`）
- Python 3
- Node.js
- [`lark-cli`](https://github.com/larksuite/lark-cli)：`npm install -g @larksuite/cli`
- Codex CLI（Codex 桌面版已内置，或自行安装）
- Obsidian 可选；知识库本质上只是 Markdown 文件夹

### 2. 创建两个飞书应用

在飞书开放平台创建两个自建应用，分别启用机器人：

- Journal / Capture：记录和周复盘
- Second Me / Knowledge：知识库问答

两个应用都需要：

1. 选择“使用长连接接收事件”。
2. 订阅 `im.message.receive_v1`。
3. 开启接收私聊和发送消息相关权限。
4. 创建版本并发布。
5. 分别保存为两个 `lark-cli profile`。

### 3. 配置知识库

```bash
mkdir -p ~/.config/journal-organizer
cp config.example.json ~/.config/journal-organizer/config.json
```

编辑 `config.json`，至少设置：

- `vault`：Markdown 知识库的绝对路径
- `categories`：记录 Bot 可选择的分类及描述
- `knowledge.category_keywords`：问题到分类的额外路由词，可选

### 4. 安装两个 Bot

```bash
JOURNAL_LARK_PROFILE=cli_writer \
KNOWLEDGE_LARK_PROFILE=cli_reader \
bash install-all.sh
```

也可以单独安装：

```bash
LARK_PROFILE=cli_writer bash feishu-bot/install.sh
LARK_PROFILE=cli_reader bash knowledge-bot/install.sh
```

安装后编辑私有长期模型：

```text
~/.knowledge-bot/self_model.md
```

模板会引导你写身份、当前目标、价值观、决策原则和偏好的说话方式。这个文件已被 `.gitignore` 排除，不会进入仓库。

## 日常使用

记录 Bot：

- 直接发一段想法：整理并归档
- `撤回`：删除最近一条归档
- `周复盘`：立即生成本周复盘
- `帮助`：查看命令

Second Me：

- 直接提问：基于知识库回答
- `重建索引`：生成本地 JSONL 索引，用作 Vault 暂时不可读时的回退
- `帮助`：查看说明

服务管理：

```bash
~/.journal-bot/ctl.sh status
~/.journal-bot/ctl.sh restart
~/.knowledge-bot/ctl.sh status
~/.knowledge-bot/ctl.sh restart
```

## 数据格式

同一分类、同一天的记录会追加到同一个文件：

```markdown
# 2026-07-22 · 信念与原则

## 21:10 · 重新理解主场

整理后的正文，保持原始思考顺序和第一人称口吻。

> [!note]- 原始记录
> 用户发送的原文会折叠保留。

---
```

## 可靠性设计

- 成功写入后才把消息标记为已处理。
- 实时消费与历史补抓共享 `message_id` 去重状态。
- 补抓只看最近数天，避免状态丢失后回灌全部历史。
- 归档时额外写入 append-only 周复盘索引，减少 macOS 对 Obsidian 目录权限波动造成的定时任务失败。
- 两个 Agent 各自使用独立飞书应用和独立 launchd 服务。
- Second Me 对 Vault 只读，Codex 运行在 `read-only` sandbox。

## 隐私边界

仓库只包含通用代码和示例，不包含：

- 飞书 App ID / Secret 或登录凭证
- 私人知识库正文
- 真实长期自我模型
- 聊天历史、消息 ID、索引和运行日志

这些数据只保存在本机的 `~/.journal-bot/`、`~/.knowledge-bot/` 和你的 Vault 中。请在公开 Fork 前再次运行敏感信息扫描。

## 项目结构

```text
journal-organizer/
├── SKILL.md                         # 记录整理 Skill
├── config.example.json              # Vault、分类、检索配置
├── install-all.sh                   # 双 Bot 安装入口
├── scripts/file_note.py             # 确定性 Markdown 归档
├── feishu-bot/                      # 写入 Bot + 周复盘
├── knowledge-bot/                   # 只读知识问答 Bot
├── dashboards/                      # Obsidian Dataview 看板
├── examples/vault/                  # 匿名示例知识库
├── tests/                            # 语法与核心检索测试
└── docs/PROJECT.md                  # 项目演进、设计决策与路线图
```

更完整的项目总结见 [docs/PROJECT.md](docs/PROJECT.md)，价值与产品理念见 [docs/PHILOSOPHY.md](docs/PHILOSOPHY.md)，飞书配置细节见 [feishu-bot/README.md](feishu-bot/README.md) 和 [knowledge-bot/README.md](knowledge-bot/README.md)。

## License

[MIT](LICENSE)
