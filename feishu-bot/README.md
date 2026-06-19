# 飞书机器人 · journal-organizer 前端套件

让你能**从手机随时口述/打字捕捉想法**，自动整理归类进笔记仓库的飞书机器人。
它是 `journal-organizer` skill 的一个「传输前端」——bot 只管收发消息，整理分类的"大脑"和归档格式跟 skill 共用同一份配置 `~/.config/journal-organizer/config.json`。

特性：实时归档 · 撤回/帮助命令 · **设备睡眠不丢**（醒来从飞书历史补抓）· 开机自启 · 崩溃自愈 · **每周复盘**（周日 21:00 自动写一篇连贯的本周复盘文章并推送）。

> 平台：macOS（用 launchd 常驻）。Linux 需改用 systemd（本套件未覆盖）。

---

## 为什么不能"对所有人一键"
每个人必须**自己**在飞书开放平台创建一个自建应用、拿到自己的 App ID/Secret——凭证不能共享。所以本套件自动化了所有「可自动化」的部分（部署脚本、生成配置、装服务、自愈），剩下两件**只能你自己做一次**：① 建飞书应用并登录 lark-cli；② 在飞书后台开事件订阅和权限。下面有傻瓜步骤。

---

## 安装步骤

### ① 装依赖
- [Node.js](https://nodejs.org)
- lark-cli：`npm install -g @larksuite/cli`
- [Claude Code](https://claude.com/claude-code)（bot 用它做整理，复用你的 Claude 订阅，不另花 API 费）

### ② 建飞书应用 + 登录 lark-cli
1. 去 [open.feishu.cn](https://open.feishu.cn/app) 创建一个**自建应用**，在「添加应用能力」里启用**机器人**。
2. 终端登录：`lark-cli auth login`，按提示填该应用的 App ID / App Secret。

### ③ 跑安装器
```bash
bash install.sh
```
它会检查环境、部署脚本、生成配置模板、装好开机自启服务。

### ④ 配置仓库和分类
编辑 `~/.config/journal-organizer/config.json`：把 `vault` 改成你的笔记仓库**绝对路径**，按需增删分类（分类预设见 skill 的 `references/default-categories.md`）。改完：
```bash
~/.journal-bot/ctl.sh restart
```

### ⑤ 在飞书后台开事件和权限（关键，否则收不到消息）
在你的应用页面：
1. **事件与回调 → 订阅方式**：选「**使用长连接接收事件**」（不用公网地址）。
2. **添加事件**：`im.message.receive_v1`（接收消息）。
3. **权限管理**：添加 `im:message.p2p_msg:readonly`（收私聊）+ 发消息权限（im:message 发送相关）。
4. **创建版本并发布**，让以上配置生效。

完成后，在飞书里找到你的机器人，私聊它发一条想法测试。

---

## 日常使用
私聊机器人**直接发想法文字**即可。
- 设备醒着 → 秒回执；设备睡着 → 照发不丢，醒来自动补归档。
- 发「撤回」/「删除上一条」→ 删掉最近归档那条。
- 发「周复盘」→ 立刻生成本周复盘文章（也会每周日 21:00 自动生成）。
- 发「帮助」→ 看用法。

**每周复盘**：每周日 21:00 自动抓取过去一周（周一~周日）所有分类的条目，写成一篇连贯的第一人称复盘文章，存进仓库的 `周复盘/` 文件夹并把全文推送到飞书。设备当时睡着也没关系，唤醒后 launchd 会补跑。

## 管理命令
```bash
~/.journal-bot/ctl.sh status     # 状态
~/.journal-bot/ctl.sh log        # 实时日志
~/.journal-bot/ctl.sh restart    # 重启
~/.journal-bot/ctl.sh stop       # 停止（务必用这个；kill 会被自愈机制拉起）
```

---

## 排错（都是实战踩过的坑）
- **收不到消息**：99% 是后台第 ⑤ 步没配全（长连接模式 / 事件 / 权限 / 发布）。`ctl.sh log` 看有没有 `feishu-websocket: connected`。
- **连接被代理打断**：飞书是国内服务，run.sh 已设 `LARK_CLI_NO_PROXY=1` 绕过本地代理。
- **后台跑会立刻退出**：consume 把 stdin EOF 当退出信号，run.sh 用 `< <(tail -f /dev/null)` 保活，已处理。
- **改了配置不生效**：handler 每条消息实时读配置，但保险起见 `ctl.sh restart`。
- **别开两个 bot**：同一个飞书应用只跑一个 consumer。如果你之前有旧版 bot 在跑，先停掉它再装本套件，否则两个进程会抢同一条事件流。

## 文件位置
- 运行目录：`~/.journal-bot/`（handler.py / run.sh / ctl.sh / 日志 / 状态）
- 共享配置：`~/.config/journal-organizer/config.json`（与 skill 共用）
- 服务：`~/Library/LaunchAgents/com.journal-bot.plist`

## 卸载
```bash
~/.journal-bot/ctl.sh stop
launchctl bootout gui/$(id -u)/com.journal-review 2>/dev/null
rm ~/Library/LaunchAgents/com.journal-bot.plist ~/Library/LaunchAgents/com.journal-review.plist
rm -rf ~/.journal-bot
# 笔记和配置保留；如需一并删除：rm -rf ~/.config/journal-organizer
```
