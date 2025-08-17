# geocode_kakao.py (교체용)
import os, time, random, csv, sys
import requests
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# .env 로컬 개발용 환경변수 로드
load_dotenv()

# ✅ B안: 둘 중 아무 이름이나 지원 (실수 방지)
# - GitHub Actions Secrets: KAKAO_REST_API_KEY 권장
# - 혹시 다른 이름(KAKAO_REST_KEY)으로 저장해도 동작
REST_KEY = os.getenv("KAKAO_REST_API_KEY") or os.getenv("KAKAO_REST_KEY")
if not REST_KEY:
    raise SystemExit("Kakao REST key not found. Set KAKAO_REST_API_KEY (or KAKAO_REST_KEY) in environment/.env")

HEADERS = {"Authorization": f"KakaoAK {REST_KEY}"}
API_ADDR = "https://dapi.kakao.com/v2/local/search/address.json"
API_KEYW = "https://dapi.kakao.com/v2/local/search/keyword.json"

SRC = "data/lottang_stores_scored.csv"
DST = "data/lottang_stores_geo.csv"
SAVE_EVERY = 100   # 행 100개 처리할 때마다 저장

def try_addr(query):
    r = requests.get(API_ADDR, headers=HEADERS, params={"query": query}, timeout=12)
    r.raise_for_status()
    docs = r.json().get("documents", [])
    if docs:
        d = docs[0]
        return d.get("y"), d.get("x")  # lat, lng
    return "", ""

def try_keyword(query):
    r = requests.get(API_KEYW, headers=HEADERS, params={"query": query}, timeout=12)
    r.raise_for_status()
    docs = r.json().get("documents", [])
    if docs:
        d = docs[0]
        return d.get("y"), d.get("x")
    return "", ""

def main():
    os.makedirs("data", exist_ok=True)
    df = pd.read_csv(SRC)

    # 재개 지원: 기존 결과 읽기(캐시)
    cache = {}
    if os.path.exists(DST):
        try:
            old = pd.read_csv(DST)
            for _, row in old.iterrows():
                key = str(row["address_full"])
                cache[key] = (row.get("lat",""), row.get("lng",""))
            print(f"[resume] loaded {len(cache)} cached rows from existing geo file")
        except Exception as e:
            print("[resume] skip loading:", e)

    out_rows = []
    processed = 0

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Geocoding"):
        addr = str(row["address_full"])
        lat = lng = ""

        # 캐시 사용
        if addr in cache and cache[addr][0] and cache[addr][1]:
            lat, lng = cache[addr]
        else:
            # 주소 검색 1차
            for attempt in range(4):
                try:
                    lat, lng = try_addr(addr)
                    if lat and lng:
                        break
                    # 주소가 안 잡히면 가게명+주소로 키워드 검색 2차
                    q = f'{row["store_name"]} {addr}'
                    lat, lng = try_keyword(q)
                    if lat and lng:
                        break
                except requests.HTTPError:
                    # 429 등 → 백오프
                    sleep = 1.5 + attempt * 1.5
                    time.sleep(sleep)
                except Exception:
                    pass
                time.sleep(random.uniform(0.35, 0.7))

        out = row.to_dict()
        out["lat"], out["lng"] = lat, lng
        out_rows.append(out)
        processed += 1

        # 주기 저장
        if processed % SAVE_EVERY == 0:
            pd.DataFrame(out_rows).to_csv(DST, index=False, encoding="utf-8")
            print(f"[autosave] wrote {processed} rows")

    # 최종 저장
    pd.DataFrame(out_rows).to_csv(DST, index=False, encoding="utf-8")
    print("OK ->", DST)

if __name__ == "__main__":
    main()