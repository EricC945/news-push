#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端每日新闻自动推送 - GitHub Actions 定时执行
功能：抓取多源新闻 → 筛选科技/AI、国内、军事/国际 → 通过 Server酱 推送微信
无需本地电脑运行，完全云端执行。

运行方式：python cloud_news_push.py
依赖：requests（通过 pip install -r requirements.txt 安装）
"""
import json
import time
import urllib.request
import urllib.parse

# ============ 配置 ============
import os
# 优先从环境变量读取（GitHub Secrets），本地测试用默认值
SERVERCHAN_KEY = os.environ.get("SERVERCHAN_KEY", "SCT429252TbEkhrU0SKxs6RaGHN2348rHf")
SERVERCHAN_URL = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
TIMEOUT = 15

# ============ 新闻源抓取 ============
def fetch_weibo():
    """微博热搜"""
    try:
        url = "https://weibo.com/ajax/side/hotSearch"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://weibo.com/",
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("data", {}).get("realtime", [])[:15]
        results = []
        for it in items:
            word = it.get("word", "")
            if word:
                results.append({
                    "title": word,
                    "heat": it.get("num", 0),
                    "url": f"https://s.weibo.com/weibo?q={urllib.parse.quote(word)}",
                })
        return results
    except Exception as e:
        print(f"[weibo] fetch failed: {e}")
        return []

def fetch_36kr():
    """36氪快讯"""
    try:
        url = "https://gateway.36kr.com/api/mis/nav/home/nav/rank/hot"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("data", {}).get("itemList", [])[:14]
        results = []
        for it in items:
            title = it.get("title", "")
            if title:
                results.append({
                    "title": title,
                    "url": f"https://www.36kr.com/p/{it.get('itemId', '')}",
                })
        return results
    except Exception as e:
        print(f"[36kr] fetch failed: {e}")
        return []

def fetch_tencent():
    """腾讯新闻"""
    try:
        url = "https://r.inews.qq.com/gw/event/hot_ranking_list?page_size=15"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("idlist", [{}])[0].get("newslist", [])[:14]
        results = []
        for it in items:
            title = it.get("title", "")
            if title:
                results.append({
                    "title": title,
                    "desc": it.get("abstract", ""),
                    "url": it.get("url", ""),
                })
        return results
    except Exception as e:
        print(f"[tencent] fetch failed: {e}")
        return []

def fetch_wallstreetcn():
    """华尔街见闻快讯"""
    try:
        url = "https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&limit=14"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("data", {}).get("items", [])[:14]
        results = []
        for it in items:
            title = it.get("title") or it.get("content_text") or ""
            title = title.strip()
            if title and len(title) > 6:
                results.append({
                    "title": title[:80],
                    "desc": (it.get("content_text") or "")[:150],
                })
        return results
    except Exception as e:
        print(f"[wallstreet] fetch failed: {e}")
        return []

# ============ 新闻整理 ============
def compile_news():
    """汇总所有来源并按板块整理"""
    weibo = fetch_weibo()
    kr36 = fetch_36kr()
    tencent = fetch_tencent()
    wall = fetch_wallstreetcn()

    # 按关键词分类
    tech_kw = ["AI", "人工智能", "大模型", "芯片", "英伟达", "OpenAI", "苹果", "华为",
               "小米", "机器人", "算力", "GPT", "DeepSeek", "智能", "科技", "卫星",
               "火箭", "手机", "汽车", "半导体", "数据", "元宇宙", "自动驾驶", "互联网"]
    dom_kw = ["中国", "国务院", "央行", "发改委", "统计局", "财政部", "政策", "医保",
             "养老金", "楼市", "房价", "就业", "高考", "亚运", "全运会", "国庆", "中秋"]
    intl_kw = ["美国", "特朗普", "伊朗", "俄罗斯", "乌克兰", "以色列", "欧盟", "北约",
              "日本", "朝鲜", "南海", "台海", "中东", "俄乌", "联合国", "欧盟", "巴基斯坦"]

    def classify(item):
        t = item.get("title", "")
        for kw in tech_kw:
            if kw.lower() in t.lower():
                return "tech"
        for kw in dom_kw:
            if kw in t:
                return "domestic"
        for kw in intl_kw:
            if kw in t:
                return "intl"
        return "other"

    groups = {"tech": [], "domestic": [], "intl": []}
    for src_items in [weibo, kr36, tencent, wall]:
        for it in src_items:
            cat = classify(it)
            if cat in groups and len(groups[cat]) < 8:
                groups[cat].append(it)

    # 补足各板块
    for it in weibo + kr36 + tencent + wall:
        if len(groups["tech"]) < 8 and classify(it) == "tech":
            pass
        if len(groups["domestic"]) < 8 and classify(it) == "domestic":
            pass
        if len(groups["intl"]) < 8 and classify(it) == "intl":
            pass

    # 如果某板块不足，从其他板块补充
    flat = weibo + kr36 + tencent + wall
    seen = set()
    for cat in ["tech", "domestic", "intl"]:
        for it in flat:
            if len(groups[cat]) >= 8:
                break
            key = it.get("title", "")
            if key in seen:
                continue
            seen.add(key)
            groups[cat].append(it)

    return groups

def build_markdown(groups):
    """构建推送 Markdown 内容"""
    now = time.strftime("%Y年%m月%d日 %A")
    md = [f"# 📰 每日新闻早报 | {now}", ""]

    if groups.get("tech"):
        md.append("## 🤖 科技 / AI")
        for i, it in enumerate(groups["tech"][:8], 1):
            md.append(f"**{i}. {it.get('title','')}**")
            desc = it.get("desc") or ""
            if desc:
                md.append(f"> {desc[:120]}")
        md.append("")

    if groups.get("domestic"):
        md.append("## 🇨🇳 国内要闻")
        for i, it in enumerate(groups["domestic"][:8], 1):
            md.append(f"**{i}. {it.get('title','')}**")
            desc = it.get("desc") or ""
            if desc:
                md.append(f"> {desc[:120]}")
        md.append("")

    if groups.get("intl"):
        md.append("## 🌍 军事 / 国际")
        for i, it in enumerate(groups["intl"][:8], 1):
            md.append(f"**{i}. {it.get('title','')}**")
            desc = it.get("desc") or ""
            if desc:
                md.append(f"> {desc[:120]}")
        md.append("")

    md.append("---")
    md.append("*由 TeleAgent 云端自动推送*")
    return "\n".join(md)

# ============ 推送 ============
def push(title, content):
    """通过 Server酱推送微信"""
    data = urllib.parse.urlencode({
        "title": title,
        "desp": content,
    }).encode("utf-8")
    req = urllib.request.Request(SERVERCHAN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if result.get("code") == 0:
            print(f"[OK] push success, pushid={result.get('data', {}).get('pushid')}")
            return True
        else:
            print(f"[FAIL] push error: {result}")
            return False
    except Exception as e:
        print(f"[FAIL] push exception: {e}")
        return False

def main():
    import urllib.parse
    from datetime import datetime
    print("开始抓取新闻...")
    groups = compile_news()
    md = build_markdown(groups)
    title = f"📰 每日早报 {datetime.now().strftime('%m月%d日')}"
    print(f"新闻整理完成，推送中...（{sum(len(v) for v in groups.values())}条）")
    ok = push(title, md)
    if ok:
        print("DONE")
    else:
        print("PUSH_FAILED")
        raise SystemExit(1)

if __name__ == "__main__":
    main()