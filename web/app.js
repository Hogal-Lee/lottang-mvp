// app.js — responsive + bottom sheet + CSV + dynamic Kakao loader

/* -------------------- 0) util -------------------- */
const $ = (sel) => document.querySelector(sel);

// CSV 파서(간단형: 쉼표가 셀 안에 들어가지 않는 전제)
function parseCSV(text) {
  const lines = text.replace(/\r/g, "").split("\n").filter(Boolean);
  const headers = lines[0].split(",").map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const cols = line.split(",");
    const obj = {};
    headers.forEach((h, i) => (obj[h] = (cols[i] ?? "").trim()));
    return obj;
  });
}

// 다양한 키를 허용하는 안전한 getter
function pick(obj, ...keys) {
  for (const k of keys) {
    if (obj && obj[k] !== undefined && obj[k] !== null && obj[k] !== "") return obj[k];
  }
  return "";
}

/* -------------------- 1) Kakao SDK 동적 로드 -------------------- */
function loadKakaoAndInit() {
  const key =
    (window.__ENV && window.__ENV.KAKAO_JS_KEY) ||
    window.__KAKAO_JS_KEY ||
    window.KAKAO_JS_KEY ||
    "";

  if (!key) {
    alert("카카오 JS 키가 없습니다. env.js를 확인하세요.");
    return;
  }

  const s = document.createElement("script");
  // ✅ autoload=false 로드 후 kakao.maps.load(...)에서 init 호출
  s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${key}&libraries=services,clusterer&autoload=false`;
  s.async = true;
  s.onload = () => {
    if (window.kakao && kakao.maps) {
      kakao.maps.load(initMapApp);
    } else {
      alert("카카오 SDK 로드 실패");
    }
  };
  s.onerror = () => alert("카카오 SDK 로드 실패");
  document.head.appendChild(s);
}

/* -------------------- 2) 지도 앱 초기화 -------------------- */
let map, clusterer;

async function initMapApp() {
  // 지도 생성
  const mapContainer = document.getElementById("map");
  const mapOption = {
    center: new kakao.maps.LatLng(37.5665, 126.9780), // 서울시청
    level: 7,
  };
  map = new kakao.maps.Map(mapContainer, mapOption);

  // 클러스터러
  clusterer = new kakao.maps.MarkerClusterer({
    map,
    averageCenter: true,
    minLevel: 5,
  });

  // CSV 로드
  const url = "data/lottang_stores_geo.csv"; // ✅ CSV 사용
  let rows = [];
  try {
    const txt = await (await fetch(url, { cache: "no-store" })).text();
    rows = parseCSV(txt);
  } catch (e) {
    console.error(e);
    alert("데이터 로드 실패");
    return;
  }

  // lat/lng 있는 것만 마커화
  const markers = [];
  for (const row of rows) {
    const lat = Number(pick(row, "lat", "y", "latitude") || 0);
    const lng = Number(pick(row, "lng", "x", "longitude") || 0);
    if (!lat || !lng) continue;

    const marker = new kakao.maps.Marker({
      position: new kakao.maps.LatLng(lat, lng),
    });

    kakao.maps.event.addListener(marker, "click", () => __openDetailFromRow(row));
    markers.push(marker);
  }

  clusterer.addMarkers(markers);
  $("#count").textContent = String(markers.length);

  // 툴바: 버튼 id는 index.html과 동일하게 사용
  $("#apply")?.addEventListener("click", () => {
    // (필요 시 필터 로직 연결) 현재는 새로고침으로 대체 가능
    location.reload();
  });
  $("#reset")?.addEventListener("click", () => location.reload());
  $("#locate")?.addEventListener("click", () => {
    if (!navigator.geolocation) return alert("위치 정보를 사용할 수 없습니다.");
    navigator.geolocation.getCurrentPosition((pos) => {
      const { latitude, longitude } = pos.coords;
      map.setCenter(new kakao.maps.LatLng(latitude, longitude));
      map.setLevel(4);
    });
  });
}

/* -------------------- 3) 바텀시트 -------------------- */
const sheet = $("#sheet");
$("#sheetHandle")?.addEventListener("click", () => sheet.classList.remove("open"));

function buildDetailItem(row) {
  const store_name   = pick(row, "store_name", "name", "상호", "상호명");
  const address_full = pick(row, "address_full", "address", "주소");

  // 1등/2등 횟수(컬럼 명 여러 케이스 허용)
  const win1 = Number(pick(row, "win1", "wins_1", "first", "rank1", "cnt1", "count_1") || 0);
  const win2 = Number(pick(row, "win2", "wins_2", "second", "rank2", "cnt2", "count_2") || 0);
  const wins_str = `1등 ${win1}회 · 2등 ${win2}회`;

  const recent_str = pick(row, "recent", "recent_date", "last_win", "last_win_date", "latest_win_at") || "-";

  const lat = Number(pick(row, "lat", "y", "latitude") || 0);
  const lng = Number(pick(row, "lng", "x", "longitude") || 0);

  return { store_name, address_full, wins_str, recent_str, lat, lng };
}

function openDetailSheet(item) {
  $("#d_name").textContent   = item.store_name || "";
  $("#d_addr").textContent   = item.address_full || "";
  $("#d_win").textContent    = item.wins_str || "";
  $("#d_recent").textContent = item.recent_str || "";

  const navi = `https://map.kakao.com/link/map/${encodeURIComponent(item.store_name)},${item.lat},${item.lng}`;
  $("#btnNavi").setAttribute("href", navi);

  $("#btnCopy").onclick = async () => {
    try {
      await navigator.clipboard.writeText(item.address_full || "");
      alert("주소 복사 완료!");
    } catch {
      alert("복사 실패 ㅠ");
    }
  };

  sheet.classList.add("open");
}

window.__openDetailFromRow = (row) => openDetailSheet(buildDetailItem(row));

/* -------------------- 4) 부트 -------------------- */
loadKakaoAndInit();