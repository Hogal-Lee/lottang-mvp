# scraper_stores.py (replace everything with this)
import json, time, random, csv, sys, os
import requests
from bs4 import BeautifulSoup
import argparse

MOBILE_BASE = "https://m.dhlottery.co.kr/store.do"
DESKTOP_BASE = "https://www.dhlottery.co.kr/store.do"
HDRS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

def fetch_page(base: str, sido: str, gugun: str, page: int) -> str:
    # 일부 페이지는 GET, 일부는 POST처럼 동작 → 둘 다 시도
    params = {"method":"sellerInfo645", "sltSIDO": sido, "sltGUGUN": gugun, "nowPage": page}
    r = requests.get(base, params=params, headers=HDRS, timeout=15)
    r.raise_for_status()
    return r.text

def parse_table(html: str):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    # 테이블이 여러 개일 수 있어 모두 순회
    for table in soup.select("table"):
        for tr in table.select("tbody tr"):
            tds = [td.get_text(strip=True) for td in tr.select("td")]
            # 보통 [상호, 주소, 전화] 형태 (간혹 순서 다름)
            if len(tds) >= 2:
                name = tds[0]
                addr = tds[1]
                tel  = tds[2] if len(tds) >= 3 else ""
                if name and addr:
                    rows.append({"store_name":name, "address_full":addr, "tel":tel, "sell_type":"lotto6/45"})
    return rows

def save_debug(sido, gugun, page, html, tag):
    os.makedirs("data/debug", exist_ok=True)
    path = f"data/debug/stores_{sido}_{gugun}_p{page}_{tag}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

def crawl_region(writer, sido: str, gugun: str):
    page = 1
    while True:
        # 1) 모바일
        html = fetch_page(MOBILE_BASE, sido, gugun, page)
        rows = parse_table(html)

        # 2) 모바일에서 0줄이면 데스크톱 폴백
        if not rows:
            dbg1 = save_debug(sido, gugun, page, html, "mobile")
            html2 = fetch_page(DESKTOP_BASE, sido, gugun, page)
            rows = parse_table(html2)
            if not rows:
                dbg2 = save_debug(sido, gugun, page, html2, "desktop")
                # 페이지 끝났을 수도 있고, 구조가 다를 수도 있음 → 일단 종료
                print(f"[WARN] {sido} {gugun} page {page}: 0 rows (saved {dbg1}, {dbg2})", file=sys.stderr)
                break

        for r in rows:
            r["source"] = "dhLottery"
            writer.writerow(r)

        page += 1
        time.sleep(random.uniform(0.7, 1.3))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sido", type=str, help="단일 테스트용 시/도 (예: 서울)")
    ap.add_argument("--gugun", type=str, help="단일 테스트용 시/군/구 (예: 강남구)")
    args = ap.parse_args()

    os.makedirs("data", exist_ok=True)
    out = open("data/stores_raw.csv", "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(out, fieldnames=["store_name","address_full","tel","sell_type","source"])
    writer.writeheader()

    if args.sido and args.gugun:
        crawl_region(writer, args.sido, args.gugun)
        out.close()
        return

    regions = json.load(open("regions.json", "r", encoding="utf-8"))
    for sido, guguns in regions.items():
        if str(sido).startswith("_"):  # _comment 등은 스킵
            continue
        for gugun in guguns:
            try:
                crawl_region(writer, sido, gugun)
            except Exception as e:
                print(f"[ERROR] {sido} {gugun}: {e}", file=sys.stderr)

    out.close()

if __name__ == "__main__":
    main()