import os, re, csv, sys, time, random, argparse
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm  # ★ 진행률 표시

MOBILE_BASE  = "https://m.dhlottery.co.kr/store.do"
DESKTOP_BASE = "https://www.dhlottery.co.kr/store.do"

BASE_HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}

def norm(s:str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def detect_rank(txt:str) -> str:
    t = (txt or "").replace(" ", "")
    if "1등" in t and "2등" not in t: return "1"
    if "2등" in t and "1등" not in t: return "2"
    return ""

def save_debug(tag:str, draw_no:int, html:str):
    os.makedirs("data/debug", exist_ok=True)
    path = f"data/debug/draw_{draw_no:04d}_{tag}.html"
    with open(path, "w", encoding="utf-8") as f: f.write(html)
    return path

# -------- 요청 (세션/리퍼러 유지) --------
def make_session(referer: str):
    s = requests.Session()
    s.headers.update({**BASE_HDRS, "Referer": referer})
    # ★ 워밍업: 먼저 referer URL을 GET 해서 JSESSIONID 등 쿠키를 받아온다
    try:
        s.get(referer, timeout=15)
    except Exception:
        pass
    return s

def fetch_detail_post(session:requests.Session, base:str, draw_no:int) -> str:
    params = {"method": "topStore", "pageGubun": "L645"}
    data   = {"drwNo": str(draw_no), "nowPage": "1", "schKey": "all", "schVal": ""}
    r = session.post(base, params=params, data=data, timeout=15)
    r.raise_for_status()
    return r.text

def fetch_detail_get(session:requests.Session, base:str, draw_no:int) -> str:
    params = {"method":"topStore", "pageGubun":"L645", "drwNo": str(draw_no)}
    r = session.get(base, params=params, timeout=15)
    r.raise_for_status()
    return r.text

def fetch_archive_page(session:requests.Session, base:str, now_page:int) -> str:
    params = {"method":"topStore", "pageGubun":"L645", "nowPage": str(now_page)}
    r = session.get(base, params=params, timeout=15)
    r.raise_for_status()
    return r.text

# -------- 파싱 --------
def header_index_map(table) -> dict:
    head = table.select_one("thead tr") or table.select_one("tr")
    if not head: return {}
    labels = [norm(c.get_text()) for c in head.find_all(["th","td"])]
    m = {}
    for i, lab in enumerate(labels):
        if re.fullmatch(r"(No|번호)", lab, re.I): m["no"] = i
        if re.search(r"(상호|상호명|판매점|가맹점)", lab): m["name"] = i
        if re.search(r"(소재지|주소|지번주소|도로명주소)", lab): m["addr"] = i
        if re.search(r"(구분|선택구분|번호선택|자동|수동)", lab): m["pick"] = i
    return m

def parse_table(table, draw_no:int, context_rank:str):
    rows = []
    idx = header_index_map(table)
    body_trs = table.select("tbody tr") or table.find_all("tr")[1:]
    for tr in body_trs:
        tds = [norm(td.get_text()) for td in tr.find_all("td")]
        if not tds: 
            continue
        no = store = addr = pick = ""
        if idx:
            if "no"   in idx and idx["no"]   < len(tds): no    = tds[idx["no"]]
            if "name" in idx and idx["name"] < len(tds): store = tds[idx["name"]]
            if "addr" in idx and idx["addr"] < len(tds): addr  = tds[idx["addr"]]
            if "pick" in idx and idx["pick"] < len(tds): pick  = tds[idx["pick"]]
        else:
            if len(tds) >= 3 and re.fullmatch(r"\d+", tds[0] or ""):
                no, store, addr = tds[0], tds[1], tds[2]
                pick = tds[3] if len(tds) >= 4 else ""
            elif len(tds) >= 2:
                store, addr = tds[0], tds[1]
                pick = tds[2] if len(tds) >= 3 else ""
        if store and addr:
            rows.append({
                "draw_no": draw_no,
                "no": no,
                "rank": context_rank or "",
                "store_name": store,
                "address_full": addr,
                "pick_type": pick,
                "source": "parsed",
            })
    return rows

def parse_detail(html:str, draw_no:int):
    soup = BeautifulSoup(html, "html.parser")
    out = []

    candidates = soup.select("section, article, div, h2, h3, h4, strong, .title, .tit, .stit")
    visited = set()
    for cand in candidates:
        rk = detect_rank(cand.get_text(" ", strip=True))
        if not rk: 
            continue
        nxt = cand.find_next()
        hops = 0
        while nxt and hops < 8:
            if getattr(nxt, "name", None) == "table":
                if id(nxt) not in visited:
                    out += parse_table(nxt, draw_no, rk)
                    visited.add(id(nxt))
            nxt = nxt.find_next_sibling()
            hops += 1

    if not out:
        for tbl in soup.find_all("table"):
            rk = ""
            prev = tbl.find_previous()
            hops = 0
            while prev and hops < 8 and not rk:
                try:
                    rk = detect_rank(prev.get_text(" ", strip=True))
                except Exception:
                    rk = ""
                prev = prev.find_previous()
                hops += 1
            out += parse_table(tbl, draw_no, rk)

    return out

def parse_archive_page(html:str, target_draw:int):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    heads = soup.select("h2, h3, h4, strong, .title, .tit, .stit")
    for h in heads:
        text = norm(h.get_text())
        m = re.search(r"제\s*([0-9]+)\s*회", text)
        if not m: 
            continue
        d = int(m.group(1))
        if d != target_draw: 
            continue
        rk = detect_rank(text)
        nxt = h.find_next()
        hops = 0
        while nxt and hops < 15:
            if getattr(nxt, "name", None) == "table":
                out += parse_table(nxt, target_draw, rk)
            else:
                try:
                    maybe = detect_rank(nxt.get_text(" ", strip=True))
                    if maybe: rk = maybe
                except Exception:
                    pass
            nxt = nxt.find_next_sibling()
            hops += 1
        break
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--out", type=str, default="data/winners_raw.csv")
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--archive_pages", type=int, default=120)
    ap.add_argument("--verbose", action="store_true", help="회차별 수집 결과 간단 로그 출력")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    mode = "a" if (args.append and os.path.exists(args.out)) else "w"

    with open(args.out, mode, newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=["draw_no","no","rank","store_name","address_full","pick_type","source"])
        if mode == "w":
            writer.writeheader()

        # ★ 진행률 바: 총 회차 수
        total = args.end - args.start + 1
        pbar = tqdm(total=total, desc="Scraping draws", unit="draw")

        for draw in range(args.start, args.end + 1):
            rows = []
            try:
                referer = f"{DESKTOP_BASE}?method=topStore&pageGubun=L645"
                s = make_session(referer)

                # 1) 데스크톱 POST
                html = fetch_detail_post(s, DESKTOP_BASE, draw)
                rows = parse_detail(html, draw)

                # 2) 모바일 POST
                if not rows:
                    save_debug("detail_post_desktop", draw, html)
                    s_m = make_session(referer.replace("www.", "m."))
                    html = fetch_detail_post(s_m, MOBILE_BASE, draw)
                    rows = parse_detail(html, draw)
                    if not rows:
                        save_debug("detail_post_mobile", draw, html)

                # 3) 데스크톱 GET
                if not rows:
                    html = fetch_detail_get(s, DESKTOP_BASE, draw)
                    rows = parse_detail(html, draw)
                    if not rows:
                        save_debug("detail_get_desktop", draw, html)

                # 4) 아카이브 목록 폴백
                if not rows:
                    found = False
                    for p in range(1, args.archive_pages + 1):
                        arch = fetch_archive_page(s, DESKTOP_BASE, p)
                        got = parse_archive_page(arch, draw)
                        if got:
                            rows = got
                            found = True
                            break
                        time.sleep(random.uniform(0.25, 0.5))
                    if not found:
                        save_debug("archive_last", draw, arch)
                        print(f"[WARN] draw {draw}: 0 rows (detail+archive miss)", file=sys.stderr)

                for r in rows:
                    writer.writerow(r)

                if args.verbose:
                    print(f"draw {draw}: {len(rows)} rows")

            except Exception as e:
                print(f"[ERROR] draw {draw}: {e}", file=sys.stderr)

            # 예의있는 속도
            time.sleep(random.uniform(0.6, 1.1))
            pbar.update(1)

        pbar.close()

    print(f"OK -> {args.out}")

if __name__ == "__main__":
    main()
