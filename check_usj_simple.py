#!/usr/bin/env python3
"""
USJ出品チェック（軽量版）
- Playwright不要・ブラウザ不要
- urllib.requestのみ使用（Python標準ライブラリのみ）
- GitHub Actionsで使用（約30秒で完了）
"""

import re
import json
import os
import base64
import urllib.request
import urllib.error
from datetime import datetime

SEARCH_URL = "https://furima.libecity.com/search?listing_type=normal&sort_key=released_at&keyword=USJ"
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")
SEEN_IDS_FILE = "seen_ids.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def get_listings():
    """検索ページから商品IDを取得（ログイン不要）"""
    req = urllib.request.Request(SEARCH_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    ids = re.findall(r'/products/(\d+)', html)
    return list(dict.fromkeys(ids))  # 重複除去・順序保持


def load_seen_ids():
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids):
    with open(SEEN_IDS_FILE, "w") as f:
        json.dump(sorted(list(ids)), f, ensure_ascii=False, indent=2)


def send_line_message(text):
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print(f"  [LINE未設定] {text}")
        return False
    try:
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
        }
        data = json.dumps({
            "to": LINE_USER_ID,
            "messages": [{"type": "text", "text": text}]
        }).encode()
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  LINE通知失敗: {e}")
        return False


def main():
    print("USJ出品チェック開始（軽量版）...")
    print(f"監視URL: {SEARCH_URL}")

    product_ids = get_listings()
    print(f"取得件数: {len(product_ids)}")

    seen_ids = load_seen_ids()
    new_ids = [pid for pid in product_ids if pid not in seen_ids]

    if new_ids:
        print(f"新着: {len(new_ids)}件")
        for pid in new_ids:
            url = f"https://furima.libecity.com/products/{pid}"
            msg = f"🎡 USJ新着出品！\n{url}"
            ok = send_line_message(msg)
            print(f"  通知{'✅' if ok else '❌'}: {pid}")
    else:
        print("新着なし")

    updated_ids = seen_ids | set(product_ids)
    save_seen_ids(updated_ids)
    print("完了")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"エラー: {e}")
        import sys
        sys.exit(0)  # 失敗メール防止のため正常終了
