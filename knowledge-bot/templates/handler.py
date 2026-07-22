#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only Feishu bot for a personal Markdown knowledge base.

The bot retrieves relevant notes, adds a configurable long-term self model and
recent chat history, then asks Codex for a concise answer. It never edits the
vault. Weekly reviews are treated as secondary AI-generated material and only
receive extra weight for timeline/growth questions.
"""

import datetime
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time


CONFIG_FILE = os.path.expanduser(
    os.environ.get("JOURNAL_CONFIG", "~/.config/journal-organizer/config.json")
)
BOT_DIR = os.path.expanduser(os.environ.get("KNOWLEDGE_BOT_DIR", "~/.knowledge-bot"))
APP_PROFILE = os.environ.get("LARK_PROFILE", "")
CODEX_BIN = os.environ.get("CODEX_BIN", "codex")
VAULT_OVERRIDE = os.environ.get("KNOWLEDGE_VAULT", "")

LOG_FILE = os.path.join(BOT_DIR, "bot.log")
SEEN_FILE = os.path.join(BOT_DIR, "seen.txt")
CHATS_FILE = os.path.join(BOT_DIR, "chats.json")
HISTORY_FILE = os.path.join(BOT_DIR, "history.json")
INDEX_FILE = os.path.join(BOT_DIR, "kb_index.jsonl")
SELF_MODEL_FILE = os.path.join(BOT_DIR, "self_model.md")

MAX_CONTEXT_CHARS = int(os.environ.get("KB_MAX_CONTEXT_CHARS", "52000"))
CATCHUP_INTERVAL = int(os.environ.get("KB_CATCHUP_INTERVAL", "180"))
CATCHUP_LOOKBACK_DAYS = int(os.environ.get("KB_CATCHUP_DAYS", "4"))
HISTORY_MAX_MESSAGES = int(os.environ.get("KB_HISTORY_MESSAGES", "8"))
HISTORY_MAX_CHARS = int(os.environ.get("KB_HISTORY_CHARS", "6000"))
SEEN = set()
LOCK = threading.Lock()

HELP_TEXT = """我是你的个人知识库问答机器人。

我会优先检索原始记录，结合你的长期自我模型和最近几轮对话回答；周复盘属于 AI 生成的二级材料，主要用于理解变化过程。

