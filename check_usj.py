import json
import os
import re
from playwright.sync_api import sync_playwright

SEARCH_URL = "https://furima.libecity.com/search?listing_type=normal&sort_key=released_at&keyword=USJ"
LOGIN_URL = "https://libecity.com/login"
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")
LIBECITY_EMAIL = os.environ.get("LIBECITY_EMAIL")
LIBECITY_PASSWORD = os.environ.get("LIBECITY_PASSWORD")
SEEN_IDS_FILE = "seen_ids.json"


def get_listings():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # ログイン
        print("ログインページへアクセス...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        # JSレンダリング待ち
        page.wait_for_timeout(5000)
        print(f"ログインページURL: {page.url}")

        # ページ上の全input/buttonをデバッグ出力
        try:
            all_inputs = page.query_selector_all('input')
            print(f"[debug] input数: {len(all_inputs)}")
            for el in all_inputs:
                print(f"  input type={el.get_attribute('type')} id={el.get_attribute('id')} placeholder={el.get_attribute('placeholder')}")
            all_btns = page.query_selector_all('button')
            print(f"[debug] button数: {len(all_btns)}")
            for el in all_btns:
                print(f"  button id={el.get_attribute('id')} type={el.get_attribute('type')} text={el.inner_text()[:20]!r} disabled={el.get_attribute('disabled')}")
        except Exception as e:
            print(f"[debug] 構造出力失敗: {e}")

        # メールアドレスを入力（placeholder="メールアドレス"のtextフィールド）
        page.fill('input[placeholder="メールアドレス"]', LIBECITY_EMAIL)
        print("メール入力成功")

        # パスワードを入力
        page.fill('input[type="password"]', LIBECITY_PASSWORD)
        print("パスワード入力成功")

        # ログインボタンをクリック（"ログイン"テキストを持つボタンを探す）
        login_btn_selectors = [
            'button:has-text("ログイン")',
            'button:has-text("サインイン")',
            'button:has-text("signin")',
            'button:has-text("login")',
            'button[id*="login"i]',
            'button[class*="login"i]',
        ]
        btn_clicked = False
        for sel in login_btn_selectors:
            try:
                btn = page.locator(sel)
                if btn.count() > 0:
                    btn.first.click(timeout=10000)
                    print(f"ログインボタンクリック成功: {sel}")
                    btn_clicked = True
                    break
            except Exception as e:
                print(f"  ボタン試行 {sel}: {e}")
                continue

        if not btn_clicked:
            print("警告: ログインボタンが見つかりません")
            # 全ボタンの詳細を出力
            all_btns2 = page.query_selector_all('button')
            for btn in all_btns2:
                print(f"  [all] button id={btn.get_attribute('id')} text={btn.inner_text()!r}")

        page.wait_for_timeout(5000)
        print(f"ログイン後URL: {page.url}")

        # furima.libecity.comのホームへまず訪問（Cookie設定・接続確立のため）
        print("furi.libecity.comホームへアクセス...")
        try:
            page.goto("https://furima.libecity.com/", wait_until="commit", timeout=30000)
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"ホームアクセス失敗（続行）: {e}")

        # 検索ページへアクセス
        print("検索ページへアクセス...")
        page.goto(SEARCH_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(6000)
        print(f"検索URL: {page.url}")

        content = page.content()
        browser.close()

    # 商品IDを抽出
    products = {}
    for match in re.finditer(r'/products/(\d+)', content):
        product_id = match.group(1)
        if product_id not in products:
            products[product_id] = {
                "id": product_id,
                "url": f"https://furima.libecity.com/products/{product_id}",
                "title": f"商品 #{product_id}"
            }

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
    import urllib.request
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    data = json.dumps({
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status == 200
    except Exception as e:
        print(f"LINE通知失敗: {e}")
        return False


def main():
    print("USJ出品チェック開始...")
    listings = get_listings()
    print(f"取得件数: {len(listings)}")

    seen_ids = load_seen_ids()
    new_listings = [l for l in listings if l["id"] not in seen_ids]

    if new_listings:
        print(f"新着: {len(new_listings)}件")
        for listing in new_listings:
            title = listing["title"][:40]
            message = f"🎡 USJ新着出品！\n{title}\n{listing['url']}"
            success = send_line_message(message)
            print(f"通知{'成功' if success else '失敗'}: {listing['id']} - {title}")
    else:
        print("新着なし")

    updated_ids = seen_ids | {l["id"] for l in listings}
    save_seen_ids(updated_ids)
    print("完了")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"エラーが発生しました（監視を継続します）: {e}")
        import sys
        sys.exit(0)  # 失敗メール送信を防ぐため正常終了
