import json
import os
import re
import time

import requests
from playwright.sync_api import sync_playwright

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
URL = os.environ.get("FIRSTCRY_URL", "https://www.firstcry.com/search.aspx?q=hot+wheels")
DATA_FILE = os.environ.get("FIRSTCRY_STATE", "firstcry_seen.json")

REAL_BRANDS = [
    "ferrari", "porsche", "mazda", "honda", "toyota", "nissan", "bmw",
    "mercedes", "audi", "volkswagen", "vw", "ford", "chevrolet", "chevy",
    "lamborghini", "pagani", "bugatti", "mclaren", "aston martin",
    "alfa romeo", "subaru", "mitsubishi", "dodge", "jeep", "pontiac",
    "volvo", "renault", "bentley", "koenigsegg", "jaguar", "land rover",
    "maserati", "lexus", "mini",
]

FANTASY_KEYWORDS = [
    "twin mill", "bone shaker", "street wiener", "pixel shaker",
    "madfast", "ain't fare", "quick bite", "power rocket",
    "layin low", "driftn break", "cruise bruiser",
    "el viento", "feline lucky", "shark", "dragon", "skull",
    "rodger dodger",
]

BIKE_KEYWORDS = [
    "bike", "motorcycle", "moto", "vfr", "ducati",
    "kawasaki", "yamaha", "triumph", "harley", "motocompo",
]


def contains_any(text: str, words: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def is_valid_product(title: str) -> bool:
    t = title.lower()
    if "hot wheels" not in t and "hotwheels" not in t:
        return False
    if contains_any(t, FANTASY_KEYWORDS) or contains_any(t, BIKE_KEYWORDS):
        return False
    return contains_any(t, REAL_BRANDS)


def send_telegram(message: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram credentials missing.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message},
            timeout=15,
        )
        time.sleep(1)
    except requests.RequestException as error:
        print("Telegram error:", error)


def load_seen() -> dict:
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_seen(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def check() -> None:
    seen = load_seen()
    first_run = len(seen) == 0
    new_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 1000},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto(URL, timeout=60000)
        page.wait_for_timeout(8000)

        for _ in range(10):
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(1500)

        links = page.query_selector_all("a[href][title]")
        print("Links with titles found:", len(links))
        if not links:
            browser.close()
            raise RuntimeError("No product links found; page may be blocked.")

        matched = 0
        for a in links:
            title = (a.get_attribute("title") or "").strip()
            href = a.get_attribute("href") or ""
            if not title or not href or not is_valid_product(title):
                continue
            if href.startswith("/"):
                href = "https://www.firstcry.com" + href
            href = href.split("?")[0].split("#")[0]
            matched += 1
            if href not in seen:
                seen[href] = title
                if not first_run:
                    new_items.append(f"{title}\n{href}")

        browser.close()

    print(f"Matching products on page: {matched}")
    save_seen(seen)

    if first_run:
        print("Baseline saved, no alerts sent.")
        send_telegram(f"FirstCry bot ready. Baseline saved: {len(seen)} matching Hot Wheels.")
    elif new_items:
        for i in range(0, len(new_items), 5):
            send_telegram("🆕 NEW Hot Wheels on FirstCry:\n\n" + "\n\n".join(new_items[i:i + 5]))
        print(f"Sent {len(new_items)} new alerts")
    else:
        print("No new items found")


if __name__ == "__main__":
    check()
