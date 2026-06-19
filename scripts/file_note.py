#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把整理好的一条想法/日记/复盘/灵感，按「当日 + 分类」追加进 vault。

为什么用脚本而不是让模型手写文件：归档格式（当日同分类合并、时间戳小标题、
折叠原文 callout、追加而非覆盖）是确定性的，脚本一次写对，省得每次重造、避免
覆盖已有内容或格式漂移。正文/原文用文件传入，避免多行文本在命令行里的转义问题。

用法：
  python file_note.py \
      --vault "/path/to/vault" \
      --category "生活记录" \
      --title "一句话小标题" \
      --body-file /tmp/body.md \
      [--original-file /tmp/original.txt]

成功后打印一行 JSON：{"path": ..., "count": N, "created": true/false}
"""
import argparse, os, re, json, datetime, sys


def read_file(p):
    if not p or not os.path.exists(p):
        return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read().strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--category", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--original-file", default="")
    args = ap.parse_args()

    vault = os.path.expanduser(args.vault)
    body = read_file(args.body_file)
    original = read_file(args.original_file)
    if not body:
        print(json.dumps({"error": "body 为空，未写入"}, ensure_ascii=False))
        sys.exit(1)

    folder = os.path.join(vault, args.category)
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
    block = f"\n## {hm} · {args.title}\n\n{body}{callout}\n\n---\n"

    with open(path, "a", encoding="utf-8") as f:
        if created:
            f.write(f"# {date} · {args.category}\n")
        f.write(block)

    with open(path, "r", encoding="utf-8") as f:
        count = len(re.findall(r"^## ", f.read(), re.M))

    print(json.dumps({"path": path, "count": count, "created": created},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
