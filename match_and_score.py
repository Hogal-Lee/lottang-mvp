
import pandas as pd
import re
from collections import defaultdict

# B안 점수 정책
def compute_score(win1_cnt, win2_cnt, last_years):
    base = win1_cnt * 10 + win2_cnt * 3
    # 최근성 보정: 단순히 '최근 N년' 입력으로 보정(정확 날짜 매핑 전 임시)
    if last_years is None:
        factor = 1.0
    elif last_years <= 1:
        factor = 1.2
    elif last_years <= 3:
        factor = 1.1
    elif last_years <= 5:
        factor = 1.0
    else:
        factor = 0.9
    return round(base * factor, 2)

def normalize(s):
    s = str(s)
    s = re.sub(r"\s+", "", s)
    s = s.replace("·","").replace("-","")
    return s

# 입력
wins = pd.read_csv("data/winners_raw.csv")  # draw_no,rank,store_name,address_full,pick_type,source
try:
    stores = pd.read_csv("data/stores_raw.csv")  # store_name,address_full,tel,sell_type,source
except FileNotFoundError:
    stores = pd.DataFrame(columns=["store_name","address_full","tel","sell_type","source"])

# 키 만들기(초간단)
wins["key"] = wins["store_name"].map(normalize) + "|" + wins["address_full"].map(normalize)
if not stores.empty:
    stores["key"] = stores["store_name"].map(normalize) + "|" + stores["address_full"].map(normalize)

# 승수 집계
agg = wins.assign(win1=(wins["rank"]==1).astype(int),
                  win2=(wins["rank"]==2).astype(int)) \
          .groupby("key", as_index=False).agg(win1_cnt=("win1","sum"),
                                             win2_cnt=("win2","sum"),
                                             sample_addr=("address_full","first"),
                                             sample_name=("store_name","first"))

# 최근성: 회차→연도로 임시 환산(대략 주 1회 기준, 52회≈1년) — 추후 정확 날짜로 교체 가능
max_draw = wins["draw_no"].max()
agg["last_win_draw"] = wins.groupby("key")["draw_no"].max().values
agg["years_since"] = ((max_draw - agg["last_win_draw"]) / 52).round(1)

agg["score"] = agg.apply(lambda r: compute_score(r["win1_cnt"], r["win2_cnt"], r["years_since"]), axis=1)

# 스토어 메타 붙이기(있을 때만)
if not stores.empty:
    meta = stores.drop_duplicates("key")[["key","store_name","address_full","tel","sell_type"]]
    out = agg.merge(meta, on="key", how="left")
else:
    out = agg.rename(columns={"sample_name":"store_name","sample_addr":"address_full"})
    out["tel"] = ""
    out["sell_type"] = ""

# 주소 분리(아주 단순)
def split_addr(addr):
    m = re.match(r'^([^ ]+)\s+([^ ]+)\s+([^ ]+)', str(addr))
    if m: return pd.Series({"sido":m.group(1),"sigungu":m.group(2),"dong":m.group(3)})
    return pd.Series({"sido":"","sigungu":"","dong":""})

out = pd.concat([out, out["address_full"].apply(split_addr)], axis=1)

out = out[["store_name","address_full","sido","sigungu","dong","tel","sell_type",
           "win1_cnt","win2_cnt","years_since","score"]].sort_values("score", ascending=False)

out.to_csv("data/lottang_stores_scored.csv", index=False, encoding="utf-8")
print("OK -> data/lottang_stores_scored.csv")
