#!/usr/bin/env python3
"""Instagram new-comment alert -> Telegram. New file only; touches nothing else.
Env: IG_TOKEN (required), TELEGRAM_TOKEN, TELEGRAM_CHAT_ID.
State: seen_ig_comments.json (comment ids already reported)."""
import json, os, sys, urllib.parse, urllib.request

API = "https://graph.instagram.com/v21.0"
STATE = "seen_ig_comments.json"
TOKEN = os.environ["IG_TOKEN"]
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def q(path, **params):
    params["access_token"] = TOKEN
    return f"{API}/{path}?{urllib.parse.urlencode(params)}"


def telegram(text):
    if not (TG_TOKEN and TG_CHAT):
        print("Telegram secrets missing; printing instead:\n" + text)
        return
    data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=30).read()


def main():
    first_run = not os.path.exists(STATE)
    seen = set(json.load(open(STATE))) if not first_run else set()
    media = get(q("me/media", fields="id,permalink,caption,timestamp", limit=15)).get("data", [])
    new = []
    for m in media:
        comments = get(q(f"{m['id']}/comments", fields="id,text,username,timestamp", limit=50)).get("data", [])
        for c in comments:
            if c["id"] not in seen:
                new.append((m, c))
                seen.add(c["id"])
    if first_run:
        print(f"First run: recorded {len(seen)} existing comments, no alerts sent.")
    else:
        for m, c in new:
            telegram(f"💬 تعليق جديد على إنستغرام\nمن: @{c.get('username','?')}\n{c.get('text','')}\n{m.get('permalink','')}")
        print(f"{len(new)} new comment(s) reported.")
    json.dump(sorted(seen), open(STATE, "w"))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
