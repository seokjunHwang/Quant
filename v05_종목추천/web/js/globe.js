/* =========================================================
   Global Event Map - globe.js
   Leaflet dark map + event markers + side panel
   ========================================================= */

var globeMap = null;
var globeMarkers = [];
var globeLines = [];
var globeState = {
  filter: 'all',
  activeEvent: null,
  eventsData: null,
};

// ── Category config ──────────────────────────────────────
var CATEGORY_ICONS = {
  war: { emoji: '', color: '#ef4444' },
  policy: { emoji: '', color: '#eab308' },
  economic: { emoji: '', color: '#3b82f6' },
  energy: { emoji: '', color: '#22c55e' },
  disaster: { emoji: '', color: '#f97316' },
  trade: { emoji: '', color: '#06b6d4' },
  technology: { emoji: '', color: '#a855f7' },
  market: { emoji: '', color: '#8b5cf6' },
  fed: { emoji: '', color: '#3b82f6' },
  earnings: { emoji: '', color: '#06b6d4' },
};

// ── Initialize map ───────────────────────────────────────
function initGlobeMap() {
  if (globeMap) return;
  var container = document.getElementById('globe-map');
  if (!container) return;

  globeMap = L.map('globe-map', {
    center: [30, 40],
    zoom: 2,
    minZoom: 2,
    maxZoom: 8,
    zoomControl: true,
    attributionControl: false,
    worldCopyJump: true,
  });

  // CartoDB Dark Matter base (no labels)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', {
    subdomains: 'abcd',
  }).addTo(globeMap);

  // Country labels — zoom-level based (major at low zoom, all at high zoom)
  globeState.countryLabels = { major: [], minor: [] };
  globeState.showLabels = true;

  // Major countries (visible at zoom 2+)
  var MAJOR_LABELS = [
    [45.0, -100.0, 'USA'], [56.0, -106.0, 'Canada'],
    [-14.2, -51.9, 'Brazil'], [61.5, 105.3, 'Russia'],
    [35.9, 104.2, 'China'], [20.6, 79.0, 'India'],
    [-25.3, 133.8, 'Australia'],
    [51.5, -0.1, 'UK'], [46.2, 2.2, 'France'], [51.2, 10.5, 'Germany'],
    [36.2, 127.8, 'S.Korea'], [36.2, 138.3, 'Japan'],
    [35.7, 51.4, 'Iran'], [24.7, 46.7, 'Saudi'],
    [48.7, 31.2, 'Ukraine'], [23.6, -102.5, 'Mexico'],
  ];

  // Minor countries (visible at zoom 4+)
  var MINOR_LABELS = [
    [41.9, 12.5, 'Italy'], [40.5, -3.7, 'Spain'], [50.8, 4.4, 'Belgium'],
    [61.5, 24.0, 'Finland'], [59.3, 18.1, 'Sweden'], [52.1, 19.1, 'Poland'],
    [47.5, 14.5, 'Austria'], [46.8, 8.2, 'Switzerland'], [55.9, -3.2, 'Scotland'],
    [53.4, -8.2, 'Ireland'], [39.4, -8.2, 'Portugal'], [56.3, 10.0, 'Denmark'],
    [60.5, 25.0, 'Estonia'], [56.9, 24.1, 'Latvia'], [55.2, 23.9, 'Lithuania'],
    [49.8, 15.5, 'Czech'], [48.7, 19.7, 'Slovakia'], [47.2, 20.0, 'Hungary'],
    [42.7, 25.5, 'Bulgaria'], [45.9, 24.9, 'Romania'], [44.0, 21.0, 'Serbia'],
    [41.2, 20.2, 'Albania'], [39.1, 21.8, 'Greece'], [43.9, 17.7, 'Bosnia'],
    [23.7, 121.0, 'Taiwan'], [39.9, 125.8, 'N.Korea'],
    [31.0, 35.0, 'Israel'], [24.5, 54.4, 'UAE'], [39.0, 35.2, 'Turkey'],
    [26.8, 30.8, 'Egypt'], [33.9, 67.7, 'Afghan.'], [30.4, 69.3, 'Pakistan'],
    [1.4, 103.8, 'Singapore'], [4.2, 101.9, 'Malaysia'],
    [13.7, 100.5, 'Thailand'], [14.1, 108.3, 'Vietnam'],
    [-0.8, 113.9, 'Indonesia'], [12.9, 122.0, 'Philippines'],
    [15.9, 101.0, 'Myanmar'], [22.4, 114.1, 'Hong Kong'],
    [9.1, 7.5, 'Nigeria'], [-30.6, 22.9, 'S.Africa'],
    [28.0, 2.0, 'Algeria'], [34.0, 9.0, 'Tunisia'], [32.0, -5.0, 'Morocco'],
    [-38.4, -63.6, 'Argentina'], [-35.7, -71.5, 'Chile'],
    [4.6, -74.1, 'Colombia'], [10.5, -66.9, 'Venezuela'], [-16.3, -63.6, 'Bolivia'],
    [29.3, 47.5, 'Kuwait'], [25.3, 51.2, 'Qatar'], [23.6, 58.5, 'Oman'],
    [33.9, 35.5, 'Lebanon'], [33.3, 44.4, 'Iraq'], [35.0, 38.5, 'Syria'],
    [15.4, 44.2, 'Yemen'], [11.6, 43.1, 'Djibouti'],
  ];

  function makeLabel(c, cls) {
    return L.marker([c[0], c[1]], {
      icon: L.divIcon({
        className: 'country-label-marker ' + cls,
        html: '<span class="country-label-text">' + c[2] + '</span>',
        iconSize: [0, 0],
        iconAnchor: [0, 6],
      }),
      interactive: false,
    });
  }

  MAJOR_LABELS.forEach(function (c) {
    var m = makeLabel(c, 'major-label').addTo(globeMap);
    globeState.countryLabels.major.push(m);
  });
  MINOR_LABELS.forEach(function (c) {
    var m = makeLabel(c, 'minor-label');
    // Don't add to map yet — added on zoom
    globeState.countryLabels.minor.push(m);
  });

  // Zoom-based label visibility
  function updateLabelsForZoom() {
    if (!globeState.showLabels) return;
    var zoom = globeMap.getZoom();
    globeState.countryLabels.minor.forEach(function (m) {
      if (zoom >= 4) {
        if (!globeMap.hasLayer(m)) m.addTo(globeMap);
      } else {
        if (globeMap.hasLayer(m)) globeMap.removeLayer(m);
      }
    });
  }
  globeMap.on('zoomend', updateLabelsForZoom);
  updateLabelsForZoom();
}