可以问：
· 我最近最重要的认知变化是什么？
· 我对工作或关系的核心判断是什么？
· 从我的材料里找几个自媒体选题
· 重建索引
"""


def log(message):
    os.makedirs(BOT_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(line)
    except Exception:
        pass
    sys.stderr.write(line)
    sys.stderr.flush()


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def save_json(path, value):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def load_config():
    return load_json(CONFIG_FILE, {})


def get_vault():
    raw = VAULT_OVERRIDE or load_config().get("vault", "")
    return os.path.expanduser(raw) if raw else ""


def knowledge_settings():
    cfg = load_config()
    knowledge = cfg.get("knowledge", {})
    category_meta = {}
    for item in cfg.get("categories", []):
        if isinstance(item, dict) and item.get("name"):
            category_meta[item["name"]] = {
                "desc": item.get("desc", ""),
                "keywords": item.get("keywords", []),
            }
    for category, words in knowledge.get("category_keywords", {}).items():
        category_meta.setdefault(category, {"desc": "", "keywords": []})
        category_meta[category]["keywords"] = list(words or [])
    return {
        "category_meta": category_meta,
        "weekly_category": knowledge.get("weekly_review_category", "周复盘"),
        "exclude_dirs": set(
            knowledge.get(
                "exclude_dirs",
                [".obsidian", ".trash", "看板", "dashboards", "templates"],
            )
        ),
        "max_chunks": int(knowledge.get("max_chunks", 36)),
    }


def run_codex(prompt, timeout=360):
    os.makedirs(BOT_DIR, exist_ok=True)
    fd, output_path = tempfile.mkstemp(prefix="kb-answer-", suffix=".md", dir=BOT_DIR)
    os.close(fd)
    command = [
        CODEX_BIN,
        "-a",
        "never",
        "exec",
        "-",
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--output-last-message",
        output_path,
    ]
    try:
        process = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=BOT_DIR,
            env={**os.environ, "LARK_CLI_NO_PROXY": "1"},
        )
        if process.returncode != 0:
            log(f"codex failed rc={process.returncode}: {(process.stderr or '')[:600]}")
            return None
        with open(output_path, encoding="utf-8") as handle:
            return handle.read().strip() or None
    except Exception as error:
        log(f"codex exception: {error}")
        return None
    finally:
        try:
            os.remove(output_path)
        except OSError:
            pass


def load_seen():
    SEEN.clear()
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, encoding="utf-8") as handle:
            SEEN.update(line.strip() for line in handle if line.strip())


def mark_seen(message_id):
    if not message_id or message_id in SEEN:
        return
    SEEN.add(message_id)
    with open(SEEN_FILE, "a", encoding="utf-8") as handle:
        handle.write(message_id + "\n")


def to_ms(value):
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        number = int(text)
        return number if number >= 10**12 else number * 1000
    return 0


def load_chats():
    return load_json(CHATS_FILE, {})


def register_chat(chat_id):
    if not chat_id:
        return
    chats = load_chats()
    if chat_id not in chats:
        chats[chat_id] = {"last_ts": 0}
        save_json(CHATS_FILE, chats)


def save_chat(chat_id, last_ts):
    if not chat_id:
        return
    chats = load_chats()
    previous = chats.get(chat_id, {}).get("last_ts", 0)
    chats[chat_id] = {"last_ts": max(int(previous or 0), to_ms(last_ts))}
    save_json(CHATS_FILE, chats)


def clean_message(text):
    text = html.unescape(text or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>\s*<p>", "\n", text, flags=re.I)
    text = re.sub(r"</?p>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def append_history(chat_id, role, text, create_time=None):
    if not chat_id or not text:
        return
    history = load_json(HISTORY_FILE, {})
    items = history.get(chat_id, [])
    items.append(
        {
            "role": role,
            "text": clean_message(text)[:3000],
            "time": str(create_time or datetime.datetime.now().isoformat(timespec="minutes")),
        }
    )
    history[chat_id] = items[-HISTORY_MAX_MESSAGES:]
    save_json(HISTORY_FILE, history)


def recent_history(chat_id):
    items = load_json(HISTORY_FILE, {}).get(chat_id, [])[-HISTORY_MAX_MESSAGES:]
    lines = []
    total = 0
    for item in items:
        role = "用户" if item.get("role") == "user" else "知识伙伴"
        line = f"{role}: {clean_message(item.get('text', ''))}"
        if total + len(line) > HISTORY_MAX_CHARS:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


def split_reply(text, limit=3500):
    text = text.strip()
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = text.rfind("\n\n", 0, limit)
        if cut < 800:
            cut = limit
        parts.append(text[:cut].strip())
        text = text[cut:].strip()
    return parts


def reply(chat_id, text):
    if not chat_id or not APP_PROFILE:
        return
    for chunk in split_reply(text):
        try:
            process = subprocess.run(
                [
                    "lark-cli",
                    "--profile",
                    APP_PROFILE,
                    "im",
                    "+messages-send",
                    "--as",
                    "bot",
                    "--chat-id",
                    chat_id,
                    "--text",
                    chunk,
                ],
                capture_output=True,
                text=True,
                timeout=45,
                env={**os.environ, "LARK_CLI_NO_PROXY": "1"},
            )
            if process.returncode != 0:
                log(f"reply failed rc={process.returncode}: {(process.stderr or '')[:400]}")
        except Exception as error:
            log(f"reply exception: {error}")


def iter_note_files(vault, settings):
    for root, dirs, files in os.walk(vault):
        dirs[:] = [
            item
            for item in dirs
            if item not in settings["exclude_dirs"] and not item.startswith(".")
        ]
        for filename in files:
            if filename.endswith(".md") and not filename.endswith(".manual-backup.md"):
                path = os.path.join(root, filename)
                yield path, os.path.relpath(path, vault)


def split_markdown(path, relative_path):
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except Exception:
        return []
    text = re.sub(r"> \[!note\]- 原始记录[\s\S]*?(?=\n---|\Z)", "", text)
    text = re.sub(r"> \[!note\]- 原始语音转录[\s\S]*?(?=\n---|\Z)", "", text)
    category = relative_path.split(os.sep)[0] if os.sep in relative_path else "根目录"
    chunks = []
    blocks = text.split("\n## ")
    if len(blocks) > 1:
        for block in blocks[1:]:
            title, _, body = block.partition("\n")
            body = body.replace("\n---", "").strip()
            if body:
                chunks.append(
                    {
                        "category": category,
                        "rel": relative_path,
                        "title": title.strip(),
                        "text": body[:6000],
                    }
                )
    elif text.strip():
        title = text.strip().splitlines()[0].lstrip("# ").strip()[:100]
        chunks.append(
            {
                "category": category,
                "rel": relative_path,
                "title": title,
                "text": text.strip()[:8000],
            }
        )
    return chunks


def scan_chunks():
    vault = get_vault()
    settings = knowledge_settings()
    if not vault or not os.path.isdir(vault):
        return []
    chunks = []
    for path, relative_path in iter_note_files(vault, settings):
        chunks.extend(split_markdown(path, relative_path))
    return chunks


def rebuild_index():
    chunks = scan_chunks()
    with open(INDEX_FILE, "w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    return len(chunks)


def load_index():
    chunks = []
    if not os.path.exists(INDEX_FILE):
        return chunks
    with open(INDEX_FILE, encoding="utf-8") as handle:
        for line in handle:
            try:
                chunks.append(json.loads(line))
            except Exception:
                continue
    return chunks


def query_terms(query):
    lower = query.lower()
    terms = set(re.findall(r"[a-zA-Z0-9_]+", lower))
    cjk = re.findall(r"[\u4e00-\u9fff]", lower)
    terms.update("".join(cjk[i : i + 2]) for i in range(max(0, len(cjk) - 1)))
    terms.update("".join(cjk[i : i + 3]) for i in range(max(0, len(cjk) - 2)))
    return {term for term in terms if term}


def asks_for_trend(query):
    words = [
        "变化",
        "成长",
        "趋势",
        "过程",
        "阶段",
        "复盘",
        "回顾",
        "最近",
        "过去",
        "演化",
        "timeline",
        "trend",
        "review",
    ]
    lower = query.lower()
    return any(word in lower for word in words)


def preferred_categories(query, settings):
    lower = query.lower()
    preferred = []
    for category, meta in settings["category_meta"].items():
        words = [category, meta.get("desc", ""), *meta.get("keywords", [])]
        if any(str(word).lower() in lower for word in words if word):
            preferred.append(category)
    return preferred


def is_weekly_review(chunk, settings):
    category = settings["weekly_category"]
    return chunk.get("category") == category or str(chunk.get("rel", "")).startswith(category + os.sep)


def chunk_score(chunk, terms, preferred, trend_query, settings):
    haystack = "\n".join(
        [chunk.get("category", ""), chunk.get("rel", ""), chunk.get("title", ""), chunk.get("text", "")]
    ).lower()
    score = sum((4 if len(term) >= 2 else 1) for term in terms if term in haystack)
    if chunk.get("category") in preferred:
        score += 18
    if is_weekly_review(chunk, settings):
        score -= 10
        if trend_query:
            score += 20
    date_match = re.search(r"20\d{2}-\d{2}-\d{2}", chunk.get("rel", ""))
    if date_match:
        try:
            age = (datetime.date.today() - datetime.date.fromisoformat(date_match.group(0))).days
            score += max(0, 10 - age // 7)
        except ValueError:
            pass
    return score


def retrieve_context(query):
    settings = knowledge_settings()
    chunks = scan_chunks()
    source = "vault"
    if not chunks:
        chunks = load_index()
        source = "index"
    terms = query_terms(query)
    preferred = preferred_categories(query, settings)
    trend_query = asks_for_trend(query)
    scored = [
        (chunk_score(chunk, terms, preferred, trend_query, settings), chunk)
        for chunk in chunks
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = []
    seen = set()
    for score, chunk in scored:
        key = (chunk.get("rel"), chunk.get("title"))
        if key in seen:
            continue
        seen.add(key)
        selected.append((score, chunk))
        if len(selected) >= settings["max_chunks"]:
            break
    parts = []
    total = 0
    for score, chunk in selected:
        material_type = "AI生成的周复盘/二级材料" if is_weekly_review(chunk, settings) else "原始记录/一手材料"
        part = (
            f"【{chunk.get('category')}｜{chunk.get('rel')}｜{chunk.get('title')}｜"
            f"{material_type}｜score={score}】\n{chunk.get('text', '').strip()}\n"
        )
        if total + len(part) > MAX_CONTEXT_CHARS:
            break
        parts.append(part)
        total += len(part)
    log(f"retrieve source={source} chunks={len(chunks)} selected={len(parts)}")
    return "\n---\n".join(parts)


def load_self_model():
    try:
        with open(SELF_MODEL_FILE, encoding="utf-8") as handle:
            return handle.read().strip()
    except Exception:
        return ""


def answer_question(question, chat_id):
    context = retrieve_context(question)
    if not context:
        return "我暂时没有在知识库里检索到能支撑这个问题的材料。"
    history = recent_history(chat_id)
    prompt = f"""你是一个高度个性化的个人知识伙伴。你已经内化了长期自我模型和知识库材料，回答时直接使用这些判断，不要把回复写成检索报告。

