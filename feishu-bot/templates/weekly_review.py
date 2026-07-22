#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每周复盘生成器（通用版）：抓取过去一周（周一~周日）各分类条目正文，
用 Codex 写成一篇连贯的第一人称复盘文章，存进 vault/周复盘/，并按需推送飞书。

仓库路径取自与 skill 共用的配置 ~/.config/journal-organizer/config.json。
用法：
  python3 weekly_review.py                 # 本周，存仓库+推送飞书
  python3 weekly_review.py --no-push       # 只存仓库
  python3 weekly_review.py --chat-id oc_x  # 指定推送会话
"""
import os, re, sys, json, subprocess, datetime, argparse, tempfile

CONFIG_FILE = os.path.expanduser("~/.config/journal-organizer/config.json")
STATE_DIR = os.path.expanduser("~/.journal-bot")
CHATS_FILE = os.path.join(STATE_DIR, "chats.json")
LOG_FILE = os.path.join(STATE_DIR, "bot.log")
WEEKLY_INDEX_FILE = os.path.join(STATE_DIR, "weekly_entries.jsonl")
CODEX_BIN = os.environ.get("CODEX_BIN", "codex")
EXCLUDE = {"周复盘", "看板", "dashboards", "templates", ".trash"}


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [周复盘] {msg}\n"
    try:
        open(LOG_FILE, "a", encoding="utf-8").write(line)
    except Exception:
        pass
    sys.stderr.write(line); sys.stderr.flush()


def get_vault():
    try:
        cfg = json.load(open(CONFIG_FILE, encoding="utf-8"))
        return os.path.expanduser(cfg.get("vault", "")) or None
    except Exception as e:
        log(f"读配置失败: {e}")
        return None


def get_categories():
    try:
        cfg = json.load(open(CONFIG_FILE, encoding="utf-8"))
        cats = []
        for item in cfg.get("categories", []):
            if isinstance(item, dict) and item.get("name"):
                cats.append(item["name"])
            elif isinstance(item, str):
                cats.append(item)
        return cats
    except Exception as e:
        log(f"读分类配置失败: {e}")
        return []


PROMPT = """你是一位善于复盘的写作者，帮我把我这一周记录的零散想法，写成一篇连贯的「本周复盘」文章，方便我日后回看。

下面 <<< >>> 之间是我这一周（{rng}）按分类记录的所思所想（含每条小标题和正文）。

请写一篇第一人称的复盘文章，要求：
- 像我自己在回顾这一周，用我的口吻，真实、有洞察；不喊口号、不拔高、不编造我没表达过的东西。
- 不要简单罗列或按分类复述，而是提炼出贯穿这周的几条主线/主题，把不同分类里相关的想法自然串联起来。
- 点出我的变化与进展，以及我反复纠结或自相矛盾的地方。
- 结构自然流畅、有起承转合；可用少量小标题分段，但整体要读起来是一篇文章，不是清单。
- 开头一句点出这周的总体基调；结尾给一两句面向下周、从我本周思考里自然长出来的提醒（不要鸡汤）。

只输出文章正文（含小标题），不要任何额外说明或前言。

