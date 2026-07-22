<!-- 语言: 中文 | [English](README.en.md) -->

# Journal Organizer

> 用一个 Bot 保存当下的我，用一个 Second Me 带着长期的我继续思考。

Journal Organizer 是一套本地优先的个人认知系统。你在飞书里随手发送想法，Journal Bot 会忠实整理并归档到 Markdown / Obsidian；当你需要回顾、分析或继续推演时，Second Me 会结合长期知识库、价值观模型和最近对话回答。

所有长期记忆都保存在用户自己的 Vault 中。飞书是低摩擦入口，Codex 是当前推理引擎，它们都不是个人数据的最终归属。

## 30 秒看懂

| 角色 | 它做什么 | 它不做什么 |
|---|---|---|
| **Journal Bot** | 接住口语化想法，保留原始顺序整理、分类、归档和周复盘 | 不评价、不说教、不替用户重新解释经历 |
| **Second Me** | 检索长期材料，内化价值观，结合最近上下文继续分析和创作 | 不修改 Vault、不机械复述笔记、不假装拥有不存在的经历 |

它们组成一条持续循环：

```text
现实经历 -> Journal Bot 保存一手思考 -> 周复盘发现变化
        -> Second Me 调用长期经验 -> 产生新判断 -> 再次进入记录
```

Journal Bot 保护“我当时究竟是怎么想的”，Second Me 回答“带着这些经历，现在的我会怎么看”。一个保证记忆真实，一个让过去积累的自我重新参与今天。

## 推荐阅读

第一次了解项目，建议按下面顺序阅读：

1. **[我的使用方式：两个 Bot 如何成为一套个人认知系统](docs/PERSONAL-CASE-STUDY.md)**
   最推荐先读。包含作者的真实使用流程、八个知识分类、周复盘方法、向 Second Me 提问的方式，以及两个 Bot 各自承载的价值观。

2. **[价值理念与产品理念](docs/PHILOSOPHY.md)**
   解释为什么要保护用户叙事权、为什么内化比引用更重要、人格如何保持连续又允许变化。

3. **[项目演进与工程设计](docs/PROJECT.md)**
   从最初的口述归档 Skill，到消息补抓、周复盘、知识检索和双 Agent 分工的完整演进过程。

4. **安装与配置**
   [Journal Bot 配置](feishu-bot/README.md) · [Second Me 配置](knowledge-bot/README.md)

## 核心原则

- **先接住，再组织**：念头消失前完成捕捉，比建立复杂标签更重要。
- **原始材料优先**：清洗正文保留原文；一手记录高于 AI 生成的周复盘。
- **写入与理解分离**：Journal Bot 能写但克制，Second Me 能推断但只读。
- **内化而非引用表演**：日常回答直接使用长期材料，需要核对时再回到来源。
- **人格可以演进**：长期模型保存稳定原则，时间线保留新的变化。
- **本地拥有、模型可替换**：真正属于用户的是自己的 Markdown Vault。

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
└── docs/
    ├── PROJECT.md                   # 项目演进、设计决策与路线图
    ├── PHILOSOPHY.md                # 价值理念与产品理念
    └── PERSONAL-CASE-STUDY.md       # 作者的真实双 Bot 使用方式
```

更完整的项目总结见 [docs/PROJECT.md](docs/PROJECT.md)，价值与产品理念见 [docs/PHILOSOPHY.md](docs/PHILOSOPHY.md)，作者如何在真实生活里使用两个 Bot 见 [docs/PERSONAL-CASE-STUDY.md](docs/PERSONAL-CASE-STUDY.md)。飞书配置细节见 [feishu-bot/README.md](feishu-bot/README.md) 和 [knowledge-bot/README.md](knowledge-bot/README.md)。

## License

[MIT](LICENSE)