// ── Load events data ─────────────────────────────────────
function loadGlobeData() {
  var dateStr = state.currentDate;
  if (!dateStr) return;

  // 같은 날짜 데이터가 이미 로드되어 있고 직전 로드와 동일하면 재호출 무시
  if (globeState.eventsData && globeState._loadedDate === dateStr) {
    return;
  }
  // 동시 호출 가드 (중복 fetch 방지)
  if (globeState._loadingDate === dateStr) return;
  globeState._loadingDate = dateStr;

  fetch('data/events_' + dateStr + '.json')
    .then(function (res) {
      if (!res.ok) throw new Error('No events data');
      return res.json();
    })
    .then(function (data) {
      globeState.eventsData = data;
      globeState._loadedDate = dateStr;
      globeState._loadingDate = null;
      renderGlobe(data);
    })
    .catch(function () {
      globeState._loadingDate = null;
      // 이전에 로드된 유효 데이터가 있으면 그대로 두고 empty 처리하지 않는다
      if (globeState.eventsData) return;
      globeState.eventsData = null;
      renderGlobeEmpty();
    });
}

// ── Render everything ────────────────────────────────────
function renderGlobe(data) {
  if (!data) return;
  renderTimeline(data);
  renderGlobeMarkers(data);
  renderGlobePanel(data);
  renderSectorBar(data);
  renderBottomSections(data);
}

function renderGlobeEmpty() {
  var timeline = document.getElementById('globe-timeline');
  if (timeline) timeline.innerHTML = '<div style="padding:0.5rem;color:var(--text-muted);font-size:0.75rem;">이벤트 데이터 없음 — main.py 실행 후 생성됩니다</div>';

  var list = document.getElementById('globe-events-list');
  if (list) list.innerHTML = '<div style="padding:2rem;text-align:center;color:var(--text-muted);font-size:0.8rem;">데이터 없음</div>';

  var sectors = document.getElementById('globe-sectors');
  if (sectors) sectors.innerHTML = '';

  clearGlobeMarkers();
}

// ── Timeline bar ─────────────────────────────────────────
function renderTimeline(data) {
  var container = document.getElementById('globe-timeline');
  if (!container) return;

  var upcoming = data.upcoming || [];
  var events = data.events || [];

  // Today marker
  var html = '<div class="timeline-item" onclick="resetGlobeView()">' +
    '<span class="timeline-dday today">TODAY</span>' +
    '<span class="timeline-name">' + events.length + '건</span>' +
    '<div class="timeline-dot high"></div>' +
    '</div>';

  for (var i = 0; i < upcoming.length && i < 8; i++) {
    var u = upcoming[i];
    var ddClass = 'later';
    var dd = u.d_day || '';
    var ddNum = parseInt(dd.replace('D-', ''));
    if (ddNum <= 2) ddClass = 'soon';
    if (ddNum <= 0) ddClass = 'today';

    var dotClass = u.importance === 'high' ? 'high' : u.importance === 'medium' ? 'medium' : 'low';

    html += '<div class="timeline-connector"></div>' +
      '<div class="timeline-item" onclick="focusUpcoming(' + i + ')" data-upcoming="' + i + '">' +
      '<span class="timeline-dday ' + ddClass + '">' + escapeHtml(dd) + '</span>' +
      '<span class="timeline-name">' + escapeHtml(u.event || '') + '</span>' +
      '<div class="timeline-dot ' + dotClass + '"></div>' +
      '</div>';
  }

  container.innerHTML = html;
}

// ── Map markers ──────────────────────────────────────────
function clearGlobeMarkers() {
  globeMarkers.forEach(function (m) { if (globeMap) globeMap.removeLayer(m); });
  globeLines.forEach(function (l) { if (globeMap) globeMap.removeLayer(l); });
  globeMarkers = [];
  globeLines = [];
}

