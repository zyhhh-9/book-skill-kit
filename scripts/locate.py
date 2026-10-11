#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""书籍全文定位脚本（零第三方依赖，仅标准库）

用法：
  python locate.py --data book.txt --query "关键词 另一关键词"     # 检索：返回命中最多的章节 + 上下文锚点
  python locate.py --data book.txt --query "关键词" --top 3
  python locate.py --data book.txt --anchor S018                  # 取某一分片全文（默认截断 12000 字）
  python locate.py --data book.txt --list                         # 列出全部篇目
  python locate.py --self-test                                    # 自检

锚点定义：`S{分片序号}` 对应资料库文件中 `===== [序号] 标识 =====` 段，
可直接反查文本位置；引用原文时单条不得超过 100 字（见 SKILL.md 硬约束）。
"""
import argparse
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "assets", "book.txt")
SEC_RE = re.compile(r"===== \[(\d+)\] ([^ ]+) =====")


def load_sections(path):
    if not os.path.isfile(path):
        return []
    raw = open(path, encoding="utf-8").read()
    parts = SEC_RE.split(raw)
    secs = []
    for i in range(1, len(parts), 3):
        idx = int(parts[i])
        body = parts[i + 2]
        secs.append({"idx": idx, "href": parts[i + 1], "body": body})
    return secs


def title_of(body):
    """取分片标题：首行为文档/书名抬头，其后的第一个非空行为篇名。"""
    lines = [x.strip() for x in body.splitlines() if x.strip()]
    if len(lines) > 1:
        return re.sub(r"[（(].*$", "", lines[1]).strip() or lines[1]
    return re.sub(r"[（(].*$", "", lines[0]).strip() if lines else "(未识别)"


def norm(s):
    return re.sub(r"\s", "", s)


def search(secs, query, top=5, ctx=80):
    kws = [k for k in re.split(r"[\s,，、]+", query.strip()) if k]
    if not kws:
        return []
    hits = []
    for s in secs:
        body = s["body"]
        nb = norm(body)
        score = sum(nb.count(norm(k)) for k in kws)
        if score <= 0:
            continue
        # 取最佳上下文窗口
        win = []
        for k in kws:
            p = body.find(k)
            while p != -1 and len(win) < 4:
                a = max(0, p - ctx)
                b = min(len(body), p + len(k) + ctx)
                win.append(body[a:b].replace("\n", " "))
                p = body.find(k, p + 1)
        hits.append((score, s, win[:3]))
    hits.sort(key=lambda x: -x[0])
    return hits[:top]


def main():
    ap = argparse.ArgumentParser(description="书籍全文定位")
    ap.add_argument("--query", help="检索关键词（空格分多词，任一命中计分）")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--anchor", help="取分片全文，如 S018 或 18")
    ap.add_argument("--limit", type=int, default=12000, help="--anchor 输出字数上限")
    ap.add_argument("--data", default=DATA, help="资料库文件路径")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    secs = load_sections(a.data)
    if not secs:
        print("[ERROR] 找不到资料库：%s" % a.data)
        return 2

    if a.list:
        for s in secs:
            print("S%03d | %s | %d字" % (s["idx"], title_of(s["body"]), len(norm(s["body"]))))
        return 0

    if a.anchor:
        m = re.search(r"(\d+)", a.anchor)
        if not m:
            print("[ERROR] 锚点格式应为 S018 或 18")
            return 2
        idx = int(m.group(1))
        for s in secs:
            if s["idx"] == idx:
                body = s["body"]
                print("锚点 S%03d | %s | 全篇 %d 字" % (idx, title_of(body), len(norm(body))))
                print("-" * 70)
                print(body[: a.limit])
                if len(body) > a.limit:
                    print("\n...[已截断，共 %d 字，可用更大 --limit]" % len(body))
                return 0
        print("[ERROR] 未找到锚点 S%03d" % idx)
        return 2

    if a.query:
        hits = search(secs, a.query, a.top)
        if not hits:
            print("未命中任何篇目。可换更通用的词，或先 --list 看篇名。")
            return 1
        print("检索「%s」命中 %d 篇（按相关度）：\n" % (a.query, len(hits)))
        for score, s, win in hits:
            print("▶ S%03d 《%s》 相关度=%d" % (s["idx"], title_of(s["body"]), score))
            for w in win:
                print("    …%s…" % w)
            print()
        print("下一步：用 --anchor S<序号> 取该篇全文再精读作答。")
        return 0

    ap.print_help()
    return 0


def self_test():
    ok = total = 0

    def chk(d, c):
        nonlocal ok, total
        total += 1
        ok += 1 if c else 0
        print("  %s %s" % ("[PASS]" if c else "[FAIL]", d))

    import tempfile
    tmp = tempfile.mkdtemp(prefix="mxq_")
    p = os.path.join(tmp, "t.txt")
    # 自检语料为自造占位文本，刻意不含任何受版权保护的内容
    open(p, "w", encoding="utf-8").write(
        "===== [001] a.html =====\n示例文档\n甲篇\n（某年某月）\n这是自检用的样例段落甲，含检索关键词「苹果」。\n"
        "===== [002] b.html =====\n示例文档\n乙篇\n（某年某月）\n这是自检用的样例段落乙，含检索关键词「香蕉」与「梨」。\n")
    secs = load_sections(p)
    chk("分片解析数量=2", len(secs) == 2)
    chk("标题识别", title_of(secs[1]["body"]) == "乙篇")
    chk("检索命中且排序正确", search(secs, "苹果")[0][1]["idx"] == 1)
    chk("多词检索", len(search(secs, "香蕉 梨")) == 1)
    chk("无命中返回空", search(secs, "量子纠缠") == [])
    chk("锚点解析", re.search(r"(\d+)", "S002").group(1) == "002")
    print("locate self-test：%d/%d 通过" % (ok, total))
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
