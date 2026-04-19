import requests
from bs4 import BeautifulSoup
import json
import os
import re

SEARCH_URL = "https://furima.libecity.com/search?listing_type=normal&sort_key=released_at&keyword=USJ"
LOGIN_URL = "https://libecity.com/login"
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")
LIBECITY_EMAIL = os.environ.get("LIBECITY_EMAIL")
LIBECITY_PASSWORD = os.environ.get("LIBECITY_PASSWORD")
SEEN_IDS_FILE = "seen_ids.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def create_session():
    session = requests.Session()
    session.headers.update(HEADERS)

    # ログインページを取得してCSRFトークンを取得
    login_page = session.get(LOGIN_URL, timeout=30)
    soup = BeautifulSoup(login_page.text, "html.parser")

    # CSRFトークンを探す
    csrf_token = None
    meta = soup.find("meta", {"name": "csrf-token"})
    if meta:
        csrf_token = meta.get("content")

    # input[name="_token"] を探す
    if not csrf_token:
        token_input = soup.find("input", {"name": "_token"})
        if token_input:
            csrf_token = token_input.get("value")

    print(f"CSRFトークン: {'取得済み' if csrf_token else '未取得'}")

    # ログイン実行
    login_data = {
        "email": LIBECITY_EMAIL,
        "password": LIBECITY_PASSWORD,
    }
    if csrf_token:
        login_data["_token"] = csrf_token

    response = session.post(LOGIN_URL, data=login_data, timeout=30, allow_redirects=True)
    print(f"ログイン結果: {response.status_code} {response.url}")

    return session


def get_listings(session):
    response = session.get(SEARCH_URL, timeout=30)
    response.raise_for_status()

    # ログインページにリダイレクトされていないか確認
    if "login" in response.url or "session" in response.url:
        print(f"警告: ログインページにリダイレクトされました: {response.url}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    products = {}
    for link in soup.find_all("a", href=True):
        href = link["href"]
        match = re.search(r"/products/(\d+)", href)
        if not match:
            continue
        product_id = match.group(1)
        if product_id in products:
            continue

        full_url = f"https://furima.libecity.com/products/{product_id}"
        title = link.get_text(strip=True) or f"商品 #{product_id}"
        products[product_id] = {"id": product_id, "url": full_url, "title": title}

    return list(products.values())


def load_seen_ids():
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids):
    with open(SEEN_IDS_FILE, "w") as f:
        json.dump(sorted(list(ids)), f, ensure_ascii=False, indent=2)


def send_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    data = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }
    response = requests.post(url, headers=headers, json=data, timeout=10)
    if response.status_code != 200:
        print(f"LINE通知失敗: {response.status_code} {response.text}")
    return response.status_code == 200


def main():
    print("USJ出品チェック開始...")

    session = create_session()
    listings = get_listings(session)
    print(f"取得件数: {len(listings)}")

    seen_ids = load_seen_ids()
    new_listings = [l for l in listings if l["id"] not in seen_ids]

    if new_listings:
        print(f"新着: {len(new_listings)}件")
        for listing in new_listings:
            title = listing["title"][:40] if listing["title"] else f"商品 #{listing['id']}"
            message = f"🎡 USJ新着出品！\n{title}\n{listing['url']}"
            send_line_message(message)
            print(f"通知送信: {listing['id']} - {title}")
    else:
        print("新着なし")

    updated_ids = seen_ids | {l["id"] for l in listings}
    save_seen_ids(updated_ids)
    print("完了")


if __name__ == "__main__":
    main()