规则：
- 以原始记录为主要依据；周复盘是 AI 生成的二级材料，只适合辅助判断长期变化。
- 自然接住最近几轮对话，不机械复述上下文。
- 默认简短、具体、像熟悉用户的人在聊天；写稿、复盘或长文任务再展开。
- 除非用户明确索要来源，否则不列文件名、不说“根据你的知识库”。
- 区分材料中的事实、用户观点和你的推断；没有依据时坦率说明，不编造经历。
- 尊重用户的主体性和个人价值观，同时保持基本判断力。遇到可能伤害他人或违法的请求，不提供可执行的伤害步骤，转向用户真正想争取的目标和可持续方案。

<长期自我模型>
{load_self_model()}
</长期自我模型>

<最近对话>
{history}
</最近对话>

<用户问题>
{question}
</用户问题>

<检索材料>
{context}
</检索材料>
"""
    return run_codex(prompt) or "我找到了相关材料，但这次生成回答失败了，请稍后再发一次。"


def process_message(message_id, chat_id, message_type, content, create_time, source="实时"):
    with LOCK:
        if message_id and message_id in SEEN:
            return
        register_chat(chat_id)
        text = clean_message(content)
        if not text:
            mark_seen(message_id)
            save_chat(chat_id, create_time)
            return
        if message_type not in {"text", "post"}:
            reply(chat_id, "我目前只处理文字消息。")
        elif text.lower().strip() in {"help", "帮助", "?", "？", "怎么用"}:
            reply(chat_id, HELP_TEXT)
        elif text.strip() in {"重建索引", "更新索引"}:
            count = rebuild_index()
            reply(chat_id, f"知识库索引已更新，共 {count} 个片段。")
        else:
            log(f"[{source}] question: {text[:80]}")
            reply(chat_id, "我在知识库里找材料，稍等。")
            answer = answer_question(text, chat_id)
            reply(chat_id, answer)
            append_history(chat_id, "user", text, create_time)
            append_history(chat_id, "assistant", answer)
        mark_seen(message_id)
        save_chat(chat_id, create_time)


def handle_event(event):
    if "event_id" not in event and isinstance(event.get("event"), dict):
        event = event["event"]
    process_message(
        event.get("message_id") or event.get("id") or event.get("event_id") or "",
        event.get("chat_id", ""),
        event.get("message_type", ""),
        event.get("content", "") or "",
        event.get("create_time") or event.get("timestamp") or "0",
    )


def parse_history_message(item):
    sender = item.get("sender") or {}
    return (
        item.get("message_id") or item.get("id") or "",
        item.get("chat_id") or "",
        item.get("msg_type") or item.get("message_type") or "",
        item.get("content") or "",
        item.get("create_time") or "0",
        (sender.get("sender_type") or "").lower() in ("app", "bot"),
        bool(item.get("deleted")),
    )


def catch_up():
    if not APP_PROFILE:
        return
    floor_ms = int(time.time() * 1000) - CATCHUP_LOOKBACK_DAYS * 86400 * 1000
    for chat_id in list(load_chats()):
        try:
            process = subprocess.run(
                [
                    "lark-cli",
                    "--profile",
                    APP_PROFILE,
                    "im",
                    "+chat-messages-list",
                    "--as",
                    "bot",
                    "--chat-id",
                    chat_id,
                    "--sort",
                    "desc",
                    "--format",
                    "json",
                    "--page-size",
                    "30",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "LARK_CLI_NO_PROXY": "1"},
            )
            data = json.loads(process.stdout or "{}").get("data") or {}
        except Exception as error:
            log(f"catch-up failed: {error}")
            continue
        items = list(reversed(data.get("items") or data.get("messages") or []))
        for item in items:
            mid, cid, msg_type, text, created, is_bot, deleted = parse_history_message(item)
            if not mid or mid in SEEN:
                continue
            if deleted or is_bot or text == "[Invalid text JSON]" or to_ms(created) < floor_ms:
                mark_seen(mid)
                continue
            process_message(mid, cid or chat_id, msg_type, text, created, source="补抓")


def catch_up_loop():
    while True:
        time.sleep(CATCHUP_INTERVAL)
        try:
            catch_up()
        except Exception as error:
            log(f"catch-up loop error: {error}")


def main():
    os.makedirs(BOT_DIR, exist_ok=True)
    if not APP_PROFILE:
        raise SystemExit("LARK_PROFILE is required")
    if not get_vault():
        raise SystemExit(f"vault is missing in {CONFIG_FILE}")
    load_seen()
    log("knowledge bot ready")
    try:
        catch_up()
    except Exception as error:
        log(f"startup catch-up error: {error}")
    threading.Thread(target=catch_up_loop, daemon=True).start()
    for line in sys.stdin:
        try:
            if line.strip():
                handle_event(json.loads(line))
        except Exception as error:
            log(f"handle error: {error}")


if __name__ == "__main__":
    main()
