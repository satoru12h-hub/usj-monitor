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
                print(f"  input type={el.get_attribute('type')} name={el.get_attribute('name')} id={el.get_attribute('id')} placeholder={el.get_attribute('placeholder')}")
            all_btns = page.query_selector_all('button[type="submit"]')
            print(f"[debug] submit button数: {len(all_btns)}")
            for el in all_btns:
                print(f"  button id={el.get_attribute('id')} disabled={el.get_attribute('disabled')} class={el.get_attribute('class')}")
        except Exception as e:
            print(f"[debug] 構造出力失敗: {e}")

        # パスワードフィールドを含むフォーム = ログインフォーム を特定
        login_form = page.locator('form:has(input[type="password"])')
        if login_form.count() > 0:
            print("ログインフォームを発見（パスワードフィールドで特定）")
            # ログインフォーム内のメール/テキスト入力を探す
            email_filled = False
            for sel in ['input[type="email"]', 'input[type="text"]', 'input:not([type="password"])']:
                try:
                    field = login_form.locator(sel).first
                    if field.count() > 0:
                        field.fill(LIBECITY_EMAIL)
                        print(f"メール入力成功（ログインフォーム内）: {sel}")
                        email_filled = True
                        break
                except Exception:
                    continue
            if not email_filled:
                print("警告: ログインフォーム内にメールフィールドが見つかりません")

            login_form.locator('input[type="password"]').fill(LIBECITY_PASSWORD)
            print("パスワード入力成功")
            login_form.locator('button[type="submit"]').click(timeout=30000)
        else:
            print("警告: ログインフォームが見つかりません。フォールバック処理を試みます")
            print(page.content()[:3000])
            # フォールバック
            page.fill('input[type="password"]', LIBECITY_PASSWORD)
            page.click('button[type="submit"]')

        page.wait_for_timeout(5000)
        print(f"ログイン後URL: {page.url}")

        # 検索ページへアクセス
        print("検索ページへアクセス...")
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
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
    main()
