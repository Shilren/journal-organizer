#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 → journal-organizer 桥接处理器（通用版）

从 `lark-cli event consume im.message.receive_v1` 的 NDJSON 事件流读消息，
对每条文字：用 claude -p 按原始语序整理并分类 -> 写入 vault -> 飞书回执。
睡眠/断线期间的消息会在唤醒/重启时从飞书历史补抓回来（不丢）。

仓库路径与分类来自与 journal-organizer skill 共用的配置：
    ~/.config/journal-organizer/config.json
所以分类/仓库只需维护这一处。
"""
import sys, os, json, re, subprocess, datetime, time, threading

CONFIG_FILE = os.path.expanduser("~/.config/journal-organizer/config.json")
STATE_DIR = os.path.expanduser("~/.journal-bot")
SEEN_FILE = os.path.join(STATE_DIR, "seen.txt")
LOG_FILE = os.path.join(STATE_DIR, "bot.log")
LAST_NOTE_FILE = os.path.join(STATE_DIR, "last_note.json")
CHATS_FILE = os.path.join(STATE_DIR, "chats.json")

CATCHUP_INTERVAL = 180
CATCHUP_LOOKBACK_DAYS = 4   # 补抓只看最近 N 天，防止 SEEN 丢失时回灌历史
PROC_LOCK = threading.Lock()
SEEN = set()

DELETE_RE = re.compile(r"(撤回|撤销|删除|删掉|删了|不要这条|不要刚|去掉刚|undo)", re.I)
HELP_WORDS = {"帮助", "help", "?", "？", "指令", "命令", "怎么用"}
REVIEW_WORDS = {"周复盘", "周报", "本周复盘", "周总结", "周小结", "weekly"}
HELP_TEXT = (
    "我是想法归档机器人～\n"
    "· 直接发想法 → 自动整理归档\n"
    "· 发「撤回」/「删除上一条」→ 删掉最近归档的那条\n"
    "· 发「周复盘」→ 立刻生成本周复盘文章\n"
    "· 发「帮助」→ 看这条说明\n"
    "（设备睡眠时消息不丢，醒来会自动补归档）"
)

PROMPT_TMPL = """你是想法整理助手。下面 <<<>>> 之间是用户口述/语音转录的一段当下所思所想，可能口语化、有重复、有口头禅、语序跳跃。

请判定分类、起小标题、按【原始语序】整理正文，然后严格按下面三段格式输出，不要任何额外说明、不要代码围栏：

分类：从下面这些里选最贴合的一个（逐字一致，只输出分类名）：
{cat_lines}
标题：一句话小标题，不超过20字
正文：
（整理后的正文，可多段。原则：去掉口头禅、语气词、明显重复和卡顿，修正错别字、断句、标点；严格顺着原话推进顺序，不重排结构、不把后面说的提到前面、不替用户下结论、不加他没表达的观点；同一段内确实并列的要点可用 "- " 列表，但不得打乱整体语序；保留第一人称口吻，读起来仍像他本人在说。）

