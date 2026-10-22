#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""磨轴 —— 从摩擦里磨出轴。

一句话：**轴是给下一次立的约定，不是对过去的总结。**

零依赖、单文件、不联网。数据就一个 axes.json，放在脚本旁边或 --db 指定。
只装这一个文件也能跑，不需要任何别的插件、记忆系统或打扫脚本。

用法：
  axis.py add "我把 A 当成 X，其实是 Y" --scene 场景 --root "抽象动作" [--should "本该"]
  axis.py scan                     # 扫族群：哪个 root 攒够了，可以提轴
  axis.py promote 名字 --axis "..." --breaks "..." --premise "..." \
                   --cand "另一个解释" --why "为什么不是它"
  axis.py list                     # 规则位 + 观察位
  axis.py check                    # 动手前看这个
  axis.py confirm 轴ID             # 记一次「这条这次真的用上了」
  axis.py decay                    # 长期没被确认的，自动降到观察位
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "axes.json")

# 门槛：同根 + 不同场景 + 至少 3 条
MIN_SAMPLES = 3
# 规则位上限：超了必须合并或降级，否则「守得极少」只是口号
MAX_RULE = 5
# 多久没被确认就降到观察位
DECAY_DAYS = 90


def now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def load(path):
    if not os.path.exists(path):
        return {"version": 1, "frictions": [], "axes": []}
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    d.setdefault("frictions", [])
    d.setdefault("axes", [])
    return d


def save(path, d):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def next_axis_id(d):
    n = 0
    for a in d["axes"]:
        try:
            n = max(n, int(str(a.get("id", "A0")).lstrip("A")))
        except ValueError:
            pass
    return "A%d" % (n + 1)


def age_days(ts):
    if not ts:
        return None
    try:
        return (datetime.now() - datetime.strptime(ts[:16], "%Y-%m-%dT%H:%M")).days
    except ValueError:
        return None


# ---------------------------------------------------------------- add

