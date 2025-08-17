
# 로땅 MVP (lottang-mvp)

모바일 웹에서 **로또 명당(1·2등 배출점)**을 지도에 보여주는 MVP입니다.  
데이터는 동행복권 사이트의 공개 페이지를 사람이 보는 속도로 요청하여 **표 데이터를 파싱**해 만듭니다.  
**공식 API가 아니므로 요청을 느리게** 보내고, 과도한 트래픽을 발생시키지 마세요. 출처 표기를 지켜주세요.

---

## 빠른 시작(개발 초보용)

### 0) 필수 설치
- Python 3.9+
- `pip install -r requirements.txt`

### 1) 비밀키 설정
- `.env.example`을 복사해서 `.env`로 만들고, 카카오 키를 넣어주세요.
  - `KAKAO_REST_API_KEY=...`
  - `KAKAO_JS_KEY=...`
- **주의: .env는 깃허브에 올리지 마세요!** (.gitignore에 이미 제외되어 있음)

### 2) 당첨 판매점(명당) 수집
- `python scraper_winners.py --start 1 --end 1184`

결과: `data/winners_raw.csv`

### 3) 판매점 전체 목록(주소록) 수집
- 한 번만 DevTools로 시/군/구 옵션을 모아 `regions.json`에 채워 넣으세요.
- `python scraper_stores.py`

결과: `data/stores_raw.csv`

### 4) 매칭 & 점수 계산
- `python match_and_score.py`

결과: `data/lottang_stores_scored.csv`

### 5) 좌표 붙이기(지오코딩)
- `python geocode_kakao.py`

결과: `data/lottang_stores_geo.csv`

### 6) 지도 실행(정적 웹)
- `web/index.html`을 브라우저로 열면 됩니다. (로컬 파일 열기)
- 만약 CSV가 크면, 간단한 서버로 열어주세요: `python -m http.server -d web 5500`

---

## 파일 개요

- `scraper_winners.py` : 회차별 1·2등 배출점 테이블을 1회~N회까지 크롤링
- `scraper_stores.py`  : 지역별 로또6/45 판매점 전체 목록 크롤링 (regions.json 필요)
- `match_and_score.py` : 주소/상호로 매칭, 1/2등 횟수 집계, **B안 점수** 계산
- `geocode_kakao.py`   : 카카오 로컬 REST API로 주소→좌표
- `web/index.html` + `web/app.js` + `web/style.css` : 카카오 지도 JS로 모바일 지도 렌더링

---

## 법무/안전
- 동행복권은 공개 API가 아닙니다. **사람이 사용하는 속도**로 요청하고, 과도한 병렬 요청 금지.
- **출처 표기**: 데이터 출처 `동행복권`을 명시하세요.
- **비밀키 노출 금지**: .env를 깃에 올리지 마세요.

행운을 빕니다 🍀