用户原文：
<<<
%s
>>>"""


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    sys.stderr.write(line)
    sys.stderr.flush()


def load_config():
    """返回 (vault, [category names], prompt_with_cat_lines)。配置缺失则返回 (None, [], None)。"""
    if not os.path.exists(CONFIG_FILE):
        return None, [], None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        log(f"配置解析失败: {e}")
        return None, [], None
    vault = os.path.expanduser(cfg.get("vault", ""))
    cats = cfg.get("categories", [])
    names = [c["name"] for c in cats if c.get("name")]
    cat_lines = "\n".join(f"- {c['name']}：{c.get('desc','')}" for c in cats if c.get("name"))
    prompt = PROMPT_TMPL.format(cat_lines=cat_lines)
    return (vault or None), names, prompt


# ———————————————— 去重 / 会话状态 ————————————————
def load_seen():
    SEEN.clear()
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            for x in f:
                if x.strip():
                    SEEN.add(x.strip())


def mark_seen(mid):
    SEEN.add(mid)
    with open(SEEN_FILE, "a", encoding="utf-8") as f:
        f.write(mid + "\n")


def to_ms(v):
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if not s:
        return 0
    if s.isdigit():
        n = int(s)
        return n if n >= 10 ** 12 else n * 1000
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return int(datetime.datetime.strptime(s, fmt).timestamp() * 1000)
        except Exception:
            pass
    return 0


def ms_to_iso(ms):
    return datetime.datetime.fromtimestamp(to_ms(ms) / 1000).astimezone().isoformat()


def load_chats():
    if not os.path.exists(CHATS_FILE):
        return {}
    try:
        with open(CHATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_chat(chat_id, last_ts):
    """推进会话水位线——仅在消息已妥善处理后调用。"""
    if not chat_id:
        return
    chats = load_chats()
    prev = chats.get(chat_id, {}).get("last_ts", 0)
    chats[chat_id] = {"last_ts": max(int(prev or 0), to_ms(last_ts))}
    with open(CHATS_FILE, "w", encoding="utf-8") as f:
        json.dump(chats, f, ensure_ascii=False)


def register_chat(chat_id):
    """登记会话（让补抓知道有它），但不推进水位线。"""
    if not chat_id:
        return
    chats = load_chats()
    if chat_id not in chats:
        chats[chat_id] = {"last_ts": 0}
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(chats, f, ensure_ascii=False)


FAILS = {}        # 整理失败重试计数（内存）
MAX_TRIES = 3


# ———————————————— 整理 / 归档 ————————————————
def organize(text, prompt, cat_names):
    try:
        proc = subprocess.run(
            # 关键：--setting-sources '' 不加载用户级一堆 skill，--strict-mcp-config 禁 MCP，
            # 把每次启动开销从 ~60s 砍到几秒，避免长输入超时丢消息。prompt 必须紧跟 -p。
            ["claude", "-p", prompt % text, "--model", "sonnet",
             "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
             "--setting-sources", ""],
            capture_output=True, text=True, timeout=180,
        )
    except Exception as e:
        log(f"claude 调用异常: {e}")
        return None
    out = (proc.stdout or "").strip()
    if not out:
        log(f"claude 无输出, stderr={proc.stderr[:300]}")
        return None
    cat_m = re.search(r"分类[:：]\s*(.+)", out)
    title_m = re.search(r"标题[:：]\s*(.+)", out)
    body_m = re.search(r"正文[:：]\s*\n?(.*)\Z", out, re.S)
    if not (cat_m and title_m and body_m):
        log(f"输出格式不符: {out[:200]}")
        return None
    raw_cat = cat_m.group(1).strip()
    cat = next((c for c in cat_names if c in raw_cat), "")
    if not cat:
        cat = cat_names[0] if cat_names else "未分类"
        log(f"分类无法识别({raw_cat})，归到 {cat}")
    title = title_m.group(1).strip().strip("（）()【】[]")
    body = body_m.group(1).strip()
    if not body:
        return None
    return {"category": cat, "title": title, "body": body}


def append_note(vault, category, title, body, original):
    folder = os.path.join(vault, category)
    os.makedirs(folder, exist_ok=True)
    now = datetime.datetime.now()
    date = now.strftime("%Y-%m-%d")
    hm = now.strftime("%H:%M")
    path = os.path.join(folder, date + ".md")
    created = not os.path.exists(path)
    if original:
        quoted = "\n".join("> " + ln for ln in original.splitlines())
        callout = f"\n\n> [!note]- 原始记录\n{quoted}"
    else:
        callout = ""
    block = f"\n## {hm} · {title}\n\n{body}{callout}\n\n---\n"
    with open(path, "a", encoding="utf-8") as f:
        if created:
            f.write(f"# {date} · {category}\n")
        f.write(block)
    with open(path, "r", encoding="utf-8") as f:
        count = len(re.findall(r"^## ", f.read(), re.M))
    with open(LAST_NOTE_FILE, "w", encoding="utf-8") as f:
        json.dump({"path": path, "category": category, "title": title}, f, ensure_ascii=False)
    return path, count


def delete_last_note():
    if not os.path.exists(LAST_NOTE_FILE):
        return False, "没有可撤回的记录。"
    try:
        with open(LAST_NOTE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        return False, "撤回状态读取失败。"
    path, title, category = state.get("path", ""), state.get("title", ""), state.get("category", "")
    if not path or not os.path.exists(path):
        os.remove(LAST_NOTE_FILE)
        return False, "上一条对应的文件已不存在。"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    idx = content.rfind("\n## ")
    if idx == -1:
        return False, "没找到可删除的条目。"
    remaining = content[:idx].rstrip() + "\n"
    if "## " in remaining:
        with open(path, "w", encoding="utf-8") as f:
            f.write(remaining)
    else:
        os.remove(path)
    os.remove(LAST_NOTE_FILE)
    return True, f"已撤回上一条：「{category}」· {title}"


def reply(chat_id, text):
    try:
        subprocess.run(
            ["lark-cli", "im", "+messages-send", "--as", "bot",
             "--chat-id", chat_id, "--text", text],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        log(f"回执失败: {e}")


def process_message(message_id, chat_id, mtype, text, create_time, source="实时"):
    with PROC_LOCK:
        if message_id and message_id in SEEN:
            return
        # 先登记会话，但只有"妥善处理"后才 finish()（标记已处理 + 推进水位线），
        # 这样整理失败的消息会被补抓自动重试，而不是开头就被标记成已读而永久丢失。
        if chat_id:
            register_chat(chat_id)

        def finish():
            if message_id:
                mark_seen(message_id)
            if chat_id:
                save_chat(chat_id, create_time or 0)
            FAILS.pop(message_id, None)

        vault, cat_names, prompt = load_config()
        if not vault or not cat_names:
            log("配置缺失（vault/categories），无法归档")
            if source == "实时" and chat_id:
                reply(chat_id, "还没配置好仓库和分类，请在电脑上运行安装器或编辑 ~/.config/journal-organizer/config.json")
            return  # 不 finish：配好后补抓会重试

        if mtype != "text":
            log(f"[{source}] 跳过非文字 type={mtype}")
            if source == "实时" and chat_id:
                reply(chat_id, "目前只支持文字消息哦～语音转写功能稍后接入。")
            finish()
            return

        t = (text or "").strip()
        if not t:
            finish()
            return
        log(f"[{source}] 收到: {t[:50]}...")

        low = t.lower().strip("。.!！~ ")
        if low in HELP_WORDS:
            if chat_id:
                reply(chat_id, HELP_TEXT)
            finish()
            return
        if low in REVIEW_WORDS:
            log(f"[{source}] 手动触发周复盘")
            if chat_id:
                reply(chat_id, "📝 正在生成本周复盘，约 1 分钟，稍等～")
            subprocess.Popen(
                [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "weekly_review.py"),
                 "--chat-id", chat_id or ""],
                env={**os.environ, "LARK_CLI_NO_PROXY": "1"},
            )
            finish()
            return
        if len(t) <= 12 and DELETE_RE.search(t):
            ok, msg = delete_last_note()
            log(f"[{source}] 撤回: {msg}")
            if chat_id:
                reply(chat_id, msg)
            finish()
            return
        if len(t) < 3:
            log(f"[{source}] 内容过短，跳过: {t!r}")
            if source == "实时" and chat_id:
                reply(chat_id, "这条太短了，没存～想记录的话多说几句哈。")
            finish()
            return

        data = organize(t, prompt, cat_names)
        if not data:
            # 整理失败：不标记已处理，让补抓稍后自动重试；超过上限才放弃
            n = FAILS.get(message_id, 0) + 1
            FAILS[message_id] = n
            if n >= MAX_TRIES:
                log(f"[{source}] 整理连续失败 {n} 次，放弃: {t[:40]}")
                if message_id:
                    mark_seen(message_id)
                if chat_id:
                    save_chat(chat_id, create_time or 0)
                    reply(chat_id, "这条我整理了几次都没成功，先跳过了，方便的话麻烦重发一遍～")
            else:
                log(f"[{source}] 整理失败({n}/{MAX_TRIES})，稍后自动重试: {t[:40]}")
                if source == "实时" and chat_id:
                    reply(chat_id, "整理没成功，待会儿我会自动再试一次，这条没丢～")
            return
        path, count = append_note(vault, data["category"], data["title"], data["body"], t)
        log(f"[{source}] 已写入 {path} (今日第{count}条)")
        finish()
        if chat_id:
            reply(chat_id, f"已归档到「{data['category']}」· 今天第 {count} 条\n小标题：{data['title']}")


def handle(ev):
    if "event_id" not in ev and isinstance(ev.get("event"), dict):
        ev = ev["event"]
    message_id = ev.get("message_id") or ev.get("id") or ev.get("event_id") or ""
    chat_id = ev.get("chat_id", "")
    mtype = ev.get("message_type", "")
    content = ev.get("content", "") or ""
    ct = ev.get("create_time") or ev.get("timestamp") or "0"
    process_message(message_id, chat_id, mtype, content, ct, source="实时")


# ———————————————— 补抓 ————————————————
def parse_history_msg(it):
    mid = it.get("message_id") or it.get("id") or ""
    mt = it.get("msg_type") or it.get("message_type") or ""
    ct = it.get("create_time") or "0"
    text = it.get("content") or ""
    sender = it.get("sender") or {}
    is_bot = (sender.get("sender_type") or "").lower() in ("app", "bot")
    return mid, mt, text, ct, is_bot


def catch_up():
    chats = load_chats()
    if not chats:
        return
    floor_ms = to_ms(datetime.datetime.now().timestamp() * 1000) - CATCHUP_LOOKBACK_DAYS * 86400 * 1000
    for chat_id in list(chats.keys()):
        # 拉最近 50 条（倒序取最新），靠 SEEN 去重，不依赖水位线做正确性——
        # 这样整理失败而未标记的消息每轮都会被重试，直到成功或达上限。
        cmd = ["lark-cli", "im", "+chat-messages-list", "--as", "bot",
               "--chat-id", chat_id, "--sort", "desc", "--format", "json", "--page-size", "50"]
        env = {**os.environ, "LARK_CLI_NO_PROXY": "1"}
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
            d = json.loads(p.stdout or "{}")
        except Exception as e:
            log(f"[补抓] 拉取失败 {chat_id}: {e}")
            continue
        data = d.get("data") or {}
        items = list(reversed(data.get("items") or data.get("messages") or []))  # 还原成时间正序
        new = 0
        for it in items:
            mid, mt, txt, ct, is_bot = parse_history_msg(it)
            if not mid or mid in SEEN:
                continue
            if is_bot:
                mark_seen(mid)
                continue
            if to_ms(ct) < floor_ms:
                continue  # 太旧，超出补抓窗口，不处理（防止 SEEN 丢失时回灌历史）
            process_message(mid, chat_id, mt, txt, ct, source="补抓")
            new += 1
        if new:
            log(f"[补抓] {chat_id} 处理了 {new} 条")


def catch_up_loop():
    while True:
        time.sleep(CATCHUP_INTERVAL)
        try:
            catch_up()
        except Exception as e:
            log(f"[补抓] 循环异常: {e}")


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    load_seen()
    log("想法机器人已就绪，开始监听飞书消息……")
    try:
        catch_up()
    except Exception as e:
        log(f"[补抓] 启动补抓异常: {e}")
    threading.Thread(target=catch_up_loop, daemon=True).start()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        try:
            handle(ev)
        except Exception as e:
            log(f"处理异常: {e}")


if __name__ == "__main__":
    main()
