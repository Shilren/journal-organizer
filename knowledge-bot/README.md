# Second Me / Knowledge Bot

Second Me 是 Journal Organizer 的只读问答层。代码目录仍叫 `knowledge-bot`，因为检索是它的技术基础；产品角色叫 Second Me，因为目标不止是找到材料，而是把长期经历和价值观内化成一个能够继续思考的视角。

它和 Journal Bot 形成一组互补关系：Journal Bot 保存“当时的我”，Second Me 带着这些材料回答“现在的我会怎么看”。

## 设计目标

- 深入理解材料，但不把回答写成“根据第几个文件”。
- 优先从相关分类寻找，而不是每次扫描后随机拼接。
- 原始记录优先；AI 生成的周复盘只用于辅助理解长期变化。
- 保留最近几轮对话，让连续追问自然承接。
- 默认短回复，需要创作、分析或复盘时再展开。
- Vault 全程只读，问答 Bot 不负责写入或修改原文。

## 产品边界

Second Me 不是搜索结果摘要，也不是静态数字克隆。它不会因为知识库里出现过一句话，就把那句话永久认定为用户人格；也不会为了显得熟悉而编造没有记录的经历。

它使用分层记忆：原始记录提供事实和真实措辞，周复盘帮助理解变化，长期自我模型保存用户确认过的稳定原则，最近对话负责当前承接。四者发生冲突时，具体事实回到原始材料，价值变化回到时间线和用户确认。

## 安装

先完成根目录 `config.example.json` 的配置，并为 Knowledge Bot 创建独立飞书应用和 `lark-cli profile`：

```bash
LARK_PROFILE=cli_knowledge bash knowledge-bot/install.sh
```

安装器会创建：

```text
~/.knowledge-bot/
├── handler.py
├── run.sh
├── ctl.sh
├── self_model.md
├── history.json
├── kb_index.jsonl
└── bot.log
```

## 长期自我模型

编辑 `~/.knowledge-bot/self_model.md`。高质量模型通常包含：

- 身份与重要经历
- 当前阶段的核心目标
- 稳定价值观和仍在变化的判断
- 决策时反复使用的评价函数
- 希望 Agent 呈现的人格与表达方式

模型不需要很长。越接近稳定、可执行的判断规则，越有用。具体事件仍应放在 Vault 原始记录中。

## 检索配置

根配置里的 `knowledge` 字段控制检索：

```json
{
  "knowledge": {
    "weekly_review_category": "周复盘",
    "exclude_dirs": [".obsidian", ".trash", "看板"],
    "max_chunks": 36,
    "category_keywords": {
      "工作与职业": ["工作", "面试", "求职"],
      "创作灵感": ["自媒体", "选题", "口播"]
    }
  }
}
```

Bot 默认直接扫描 Vault，保证新增记录立刻可检索；`重建索引` 会写入本地 JSONL 快照，当 Vault 因权限或挂载问题暂时不可读时作为回退。

## 两个 Bot 同时运行

可以同时运行，前提是使用两个不同的飞书自建应用 / profile。同一个应用启动两个事件 consumer 会竞争消息，看起来就像其中一个 Bot 偶尔不回复。
