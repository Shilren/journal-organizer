# Capture Bot

Capture Bot 是 Journal Organizer 的写入层：从飞书接收文字或富文本，用 Codex 忠实整理和分类，追加写入 Markdown Vault，并负责撤回、历史补抓和周复盘。

## 安装

准备 Python 3、Node.js、`lark-cli` 和 Codex CLI，然后为这个 Bot 创建一个独立飞书应用/profile：

```bash
LARK_PROFILE=cli_capture bash feishu-bot/install.sh
```

配置文件位于：

```text
~/.config/journal-organizer/config.json
```

如果它不存在，安装器会从根目录的 `config.example.json` 创建。把 `vault` 改成知识库绝对路径，再重启：

```bash
~/.journal-bot/ctl.sh restart
```

## 飞书后台配置

1. 创建自建应用并启用机器人。
2. “事件与回调”选择“使用长连接接收事件”。
3. 订阅 `im.message.receive_v1`。
4. 开启接收私聊和发送消息权限。
5. 创建版本并发布。

## 命令

- 直接发文字或富文本：整理归档
- `撤回` / `删除上一条`：删除最近归档
- `周复盘`：立即生成本周复盘
- `帮助`：显示使用说明

每周日 21:00，launchd 会自动运行周复盘。也可以指定任意一周：

```bash
python3 ~/.journal-bot/weekly_review.py --week-start 2026-07-13 --no-push
```

## 可靠性

- 归档成功后才标记消息已处理。
- 每 180 秒补抓飞书历史，恢复睡眠或断线期间的消息。
- 实时和补抓使用同一份 `seen.txt` 去重。
- 每次写入同步追加 `weekly_entries.jsonl`，撤回写 tombstone；周复盘优先读索引，Vault 扫描作为回退。

## 排错

```bash
~/.journal-bot/ctl.sh status
~/.journal-bot/ctl.sh log
~/.journal-bot/ctl.sh restart
```

收不到消息时，优先检查长连接、事件、权限和应用版本是否已经发布。若同一个飞书应用有第二个 consumer 在运行，它们会竞争事件；Knowledge Bot 必须使用另一个应用/profile。
