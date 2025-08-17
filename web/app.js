// Lottang – 상세 패널 업그레이드 (+URL/반경/공유/필터 유지)
(function () {
  const JS_KEY = window.KAKAO_JS_KEY || localStorage.getItem("KAKAO_JS_KEY") || "";
  if (!JS_KEY) {
    alert('Kakao JS 키가 없습니다.\n콘솔에 입력:\nlocalStorage.setItem("KAKAO_JS_KEY","ca26f9ae7a3d87a3526307104203c1a0"); location.reload();');
    return;
  }
  if (!window.kakao || !kakao.maps) {
    alert("Kakao SDK가 로드되지 않았습니다. index.html의 SDK 스크립트를 확인하세요.");
    return;
  }

  kakao.maps.load(init);

  // ----- 전역 상태 -----
  let map, clusterer;
  let rowsAll = [];
  let markers = [];
  let centerCircle = null;
  let currentRadiusKm = 0;
  let suppressUrlSync = false;

  // ----- 유틸 -----
  const num = (v) => { const n = parseFloat(v); return Number.isFinite(n) ? n : 0; };
  const distKm = (lat1,lng1,lat2,lng2) => {
    const R=6371,toRad=d=>d*Math.PI/180;
    const dLat=toRad(lat2-lat1), dLng=toRad(lng2-lng1);
    const a=Math.sin(dLat/2)**2 + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dLng/2)**2;
    return 2*R*Math.asin(Math.sqrt(a));
  };
  const qs = () => new URLSearchParams(location.search);
  const setQS = (obj) => {
    const p = new URLSearchParams();
    Object.entries(obj).forEach(([k,v])=>{
      if (v === null || v === undefined) return;
      if (v === "" || v === 0 || v === "0") return; // 기본값 생략
      p.set(k, String(v));
    });
    history.replaceState(null, "", (location.pathname + (p.toString()?`?${p}`:"")));
  };

  // 날짜 포맷(YYYY-MM-DD)
  function fmtDate(d){
    const y = d.getFullYear();
    const m = String(d.getMonth()+1).padStart(2,'0');
    const day = String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${day}`;
  }

  // CSV에 last_win_date(YYYY-MM-DD) 또는 last_win_draw_date 같은 필드가 있으면 사용.
  // 없으면 years_since를 기반으로 "대략" 날짜 추정. (추정인 경우 note에 '추정' 표기)
  function getRecentDateFromRow(r){
    const keys = ["last_win_date","last_win_draw_date","recent_win_date"];
    for (const k of keys){
      const v = (r[k]||"").trim();
      if (v) return { date: v, note: "" };
    }
    const ys = num(r.years_since);
    if (ys > 0 && Number.isFinite(ys)) {
      const days = Math.round(ys * 365);
      const d = new Date(); d.setDate(d.getDate()-days);
      return { date: fmtDate(d), note: " (추정)" };
    }
    return { date: "-", note: "" };
  }

  async function init() {
    // 지도
    const mapEl = document.getElementById("map");
    map = new kakao.maps.Map(mapEl, {
      center: new kakao.maps.LatLng(37.5665, 126.9780),
      level: 7,
    });

    // URL → UI
    readStateFromUrlAndFillUI();

    // CSV
    const CSV_URL = "data/lottang_stores_geo.csv";
    const head = await fetch(CSV_URL, { method:"HEAD", cache:"no-store" });
    if (!head.ok) { alert("CSV가 없습니다: web/data/lottang_stores_geo.csv"); return; }
    const text = await (await fetch(CSV_URL, { cache:"no-store" })).text();
    rowsAll = parseCsv(text).filter(r=>r.lat&&r.lng);

    // 초기 적용
    applyFilters();

    // 필터 이벤트
    ["f-only1","f-recent","f-minscore","f-radius"].forEach(id=>{
      document.getElementById(id)?.addEventListener("change", applyFilters);
    });
    document.getElementById("f-q")?.addEventListener("input", ()=>{
      clearTimeout(window.__qTimer);
      window.__qTimer = setTimeout(applyFilters, 300);
    });
    document.getElementById("btn-apply")?.addEventListener("click", applyFilters);
    document.getElementById("btn-reset")?.addEventListener("click", resetFilters);

    document.getElementById("loc-btn")?.addEventListener("click", ()=>{
      if(!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition((pos)=>{
        map.setCenter(new kakao.maps.LatLng(pos.coords.latitude, pos.coords.longitude));
        map.setLevel(5);
        applyFilters();
      });
    });

    // 공유
    document.getElementById("btn-share")?.addEventListener("click", async ()=>{
      try {
        await navigator.clipboard.writeText(location.href);
        toast("링크를 클립보드에 복사했어요!");
      } catch {
        prompt("링크 복사", location.href);
      }
    });

    // 시트 닫기
    document.getElementById("btn-close")?.addEventListener("click", ()=>{
      document.getElementById("bottom-sheet")?.classList.add("hidden");
    });
    // 지도 클릭 시 시트 닫기
    kakao.maps.event.addListener(map, "click", ()=>{
      document.getElementById("bottom-sheet")?.classList.add("hidden");
    });

    // 지도 이동/줌 시 URL 동기 + 반경 재적용
    kakao.maps.event.addListener(map, "idle", ()=>{
      syncUrlFromUI(true);
      if (currentRadiusKm > 0) applyFilters();
    });
  }

  function readStateFromUrlAndFillUI(){
    const p = qs();
    const only1   = p.get("only1")==="1";
    const recent  = p.get("recent")==="1";
    const minscore= p.get("minscore") ?? "0";
    const radius  = p.get("radius") ?? "0";
    const q       = decodeURIComponent(p.get("q") || "");

    document.getElementById("f-only1").checked = only1;
    document.getElementById("f-recent").checked = recent;
    document.getElementById("f-minscore").value = minscore;
    document.getElementById("f-radius").value = radius;
    document.getElementById("f-q").value = q;

    const lat = num(p.get("lat")); const lng = num(p.get("lng")); const level = num(p.get("level"));
    if (lat && lng) map.setCenter(new kakao.maps.LatLng(lat,lng));
    if (level) map.setLevel(level);
  }

  function resetFilters(){
    suppressUrlSync = true;
    document.getElementById("f-only1").checked = false;
    document.getElementById("f-recent").checked = false;
    document.getElementById("f-minscore").value = "0";
    document.getElementById("f-radius").value = "0";
    document.getElementById("f-q").value = "";
    currentRadiusKm = 0;
    if (centerCircle) { centerCircle.setMap(null); centerCircle = null; }
    render(rowsAll);
    syncUrlFromUI(false);
    suppressUrlSync = false;
  }

  function applyFilters() {
    const only1 = document.getElementById("f-only1").checked;
    const recent = document.getElementById("f-recent").checked;
    const minScore = num(document.getElementById("f-minscore").value);
    const radiusKm = num(document.getElementById("f-radius").value);
    const q = (document.getElementById("f-q").value || "").trim().toLowerCase();

    currentRadiusKm = radiusKm;

    let out = rowsAll;

    if (only1) out = out.filter(r => num(r.win1_cnt) > 0);
    if (recent) out = out.filter(r => num(r.years_since) <= 1.0);
    if (minScore > 0) out = out.filter(r => num(r.score) >= minScore);
    if (q) {
      out = out.filter(r =>
        (r.store_name || "").toLowerCase().includes(q) ||
        (r.address_full || "").toLowerCase().includes(q)
      );
    }

    if (radiusKm > 0) {
      const c = map.getCenter();
      out = out.filter(r => distKm(num(r.lat), num(r.lng), c.getLat(), c.getLng()) <= radiusKm);

      const mRadius = radiusKm * 1000;
      if (!centerCircle) {
        centerCircle = new kakao.maps.Circle({
          center: c, radius: mRadius,
          strokeWeight: 2, strokeColor: '#1e88e5', strokeOpacity: 0.8, strokeStyle: 'solid',
          fillColor: '#42a5f5', fillOpacity: 0.12
        });
        centerCircle.setMap(map);
      } else {
        centerCircle.setPosition(c);
        centerCircle.setRadius(mRadius);
        centerCircle.setMap(map);
      }
    } else {
      if (centerCircle) { centerCircle.setMap(null); centerCircle = null; }
    }

    render(out);
    syncUrlFromUI(false);
  }

  function syncUrlFromUI(mapOnly){
    if (suppressUrlSync) return;
    const only1 = document.getElementById("f-only1").checked;
    const recent = document.getElementById("f-recent").checked;
    const minScore = document.getElementById("f-minscore").value;
    const radiusKm = document.getElementById("f-radius").value;
    const q = document.getElementById("f-q").value.trim();

    const c = map.getCenter();
    const payload = {
      lat: c.getLat().toFixed(6),
      lng: c.getLng().toFixed(6),
      level: map.getLevel()
    };
    if (!mapOnly) {
      if (only1) payload.only1 = 1;
      if (recent) payload.recent = 1;
      if (minScore !== "0") payload.minscore = minScore;
      if (radiusKm !== "0") payload.radius = radiusKm;
      if (q) payload.q = encodeURIComponent(q);
    }
    setQS(payload);
  }

  function render(rows) {
    // 카운트
    const countEl = document.getElementById("count-label");
    if (countEl) countEl.textContent = `${rows.length.toLocaleString()}건`;

    // 기존 제거
    if (clusterer) { clusterer.clear(); clusterer.setMap(null); clusterer = null; }
    if (markers.length) { markers.forEach(m => m.setMap(null)); }
    markers = [];

    // 새 마커
    markers = rows.map(r => makeMarker(r));

    // 클러스터
    clusterer = new kakao.maps.MarkerClusterer({
      map, averageCenter: true, minLevel: 6, gridSize: 80,
      styles: [{
        width:'36px', height:'36px',
        background:'rgba(180,240,120,0.9)',
        borderRadius:'18px', border:'2px solid #79c143',
        color:'#1b5e20', textAlign:'center',
        lineHeight:'34px', fontWeight:'bold'
      }]
    });
    clusterer.addMarkers(markers);

    // 데이터 적을 때 화면 맞춤
    if (rows.length && rows.length <= 300) {
      const bounds = new kakao.maps.LatLngBounds();
      rows.forEach(r => bounds.extend(new kakao.maps.LatLng(num(r.lat), num(r.lng))));
      map.setBounds(bounds);
    }
  }

  function makeMarker(r) {
    const pos = new kakao.maps.LatLng(num(r.lat), num(r.lng));
    const score = num(r.score);
    const color = score >= 50 ? "#e53935" : score >= 20 ? "#fb8c00" : "#9e9e9e";

    const svg = encodeURIComponent(
      `<svg xmlns='http://www.w3.org/2000/svg' width='28' height='28' viewBox='0 0 28 28'>
         <circle cx='14' cy='14' r='9' fill='${color}' stroke='white' stroke-width='3'/>
       </svg>`
    );
    const img = new kakao.maps.MarkerImage(
      "data:image/svg+xml;utf8," + svg,
      new kakao.maps.Size(28, 28),
      { offset: new kakao.maps.Point(14, 14) }
    );

    const m = new kakao.maps.Marker({ position: pos, image: img, title: r.store_name });

    kakao.maps.event.addListener(m, "click", () => {
      // 필수 4항목 바인딩
      setText("#s-name", r.store_name || "-");
      setText("#s-addr", r.address_full || "-");
      setText("#s-win1", `1등 ${num(r.win1_cnt)}`);
      setText("#s-win2", `2등 ${num(r.win2_cnt)}`);
      setText("#s-score", `(점수 ${Number.isFinite(score)?score:"-"})`);

      const { date, note } = getRecentDateFromRow(r);
      setText("#s-recent-date", date);
      setText("#s-recent-note", note);

      // 길찾기 링크
      const a = document.getElementById("nav-link");
      if (a) a.href = `https://map.kakao.com/link/to/${encodeURIComponent(r.store_name || "목적지")},${r.lat},${r.lng}`;

      // 시트 열기
      document.getElementById("bottom-sheet")?.classList.remove("hidden");
    });

    return m;
  }

  // CSV 파서
  function parseCsv(text){
    const lines = text.replace(/\r/g,"").split("\n").filter(Boolean);
    if (!lines.length) return [];
    const header = split(lines[0]);
    return lines.slice(1).map(line=>{
      const cols = split(line), o={};
      header.forEach((h,i)=>o[h]=(cols[i]??"").trim());
      return o;
    });
  }
  function split(line){
    const out=[]; let cur="", q=false;
    for(let i=0;i<line.length;i++){
      const ch=line[i], nx=line[i+1];
      if(q){
        if(ch=='"'&&nx=='"'){cur+='"'; i++; continue;}
        if(ch=='"'){q=false; continue;}
        cur+=ch;
      }else{
        if(ch=='"'){q=true; continue;}
        if(ch==","){out.push(cur); cur=""; continue;}
        cur+=ch;
      }
    }
    out.push(cur); return out;
  }
  function setText(sel, txt){ const el=document.querySelector(sel); if(el) el.textContent=txt; }

  // 토스트
  function toast(msg){
    const el = document.createElement("div");
    el.textContent = msg;
    Object.assign(el.style, {
      position:"fixed", left:"50%", bottom:"24px", transform:"translateX(-50%)",
      background:"#111", color:"#fff", padding:"8px 12px", borderRadius:"999px",
      fontSize:"12px", zIndex:9999, opacity:0.95
    });
    document.body.appendChild(el);
    setTimeout(()=>{ el.remove(); }, 1500);
  }
})();