def cmd_add(a):
    d = load(a.db)
    fid = datetime.now().strftime("%Y%m%d-%H%M%S") + "-%03d" % (datetime.now().microsecond // 1000)
    d["frictions"].append({
        "id": fid,
        "at": now(),
        "did": a.what,                      # 我做了什么（行为，可核）
        "scene": a.scene,
        "root": a.root,                     # 抽象动作：把「我默认用了什么」抽成一句
        "should": a.should or "",
        "note": a.note or "",
    })
    save(a.db, d)
    same = [f for f in d["frictions"] if f["root"] == a.root]
    scenes = {f["scene"] for f in same}
    print("记下了：%s" % fid)
    print("  同根「%s」现在 %d 条 / %d 个场景" % (a.root, len(same), len(scenes)))
    if len(same) >= MIN_SAMPLES and len(scenes) >= MIN_SAMPLES:
        print("  ✅ 够门槛了（同根 + 不同场景 + ≥%d 条）→ axis.py scan 看候选" % MIN_SAMPLES)
    else:
        need = MIN_SAMPLES - min(len(same), len(scenes))
        print("  ⏳ 还差 %d 步（要同根、且来自不同场景）" % max(need, 0))
    return 0


# ---------------------------------------------------------------- scan

def cmd_scan(a):
    d = load(a.db)
    groups = {}
    for f in d["frictions"]:
        groups.setdefault(f["root"], []).append(f)
    if not groups:
        print("还没有摩擦记录。axis.py add 记第一笔。")
        return 0
    ready, waiting = [], []
    for root, items in groups.items():
        scenes = {i["scene"] for i in items}
        row = (root, len(items), len(scenes), items)
        if len(items) >= MIN_SAMPLES and len(scenes) >= MIN_SAMPLES:
            ready.append(row)
        else:
            waiting.append(row)
    if ready:
        print("✅ 够门槛、可以提轴：\n")
        for root, n, s, items in sorted(ready, key=lambda r: -r[1]):
            print("  [%d 条 / %d 场景] %s" % (n, s, root))
            for i in items[:6]:
                print("      - [%s] %s" % (i["scene"], i["did"]))
            if len(items) > 6:
                print("      ... 还有 %d 条" % (len(items) - 6))
            print("      → axis.py promote <名字> --axis ... --breaks ... --premise ...")
            print()
    if waiting:
        print("⏳ 还不够（攒着，别硬提）：\n")
        for root, n, s, items in sorted(waiting, key=lambda r: -r[1]):
            print("  [%d 条 / %d 场景] %s" % (n, s, root))
        print("\n门槛：同根 + 不同场景 + 至少 %d 条。同一个场景犯三次，只算一条样本。" % MIN_SAMPLES)
    return 0


# ---------------------------------------------------------------- promote

def cmd_promote(a):
    d = load(a.db)
    # 门槛靠代码卡，不靠自觉
    miss = []
    if not a.axis.strip():
        miss.append("--axis（一句坐标，不是答案）")
    if not a.breaks.strip():
        miss.append("--breaks（什么情况下它会失效）")
    if not a.premise.strip():
        miss.append("--premise（它靠什么前提成立）")
    if len(a.cand) < 2:
        miss.append("--cand 给两次（两根候选轴：为什么是这根、不是另一根）")
    if not a.why.strip():
        miss.append("--why（为什么不是另一根）")
    if miss:
        print("❌ 缺东西，不让过：")
        for m in miss:
            print("   - " + m)
        print("\n没失效条件的不是轴，是口号。只给一根候选等于没提炼——那是把最熟的框架改名叫轴。")
        return 2
    if a.root:
        same = [f for f in d["frictions"] if f["root"] == a.root]
        scenes = {f["scene"] for f in same}
        if len(same) < MIN_SAMPLES or len(scenes) < MIN_SAMPLES:
            print("❌ 样本不够：同根 %d 条 / %d 场景（门槛 ≥%d 条且 ≥%d 场景）"
                  % (len(same), len(scenes), MIN_SAMPLES, MIN_SAMPLES))
            print("   硬提就是拿最熟的框架顶掉观察。攒着。")
            return 2
    rules = [x for x in d["axes"] if x.get("state") == "rule"]
    if len(rules) >= MAX_RULE:
        print("❌ 规则位已满（%d / %d）。先合并或降一条：axis.py list 看现状。" % (len(rules), MAX_RULE))
        return 2
    ax = {
        "id": next_axis_id(d),
        "name": a.name,
        "axis": a.axis.strip(),
        "breaks": a.breaks.strip(),
        "premise": a.premise.strip(),
        "cands": list(a.cand),
        "why": a.why.strip(),
        "root": a.root or "",
        "state": "rule",
        "created": now(),
        "last_confirmed": now(),
        "confirmed": 1,
    }
    d["axes"].append(ax)
    save(a.db, d)
    print("✅ 提出来了：%s · %s" % (ax["id"], ax["name"]))
    print("   轴：%s" % ax["axis"])
    print("   失效条件：%s" % ax["breaks"])
    print("   前提：%s" % ax["premise"])
    print("   规则位 %d / %d" % (len(rules) + 1, MAX_RULE))
    return 0


# ---------------------------------------------------------------- list / check

def _fmt(ax):
    age = age_days(ax.get("last_confirmed"))
    agetxt = "?" if age is None else ("今天" if age == 0 else "%d 天前" % age)
    print("  %-4s %s" % (ax["id"], ax["name"]))
    print("       轴：%s" % ax["axis"])
    print("       打中它的：%s" % ax["breaks"])
    print("       前提：%s" % ax["premise"])
    print("       上次确认 %s · 已确认 %d 次" % (agetxt, ax.get("confirmed", 1)))


def cmd_list(a):
    d = load(a.db)
    rules = [x for x in d["axes"] if x.get("state") == "rule"]
    watch = [x for x in d["axes"] if x.get("state") != "rule"]
    print("规则位（%d / %d）\n" % (len(rules), MAX_RULE))
    for ax in rules:
        _fmt(ax)
        print()
    if watch:
        print("观察位（在场，但不当规则用）\n")
        for ax in watch:
            print("  %-4s %s —— %s" % (ax["id"], ax["name"], ax["axis"]))
        print()
    print("摩擦记录 %d 条" % len(d["frictions"]))
    return 0


def cmd_check(a):
    """动手前看这个。三条全读，不判命中——判「这次命中哪条」本身就是毛病。"""
    d = load(a.db)
    rules = [x for x in d["axes"] if x.get("state") == "rule"]
    if not rules:
        print("规则位是空的。没有轴的时候，唯一能靠的是「先问这是什么」。")
        return 0
    print("动手前三条全读（不判命中）：")
    for ax in rules:
        print("  %-4s %s —— %s" % (ax["id"], ax["name"], ax["axis"]))
    print("\n读完不算检查过。要留痕就写一行：这次可能碰到的是哪条、为什么。")
    return 0


# ---------------------------------------------------------------- confirm / decay

def cmd_confirm(a):
    d = load(a.db)
    for ax in d["axes"]:
        if ax["id"] == a.id:
            ax["last_confirmed"] = now()
            ax["confirmed"] = int(ax.get("confirmed", 1)) + 1
            save(a.db, d)
            print("✓ %s 确认一次（累计 %d）%s" % (ax["id"], ax["confirmed"],
                                                ("：" + a.note) if a.note else ""))
            return 0
    print("没有这个轴：" + a.id)
    return 1


def cmd_decay(a):
    d = load(a.db)
    moved = 0
    for ax in d["axes"]:
        if ax.get("state") != "rule":
            continue
        age = age_days(ax.get("last_confirmed"))
        if age is not None and age >= DECAY_DAYS:
            ax["state"] = "watch"
            ax["moved_at"] = now()
            moved += 1
            print("↓ %s %s（%d 天没被确认）→ 观察位" % (ax["id"], ax["name"], age))
    if moved:
        save(a.db, d)
        print("\n降级不是退出：它还在场，还会响。不当规则用，但仍在观察。")
    else:
        print("没有需要降级的轴。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="磨轴：从摩擦里磨出轴")
    ap.add_argument("--db", default=DEFAULT_DB, help="数据文件（默认脚本旁边的 axes.json）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("add", help="记一条摩擦")
    s.add_argument("what", help="我做了什么（行为，可核）")
    s.add_argument("--scene", required=True, help="场景（不同场景才算独立样本）")
    s.add_argument("--root", required=True, help="抽象动作：把「我默认用了什么」抽成一句")
    s.add_argument("--should", default=None, help="本该怎么做")
    s.add_argument("--note", default=None)
    s.set_defaults(fn=cmd_add)

    s = sub.add_parser("scan", help="扫族群：哪个 root 攒够了")
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("promote", help="提炼成轴（强制四件套）")
    s.add_argument("name")
    s.add_argument("--axis", required=True, help="一句坐标，不是答案")
    s.add_argument("--breaks", required=True, help="什么情况下它会失效")
    s.add_argument("--premise", required=True, help="它靠什么前提成立")
    s.add_argument("--cand", action="append", default=[], help="候选轴解释（给两次）")
    s.add_argument("--why", required=True, help="为什么不是另一根")
    s.add_argument("--root", default=None, help="绑到哪个 root（给了就验门槛）")
    s.set_defaults(fn=cmd_promote)

    s = sub.add_parser("list", help="规则位 + 观察位")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("check", help="动手前看这个")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("confirm", help="记一次确认")
    s.add_argument("id")
    s.add_argument("--note", default=None)
    s.set_defaults(fn=cmd_confirm)

    s = sub.add_parser("decay", help="长期没确认的降到观察位")
    s.set_defaults(fn=cmd_decay)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