// 카테고리별 SVG 아이콘 + 색상 (Lucide icons 기반, 24x24 viewBox)
var CAT_META = {
  war:        { color: '#ef4444', svg: '<path d="M14.5 17.5 3 6V3h3l11.5 11.5"/><path d="m13 19 6-6"/><path d="m16 16 4 4"/><path d="m19 21 2-2"/>' },
  policy:     { color: '#eab308', svg: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 12h8M8 8h8M8 16h5"/>' },
  economic:   { color: '#3b82f6', svg: '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/>' },
  energy:     { color: '#22c55e', svg: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>' },
  disaster:   { color: '#f97316', svg: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4M12 17h.01"/>' },
  trade:      { color: '#06b6d4', svg: '<path d="M16 3h5v5"/><path d="M8 3H3v5"/><path d="M3 16v5h5"/><path d="M16 21h5v-5"/><path d="M21 3 3 21"/>' },
  technology: { color: '#a855f7', svg: '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/>' },
  market:     { color: '#8b5cf6', svg: '<path d="M3 3v18h18"/><path d="M7 16v-7M11 16v-4M15 16v-9M19 16v-2"/>' },
  upcoming:   { color: '#94a3b8', svg: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>' },
};

function buildCategoryIcon(cat, severity) {
  var meta = CAT_META[cat] || CAT_META.economic;
  var sizeClass = severity === 'critical' ? 'sev-critical'
                 : severity === 'high' ? 'sev-high'
                 : severity === 'low' ? 'sev-low' : 'sev-medium';
  var pulse = severity === 'critical' ? 'pulse' : '';
  return '<div class="event-icon ' + sizeClass + ' ' + pulse + '" style="--cat-color:' + meta.color + '">' +
           '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" ' +
                'stroke-linecap="round" stroke-linejoin="round">' + meta.svg + '</svg>' +
         '</div>';
}

// upcoming idx → marker 매핑 (타임라인에서 popup 열 때 사용)
var upcomingMarkerMap = {};

// 좌표 충돌 회피: 같은 좌표를 공유하는 마커들을 작은 원으로 분산
function spreadOverlappingPoints(items) {
  // items: [{lat, lng, ...}]
  var groups = {};
  items.forEach(function (it, idx) {
    if (it.lat == null || it.lng == null) return;
    var key = it.lat.toFixed(2) + ',' + it.lng.toFixed(2);
    (groups[key] = groups[key] || []).push(idx);
  });
  var radiusDeg = 1.6;            // 약 ~180km 반경
  Object.keys(groups).forEach(function (k) {
    var arr = groups[k];
    if (arr.length <= 1) return;
    arr.forEach(function (i, n) {
      var angle = (2 * Math.PI * n) / arr.length - Math.PI / 2;
      items[i]._displayLat = items[i].lat + radiusDeg * Math.sin(angle);
      items[i]._displayLng = items[i].lng + radiusDeg * Math.cos(angle);
    });
  });
}

function renderGlobeMarkers(data) {
  if (!globeMap) return;
  clearGlobeMarkers();
  upcomingMarkerMap = {};

  var events = data.events || [];
  var upcoming = data.upcoming || [];

  // 1) 모든 표시 대상 점들을 한 배열로 수집해 좌표 분산 적용
  var allPoints = [];
  events.forEach(function (ev, evIdx) {
    var evCat = ev.category || 'economic';
    if (!isCatVisible(evCat)) return;
    (ev.points || []).forEach(function (pt) {
      if (pt.lat == null || pt.lng == null) return;
      allPoints.push({ kind: 'event', evIdx: evIdx, ev: ev, pt: pt, lat: pt.lat, lng: pt.lng });
    });
  });
  upcoming.forEach(function (u, uIdx) {
    if (u.lat == null || u.lng == null) return;
    allPoints.push({ kind: 'upcoming', uIdx: uIdx, u: u, lat: u.lat, lng: u.lng });
  });
  spreadOverlappingPoints(allPoints);

  // 2) 마커 생성
  allPoints.forEach(function (p) {
    var lat = p._displayLat != null ? p._displayLat : p.lat;
    var lng = p._displayLng != null ? p._displayLng : p.lng;

    if (p.kind === 'event') {
      var ev = p.ev;
      var evCat = ev.category || 'economic';
      var iconHtml = buildCategoryIcon(evCat, ev.severity || 'medium') +
                     '<div class="marker-label">' + escapeHtml(p.pt.label || p.pt.country || '') + '</div>';
      var icon = L.divIcon({
        className: 'event-marker-wrap',
        html: iconHtml,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });
      var marker = L.marker([lat, lng], { icon: icon }).addTo(globeMap);
      marker.bindPopup(buildPopupHtml(ev), {
        className: 'event-popup',
        maxWidth: 300,
        offset: [0, -14],
      });
      var evIdx = p.evIdx;
      marker.on('click', function () { highlightEventCard(evIdx); });
      globeMarkers.push(marker);
    } else {
      var u = p.u;
      var iconHtml2 = buildCategoryIcon('upcoming', 'medium') +
                     '<div class="marker-label">' + escapeHtml(u.d_day || '') + ' ' + escapeHtml((u.event || '').substring(0, 12)) + '</div>';
      var icon2 = L.divIcon({
        className: 'event-marker-wrap',
        html: iconHtml2,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });
      var marker2 = L.marker([lat, lng], { icon: icon2 }).addTo(globeMap);
      marker2.bindPopup(buildUpcomingPopupHtml(u), {
        className: 'event-popup',
        maxWidth: 300,
        offset: [0, -12],
      });
      upcomingMarkerMap[p.uIdx] = marker2;
      globeMarkers.push(marker2);
    }
  });
}

// upcoming 전용 팝업 (예정 이벤트에 맞는 정보 노출)
function buildUpcomingPopupHtml(u) {
  var html = '<div class="popup-title">' + escapeHtml(u.event || '') + '</div>' +
    '<div class="popup-summary">' +
      '<strong>' + escapeHtml(u.d_day || '') + '</strong> · ' +
      escapeHtml(u.date || '') + ' · ' +
      escapeHtml(u.country || '') +
    '</div>';

  if (u.impact_preview) {
    html += '<div class="popup-summary">' + escapeHtml(u.impact_preview) + '</div>';
  }

  var scenarios = u.scenarios || [];
  if (scenarios.length) {
    html += '<div class="popup-scenarios">';
    scenarios.forEach(function (s) {
      html += '<div class="popup-scenario">' +
        '<span class="popup-scenario-name">' + escapeHtml(s.name || '') + '</span> ' +
        '<span class="popup-scenario-prob">' + escapeHtml(s.probability || '') + '</span><br>' +
        '<span class="popup-scenario-impact">' + escapeHtml(s.impact || '') + '</span>' +
        '</div>';
    });
    html += '</div>';
  }

  var ws = u.watch_sectors || [];
  if (ws.length) {
    html += '<div class="popup-sectors">';
    ws.forEach(function (s) {
      html += '<span class="popup-sector-tag bullish">' + escapeHtml(s) + '</span>';
    });
    html += '</div>';
  }

  return html;
}

function buildPopupHtml(ev) {
  var html = '<div class="popup-title">' + escapeHtml(ev.title || '') + '</div>' +
    '<div class="popup-summary">' + escapeHtml(ev.summary || '') + '</div>';

  var sectors = ev.affected_sectors || [];
  if (sectors.length) {
    html += '<div class="popup-sectors">';
    sectors.forEach(function (s) {
      var cls = s.direction === 'bullish' ? 'bullish' : 'bearish';
      html += '<span class="popup-sector-tag ' + cls + '">' +
        escapeHtml(s.sector) + ' ' + escapeHtml(s.magnitude || '') + '</span>';
    });
    html += '</div>';
  }

  var tickers = ev.affected_tickers || [];
  if (tickers.length) {
    html += '<div class="popup-tickers">';
    tickers.forEach(function (t) {
      html += escapeHtml(t.ticker || '') + '(' + escapeHtml(t.impact || '') + ') ';
    });
    html += '</div>';
  }

  return html;
}

// ── Side panel event list ────────────────────────────────
function renderGlobePanel(data) {
  var list = document.getElementById('globe-events-list');
  if (!list) return;

  var events = data.events || [];
  var upcoming = data.upcoming || [];
  var filter = globeState.filter;

  var html = '';

  // Happened/Live events (filtered by category)
  if (filter === 'all' || filter === 'live') {
    events.forEach(function (ev, idx) {
      var evCat = ev.category || 'economic';
      if (!isCatVisible(evCat)) return;
      html += buildEventCard(ev, idx);
    });
  }

  // Upcoming events
  if (filter === 'all' || filter === 'upcoming') {
    upcoming.forEach(function (u, idx) {
      html += buildUpcomingCard(u, idx);
    });
  }

  if (!html) {
    html = '<div style="padding:2rem;text-align:center;color:var(--text-muted);font-size:0.8rem;">해당 이벤트 없음</div>';
  }

  list.innerHTML = html;
}

function buildEventCard(ev, idx) {
  var severity = ev.severity || 'medium';
  var status = ev.status || 'happened';
  var statusLabel = status === 'live' ? 'LIVE' : status === 'developing' ? '진행중' : ev.time_label || '';

  var html = '<div class="globe-event-card" data-event="' + idx + '" onclick="focusEvent(' + idx + ')">' +
    '<div class="gev-header">' +
    '<div class="gev-severity ' + severity + '"></div>' +
    '<div class="gev-title">' + escapeHtml(ev.title || '') + '</div>' +
    '<span class="gev-status ' + status + '">' + escapeHtml(statusLabel) + '</span>' +
    '</div>' +
    '<div class="gev-time">' + escapeHtml(ev.time_label || '') + '</div>' +
    '<div class="gev-summary">' + escapeHtml(ev.summary || '') + '</div>';

  // Sectors
  var sectors = ev.affected_sectors || [];
  if (sectors.length) {
    html += '<div class="gev-sectors">';
    sectors.forEach(function (s) {
      var cls = s.direction === 'bullish' ? 'bullish' : 'bearish';
      html += '<span class="popup-sector-tag ' + cls + '">' +
        escapeHtml(s.sector) + '</span>';
    });
    html += '</div>';
  }

  // Tickers
  var tickers = ev.affected_tickers || [];
  if (tickers.length) {
    html += '<div class="gev-tickers">';
    tickers.forEach(function (t) {
      html += escapeHtml(t.ticker) + ' ';
    });
    html += '</div>';
  }

  // Impact chain
  var chain = ev.impact_chain || [];
  if (chain.length) {
    html += '<div class="gev-chain">' + chain.map(escapeHtml).join(' → ') + '</div>';
  }

  html += '</div>';
  return html;
}

function buildUpcomingCard(u, idx) {
  var impClass = u.importance === 'high' ? 'high' : 'medium';

  var html = '<div class="globe-event-card upcoming-card" data-upcoming="' + idx + '">' +
    '<div class="gev-header">' +
    '<div class="gev-severity ' + impClass + '"></div>' +
    '<div class="gev-title">' + escapeHtml(u.event || '') + '</div>' +
    '<span class="gev-status upcoming">' + escapeHtml(u.d_day || '') + '</span>' +
    '</div>' +
    '<div class="gev-time">' + escapeHtml(u.date || '') + ' · ' + escapeHtml(u.country || '') + '</div>';

  if (u.impact_preview) {
    html += '<div class="gev-summary">' + escapeHtml(u.impact_preview) + '</div>';
  }

  // Scenarios
  var scenarios = u.scenarios || [];
  if (scenarios.length) {
    html += '<div class="gev-scenarios">';
    scenarios.forEach(function (s) {
      html += '<div class="gev-scenario">' +
        '<span class="gev-scenario-name">' + escapeHtml(s.name || '') + '</span>' +
        '<span>' + escapeHtml(s.probability || '') + ' — ' + escapeHtml(s.impact || '') + '</span>' +
        '</div>';
    });
    html += '</div>';
  }

  // Watch sectors
  var ws = u.watch_sectors || [];
  if (ws.length) {
    html += '<div class="gev-sectors" style="margin-top:0.25rem">';
    ws.forEach(function (s) {
      html += '<span class="popup-sector-tag bullish">' + escapeHtml(s) + '</span>';
    });
    html += '</div>';
  }

  html += '</div>';
  return html;
}

// ── Sector impact bar (마키 흐름) ────────────────────────
function renderSectorBar(data) {
  var container = document.getElementById('globe-sectors');
  if (!container) return;

  var sectors = data.sector_summary || [];
  if (!sectors.length) { container.innerHTML = ''; return; }

  function buildItem(s) {
    var dir = s.net_direction || 'neutral';
    var colorClass = dir === 'bullish' ? 'bullish' : dir === 'bearish' ? 'bearish' : 'neutral';
    var pctColor = dir === 'bullish' ? 'var(--green)' : dir === 'bearish' ? 'var(--red)' : 'var(--text-muted)';
    return '<div class="sector-impact-item">' +
      '<span class="sector-impact-name">' + escapeHtml(s.sector || '') + '</span>' +
      '<div class="sector-impact-bar">' +
      '<div class="sector-impact-fill ' + colorClass + '" style="width:' + Math.min(Math.abs(s.event_count || 1) * 30, 100) + '%"></div>' +
      '</div>' +
      '<span class="sector-impact-pct" style="color:' + pctColor + '">' +
      escapeHtml(s.key_reason || dir) + '</span>' +
      '</div>';
  }

  // 끊김 없이 흐르도록 동일 트랙을 2회 이어 붙임
  var inner = sectors.map(buildItem).join('');
  container.innerHTML =
    '<div class="globe-sectors-track">' + inner + inner + '</div>';
}

// ── Interactions ─────────────────────────────────────────
function focusEvent(idx) {
  if (!globeState.eventsData) return;
  var ev = globeState.eventsData.events[idx];
  if (!ev) return;

  var points = ev.points || [];
  if (points.length && points[0].lat) {
    globeMap.flyTo([points[0].lat, points[0].lng], 4, { duration: 0.8 });
  }
  highlightEventCard(idx);

  // 같은 idx 의 마커 중 첫 번째 popup 열기
  var target = globeMarkers.find(function (m) {
    var ll = m.getLatLng();
    return points.some(function (pt) {
      return Math.abs(ll.lat - pt.lat) < 2 && Math.abs(ll.lng - pt.lng) < 2;
    });
  });
  if (target) setTimeout(function () { target.openPopup(); }, 850);
}

function focusUpcoming(idx) {
  if (!globeState.eventsData) return;
  var u = globeState.eventsData.upcoming[idx];
  if (!u) return;

  if (u.lat && u.lng) {
    globeMap.flyTo([u.lat, u.lng], 4, { duration: 0.8 });
  }
  // 타임라인 → 해당 upcoming 마커 popup 열기
  var marker = upcomingMarkerMap[idx];
  if (marker) setTimeout(function () { marker.openPopup(); }, 850);
}

function highlightEventCard(idx) {
  document.querySelectorAll('.globe-event-card').forEach(function (el) {
    el.classList.remove('active');
  });
  var card = document.querySelector('.globe-event-card[data-event="' + idx + '"]');
  if (card) {
    card.classList.add('active');
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function resetGlobeView() {
  if (globeMap) globeMap.flyTo([30, 40], 2, { duration: 0.8 });
}

// ── Category filter state ────────────────────────────────
// 처음엔 모든 카테고리 활성. 'all' 키는 의미적 알리아스가 아니라 단순 표시용으로만 사용.
globeState.activeCats = new Set(['war', 'policy', 'economic', 'energy', 'disaster', 'trade', 'technology', 'market']);

function isCatVisible(cat) {
  // 정확히 그 카테고리가 set 안에 있을 때만 보임
  return globeState.activeCats.has(cat);
}

function refreshGlobeFilters() {
  if (!globeState.eventsData) return;
  // Re-render markers with filter
  renderGlobeMarkers(globeState.eventsData);
  renderGlobePanel(globeState.eventsData);
}

// ── Filter tabs (side panel) ─────────────────────────────
document.addEventListener('click', function (e) {
  // Side panel filter (전체/진행중/예정)
  if (e.target.classList.contains('globe-filter')) {
    document.querySelectorAll('.globe-filter').forEach(function (b) { b.classList.remove('active'); });
    e.target.classList.add('active');
    globeState.filter = e.target.getAttribute('data-filter');
    if (globeState.eventsData) renderGlobePanel(globeState.eventsData);
    return;
  }

  // Category bar toggle
  var catBtn = e.target.closest('.cat-btn');
  if (!catBtn) return;

  var action = catBtn.getAttribute('data-action');
  if (action === 'labels') {
    // Toggle country labels
    catBtn.classList.toggle('active');
    globeState.showLabels = catBtn.classList.contains('active');
    var allLabels = (globeState.countryLabels.major || []).concat(globeState.countryLabels.minor || []);
    allLabels.forEach(function (lbl) {
      if (globeState.showLabels) {
        // Respect zoom for minor
        var isMinor = globeState.countryLabels.minor.indexOf(lbl) >= 0;
        if (isMinor && globeMap.getZoom() < 4) return;
        if (!globeMap.hasLayer(lbl)) lbl.addTo(globeMap);
      } else {
        if (globeMap.hasLayer(lbl)) globeMap.removeLayer(lbl);
      }
    });
    return;
  }

  var cat = catBtn.getAttribute('data-cat');
  if (!cat) return;

  var ALL_CATS = ['war', 'policy', 'economic', 'energy', 'disaster', 'trade', 'technology', 'market'];

  if (cat === 'all') {
    // 전체 토글
    var allBtn = catBtn;
    var isAllActive = allBtn.classList.contains('active');
    if (isAllActive) {
      // 전체 끔
      allBtn.classList.remove('active');
      globeState.activeCats.clear();
      document.querySelectorAll('.cat-btn[data-cat]').forEach(function (b) {
        if (b.getAttribute('data-action') !== 'labels' && b.getAttribute('data-cat') !== 'all') {
          b.classList.remove('active');
        }
      });
    } else {
      // 전체 켬
      allBtn.classList.add('active');
      globeState.activeCats = new Set(ALL_CATS);
      document.querySelectorAll('.cat-btn[data-cat]').forEach(function (b) {
        if (b.getAttribute('data-action') !== 'labels') b.classList.add('active');
      });
    }
  } else {
    // 개별 토글
    catBtn.classList.toggle('active');
    if (catBtn.classList.contains('active')) {
      globeState.activeCats.add(cat);
    } else {
      globeState.activeCats.delete(cat);
    }
    // 'all' 버튼은 8개가 모두 active 일 때만 active
    var allActive = ALL_CATS.every(function (c) { return globeState.activeCats.has(c); });
    var allBtn2 = document.querySelector('.cat-btn[data-cat="all"]');
    if (allBtn2) allBtn2.classList.toggle('active', allActive);
  }

  refreshGlobeFilters();
});

// ── Hook into page tab switching + auto-init ─────────────
function initGlobeIfVisible() {
  var el = document.getElementById('page-globe');
  if (el && !el.classList.contains('hidden')) {
    setTimeout(function () {
      initGlobeMap();
      // flex 레이아웃 안에서 leaflet 이 폭/높이를 정확히 잡도록 여러 번 invalidate
      if (globeMap) {
        globeMap.invalidateSize();
        setTimeout(function () { globeMap && globeMap.invalidateSize(); }, 100);
        setTimeout(function () { globeMap && globeMap.invalidateSize(); }, 400);
      }
      loadGlobeData();
    }, 200);
  }
}

// 창 크기 바뀔 때도 leaflet 재계산
window.addEventListener('resize', function () {
  if (globeMap) globeMap.invalidateSize();
});

document.addEventListener('DOMContentLoaded', function () {
  // Auto-init on page load (globe is now default tab)
  initGlobeIfVisible();

  // Also init when tab is clicked
  document.querySelectorAll('.page-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      var page = this.getAttribute('data-page');
      if (page === 'globe') {
        initGlobeIfVisible();
      }
    });
  });
});

// Also try after data loads (dashboard may be hidden initially)
var _origRenderDashboard = window.renderDashboard;
if (typeof _origRenderDashboard === 'function') {
  window.renderDashboard = function () {
    _origRenderDashboard();
    initGlobeIfVisible();
  };
}

// ── Bottom Sections ──────────────────────────────────────

// ── Heatmap — TradingView free widget ────────────────────
var currentHeatmap = 'us';
var currentHeatmapSize = 'medium';
var currentHeatmapSector = '';

var HEATMAP_CONFIGS = {
  us:      { dataSource: 'SPX500',   title: 'S&P 500',  type: 'stock' },
  nasdaq:  { dataSource: 'NASDAQ100', title: 'NASDAQ 100', type: 'stock' },
  kr:      { dataSource: 'KOSPI',    title: 'KOSPI',     type: 'stock' },
  kosdaq:  { dataSource: 'KOSDAQ',   title: 'KOSDAQ',    type: 'stock' },
  crypto:  { dataSource: 'Crypto',   title: 'Crypto',    type: 'crypto' },
  eu:      { dataSource: 'SX5E',     title: 'Euro Stoxx', type: 'stock' },
};

var SECTOR_NAMES_KR = {
  'Technology': '기술/IT',
  'Healthcare': '헬스케어',
  'Financial': '금융',
  'Energy': '에너지',
  'Consumer Cyclical': '경기소비재',
  'Industrials': '산업재',
  'Communication Services': '커뮤니케이션',
  'Consumer Defensive': '필수소비재',
  'Basic Materials': '소재',
  'Real Estate': '부동산',
  'Utilities': '유틸리티',
};

var HM_SIZES = {
  small: 280,
  medium: 380,
  large: 520,
};

function loadHeatmapWidget(type) {
  var container = document.getElementById('heatmap-widget');
  if (!container) return;
  currentHeatmap = type;

  var cfg = HEATMAP_CONFIGS[type] || HEATMAP_CONFIGS.us;
  var isDark = document.documentElement.getAttribute('data-theme') !== 'light';
  var height = HM_SIZES[currentHeatmapSize] || 380;

  var widgetConfig = {
    dataSource: cfg.dataSource,
    blockSize: cfg.type === 'crypto' ? 'market_cap_calc' : 'market_cap_basic',
    blockColor: 'change',
    locale: 'kr',
    symbolUrl: '',
    colorTheme: isDark ? 'dark' : 'light',
    hasTopBar: false,
    isDataSetEnabled: false,
    isZoomEnabled: true,
    hasSymbolTooltip: true,
    isMonoSize: false,
    width: '100%',
    height: '100%',
  };

  if (cfg.type !== 'crypto') {
    widgetConfig.grouping = 'sector';
    widgetConfig.exchanges = [];
  }

  var widgetPath = cfg.type === 'crypto'
    ? 'crypto-coins-heatmap'
    : 'stock-heatmap';

  var url = 'https://s.tradingview.com/embed-widget/' + widgetPath + '/?locale=kr#' +
    encodeURIComponent(JSON.stringify(widgetConfig));
  container.innerHTML = '<iframe src="' + url + '" style="width:100%;height:' + height + 'px;border:none;" allowfullscreen></iframe>';

  // 사이드바: 다른 마켓 퀵 리스트
  renderMarketList();
}

function renderMarketList() {
  var container = document.getElementById('hm-sector-list');
  if (!container) return;

  var markets = [
    { key: 'us', name: 'S&P 500' },
    { key: 'nasdaq', name: 'NASDAQ 100' },
    { key: 'kr', name: 'KOSPI' },
    { key: 'kosdaq', name: 'KOSDAQ' },
    { key: 'crypto', name: 'Crypto' },
  ];

  var html = '';
  markets.forEach(function (m) {
    var isActive = currentHeatmap === m.key;
    html += '<div class="hm-sector-item' + (isActive ? ' active' : '') + '" data-hm-quick="' + m.key + '">' +
      '<span class="hm-sector-name">' + escapeHtml(m.name) + '</span>' +
      '</div>';
  });

  container.innerHTML = html;
}

// Heatmap tab clicks
document.addEventListener('click', function (e) {
  var hmTab = e.target.closest('.heatmap-tab');
  if (hmTab) {
    document.querySelectorAll('.heatmap-tab').forEach(function (b) { b.classList.remove('active'); });
    hmTab.classList.add('active');
    loadHeatmapWidget(hmTab.getAttribute('data-hm'));
    return;
  }

  // Size buttons
  var sizeBtn = e.target.closest('.hm-size-btn');
  if (sizeBtn) {
    document.querySelectorAll('.hm-size-btn').forEach(function (b) { b.classList.remove('active'); });
    sizeBtn.classList.add('active');
    currentHeatmapSize = sizeBtn.getAttribute('data-size');
    var mainEl = document.getElementById('heatmap-main');
    if (mainEl) mainEl.setAttribute('data-size', currentHeatmapSize);
    loadHeatmapWidget(currentHeatmap);
    return;
  }

  // Quick market switch (sidebar)
  var quickItem = e.target.closest('[data-hm-quick]');
  if (quickItem) {
    var mkt = quickItem.getAttribute('data-hm-quick');
    // Also update top tabs if matching
    document.querySelectorAll('.heatmap-tab').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-hm') === mkt);
    });
    loadHeatmapWidget(mkt);
    return;
  }
});

// News tab clicks
document.addEventListener('click', function (e) {
  var newsTab = e.target.closest('.gbc-tab[data-news]');
  if (!newsTab) return;
  document.querySelectorAll('.gbc-tab[data-news]').forEach(function (b) { b.classList.remove('active'); });
  newsTab.classList.add('active');
  if (globeState.eventsData) renderBottomNews(newsTab.getAttribute('data-news'));
});

// ── Render bottom sections from data ─────────────────────
function renderBottomSections(data) {
  // Load heatmap
  loadHeatmapWidget(currentHeatmap);

  // News from main data (state.data from app.js)
  renderBottomNews('kr');

  // Disasters from events
  renderDisasters(data);

  // Timeline from upcoming
  renderBottomTimeline(data);

  lucide.createIcons();
}

function renderBottomNews(market) {
  var container = document.getElementById('globe-news-list');
  if (!container) return;

  // Get news from main app state
  var mainData = (typeof state !== 'undefined' && state.data) ? state.data : null;
  if (!mainData || !mainData.news) {
    container.innerHTML = '<div class="gbc-empty">main.py \uC2E4\uD589 \uD6C4 \uD45C\uC2DC\uB429\uB2C8\uB2E4</div>';
    return;
  }

  var newsData = mainData.news[market] || {};
  var themes = newsData.hot_themes || [];
  var risks = newsData.risk_factors || [];

  var html = '';

  // Summary
  if (newsData.summary) {
    html += '<div class="gnews-item"><div class="gnews-title">' + escapeHtml(newsData.summary) + '</div></div>';
  }

  // Hot themes
  themes.forEach(function (t) {
    html += '<div class="gnews-item">' +
      '<div class="gnews-title">' + escapeHtml(t.theme || '') + '</div>' +
      '<div class="gnews-meta">' + escapeHtml(t.reason || '') + '</div>' +
      '<div class="gnews-sector-tags">';
    (t.sectors || []).forEach(function (s) {
      html += '<span class="popup-sector-tag bullish">' + escapeHtml(s) + '</span>';
    });
    html += '</div></div>';
  });

  // Risks
  risks.forEach(function (r) {
    var sev = r.severity === 'high' ? 'color:var(--red)' : r.severity === 'medium' ? 'color:var(--yellow)' : '';
    html += '<div class="gnews-item">' +
      '<div class="gnews-title" style="' + sev + '">' + escapeHtml(r.factor || '') + '</div>' +
      '<div class="gnews-meta">' + escapeHtml(r.description || '') + '</div>' +
      '</div>';
  });

  container.innerHTML = html || '<div class="gbc-empty">\uB274\uC2A4 \uC5C6\uC74C</div>';
}

function renderDisasters(data) {
  var container = document.getElementById('globe-disaster-list');
  if (!container) return;

  var events = (data.events || []).filter(function (ev) {
    return ev.category === 'disaster' || ev.category === 'war' ||
           ev.severity === 'critical' || ev.status === 'live';
  });

  if (!events.length) {
    container.innerHTML = '<div class="gbc-empty">\uAE34\uAE09 \uC774\uBCA4\uD2B8 \uC5C6\uC74C</div>';
    return;
  }

  var html = '';
  events.forEach(function (ev) {
    var sevColor = ev.severity === 'critical' ? 'var(--red)' :
                   ev.severity === 'high' ? '#f97316' : 'var(--yellow)';
    html += '<div class="gdisaster-item">' +
      '<div class="gdisaster-severity" style="background:' + sevColor + '"></div>' +
      '<div class="gdisaster-content">' +
      '<div class="gdisaster-title">' + escapeHtml(ev.title || '') + '</div>' +
      '<div class="gdisaster-meta">' + escapeHtml(ev.time_label || ev.time_ago || '') +
      ' \xB7 ' + (ev.countries || []).map(escapeHtml).join(', ') + '</div>' +
      '</div></div>';
  });
  container.innerHTML = html;
}

function renderBottomTimeline(data) {
  var container = document.getElementById('globe-timeline-list');
  if (!container) return;

  var upcoming = data.upcoming || [];
  if (!upcoming.length) {
    container.innerHTML = '<div class="gbc-empty">\uACBD\uC81C \uCE98\uB9B0\uB354 \uC5C6\uC74C</div>';
    return;
  }

  var html = '';
  upcoming.forEach(function (u) {
    var impClass = u.importance === 'high' ? 'high' : u.importance === 'medium' ? 'medium' : 'low';
    html += '<div class="gtl-item">' +
      '<div class="gtl-dday ' + impClass + '">' + escapeHtml(u.d_day || '') + '</div>' +
      '<div class="gtl-content">' +
      '<div class="gtl-event">' + escapeHtml(u.event || '') + '</div>' +
      '<div class="gtl-meta">' + escapeHtml(u.date || '') + ' \xB7 ' + escapeHtml(u.country || '') + '</div>' +
      '</div></div>';
  });
  container.innerHTML = html;
}