我这一周的记录：
<<<
{material}
>>>"""


def collect(vault, monday, sunday):
    indexed = collect_from_index(monday, sunday)
    if indexed:
        log(f"从周复盘索引收集 {len(indexed)} 条")
        return indexed
    log("周复盘索引为空，回退扫描 Obsidian 仓库")
    out = []
    categories = [c for c in get_categories() if c not in EXCLUDE]
    if not categories:
        log("分类配置为空，无法收集周复盘材料")
        return out
    for cat in categories:
        d = os.path.join(vault, cat)
        if not os.path.isdir(d) or cat in EXCLUDE:
            continue
        for fn in os.listdir(d):
            m = re.match(r"^(\d{4}-\d{2}-\d{2})\.md$", fn)
            if not m:
                continue
            day = datetime.date.fromisoformat(m.group(1))
            if not (monday <= day <= sunday):
                continue
            content = open(os.path.join(d, fn), encoding="utf-8").read()
            for block in content.split("\n## ")[1:]:
                head, _, rest = block.partition("\n")
                for marker in ("> [!note]", "\n---"):
                    i = rest.find(marker)
                    if i != -1:
                        rest = rest[:i]
                hm = re.match(r"\s*(\d{1,2}:\d{2})\s*[·:：]\s*(.*)", head)
                title = hm.group(2).strip() if hm else head.strip()
                body = rest.strip()
                if body:
                    out.append((cat, m.group(1), title, body))
    out.sort(key=lambda x: x[1])
    return out


def collect_from_index(monday, sunday):
    if not os.path.exists(WEEKLY_INDEX_FILE):
        return []
    rows = []
    deleted = set()
    try:
        with open(WEEKLY_INDEX_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if item.get("type") == "delete" and item.get("id"):
                    deleted.add(item["id"])
                    continue
                if item.get("type") != "entry":
                    continue
                entry_id = item.get("id", "")
                date_s = item.get("date", "")
                try:
                    day = datetime.date.fromisoformat(date_s)
                except Exception:
                    continue
                if not (monday <= day <= sunday):
                    continue
                cat = str(item.get("category", "")).strip()
                if not cat or cat in EXCLUDE:
                    continue
                title = str(item.get("title", "")).strip() or "未命名记录"
                body = str(item.get("body", "")).strip()
                if body:
                    rows.append((entry_id, cat, date_s, title, body))
    except Exception as e:
        log(f"读取周复盘索引失败: {e}")
        return []
    rows = [(cat, date_s, title, body) for entry_id, cat, date_s, title, body in rows if not entry_id or entry_id not in deleted]
    rows.sort(key=lambda x: x[1])
    return rows


def build_material(entries):
    by_cat = {}
    for cat, date, title, body in entries:
        by_cat.setdefault(cat, []).append(f"[{date}] {title}\n{body}")
    return "\n\n".join(f"## 【{c}】\n\n" + "\n\n".join(v) for c, v in by_cat.items())


def run_codex(prompt, timeout=420):
    os.makedirs(STATE_DIR, exist_ok=True)
    fd, out_path = tempfile.mkstemp(prefix="codex-review-", suffix=".md", dir=STATE_DIR)
    os.close(fd)
    cmd = [
        CODEX_BIN, "-a", "never", "exec", "-",
        "--skip-git-repo-check", "--ephemeral", "--sandbox", "read-only",
        "--output-last-message", out_path,
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=STATE_DIR,
            env={**os.environ, "LARK_CLI_NO_PROXY": "1"},
        )
        if proc.returncode != 0:
            log(f"codex 调用失败 rc={proc.returncode}, stderr={(proc.stderr or '')[:500]}, stdout={(proc.stdout or '')[:500]}")
            return None
        try:
            return open(out_path, encoding="utf-8").read().strip() or None
        except Exception as e:
            log(f"读取 codex 输出失败: {e}")
            return None
    except Exception as e:
        log(f"codex 调用异常: {e}")
        return None
    finally:
        try:
            os.remove(out_path)
        except Exception:
            pass


def write_article(text):
    return run_codex(text)


APP_PROFILE = os.environ.get("LARK_PROFILE", "")


def push_feishu(chat_id, header, article):
    try:
        p = subprocess.run(
            ["lark-cli", "--profile", APP_PROFILE, "im", "+messages-send", "--as", "bot",
             "--chat-id", chat_id, "--markdown", f"{header}\n\n{article}"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "LARK_CLI_NO_PROXY": "1"},
        )
        if p.returncode == 0:
            log("已推送到飞书")
        else:
            log(f"推送失败 rc={p.returncode}: {(p.stderr or p.stdout or '').strip()[:500]}")
    except Exception as e:
        log(f"推送失败: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--chat-id", default="")
    ap.add_argument("--week-start", default="", help="指定周一日期，例如 2026-06-29")
    args = ap.parse_args()

    vault = get_vault()
    if not vault or not os.path.isdir(vault):
        log("仓库未配置或不存在，终止")
        return

    if args.week_start:
        monday = datetime.date.fromisoformat(args.week_start)
    else:
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
    sunday = monday + datetime.timedelta(days=6)
    rng = f"{monday:%Y-%m-%d} ~ {sunday:%m-%d}"

    entries = collect(vault, monday, sunday)
    if not entries:
        log(f"本周({rng})没有记录，跳过")
        return
    log(f"本周({rng}) 共 {len(entries)} 条，开始生成……")

    article = write_article(PROMPT.format(rng=rng, material=build_material(entries)))
    if not article:
        log("生成失败")
        return

    out_dir = os.path.join(vault, "周复盘")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{monday:%Y-%m-%d}_{sunday:%m-%d}.md")
    meta = f"\n> 自动生成于 {datetime.datetime.now():%Y-%m-%d %H:%M} · 本周 {len(entries)} 条记录\n"
    open(path, "w", encoding="utf-8").write(f"# 本周复盘 · {rng}\n{meta}\n{article}\n")
    log(f"已写入 {path}")

    if not args.no_push:
        chat_id = args.chat_id
        if not chat_id and os.path.exists(CHATS_FILE):
            chat_id = next(iter(json.load(open(CHATS_FILE, encoding="utf-8"))), "")
        if chat_id:
            push_feishu(chat_id, f"📝 本周复盘已生成 · {rng}", article)


if __name__ == "__main__":
    main()
