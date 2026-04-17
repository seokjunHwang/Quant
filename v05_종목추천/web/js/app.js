/* =========================================================
   Stock Recommendation Dashboard - app.js
   Pure vanilla JS, no frameworks, no emojis.
   ========================================================= */

// ── State ──────────────────────────────────────────────────
let state = {
  dates: [],
  currentDate: '',
  data: null,
  prevData: null,
  themeFilter: 'all',
  recFilter: 'all',
  isDark: true,
};

// ── Macro key display names ────────────────────────────────
const MACRO_NAMES = {
  vix: 'VIX',
  sp500: 'S&P 500',
  nasdaq: 'NASDAQ',
  kospi: 'KOSPI',
  kosdaq: 'KOSDAQ',
  usdkrw: 'USD/KRW',
  oil_wti: 'WTI',
  gold: 'GOLD',
  bitcoin: 'BTC',
  dollar_index: 'DXY',
  us10y_yield: 'US 10Y',
  us2y_yield: 'US 2Y',
};

// Display order for macro cards
const MACRO_ORDER = [
  'vix', 'sp500', 'nasdaq', 'kospi', 'usdkrw',
  'oil_wti', 'gold', 'bitcoin', 'dollar_index', 'us10y_yield',
];

// TradingView symbol mapping
var MACRO_TV_SYMBOLS = {
  vix: 'CBOE:VIX',
  sp500: 'SP:SPX',
  nasdaq: 'NASDAQ:NDX',
  kospi: 'KRX:KOSPI',
  kosdaq: 'KRX:KOSDAQ',
  usdkrw: 'FX_IDC:USDKRW',
  oil_wti: 'TVC:USOIL',
  gold: 'TVC:GOLD',
  bitcoin: 'BITSTAMP:BTCUSD',
  dollar_index: 'TVC:DXY',
  us10y_yield: 'TVC:US10Y',
};

var currentTVTimeframe = 'D';

function formatMarketCap(cap, market) {
  if (!cap || cap <= 0) return '-';
  if (market === 'kr') {
    // 한국: 원 단위
    var eok = cap / 100000000;
    if (eok >= 10000) return (eok / 10000).toFixed(1) + '조';
    return Math.round(eok).toLocaleString() + '억';
  } else {
    // 미국: USD 단위 → $1조, $3,311억 형식
    var billions = cap / 1000000000;        // 10억$ 단위
    var eokDollar = Math.round(billions * 10); // 억$ 단위
    if (eokDollar >= 10000) return '$' + (eokDollar / 10000).toFixed(1) + '조';
    return '$' + eokDollar.toLocaleString() + '억';
  }
}

function openTVChart(symbol, title) {
  document.getElementById('tv-title').textContent = title || symbol;
  var searchInput = document.getElementById('tv-search-input');
  if (searchInput) searchInput.value = symbol;
  document.getElementById('tv-overlay').classList.remove('hidden');
  document.getElementById('tv-modal').classList.remove('hidden');
  loadTVWidget(symbol, currentTVTimeframe);
  lucide.createIcons();
}

function openTVSearch() {
  document.getElementById('tv-title').textContent = '';
  var searchInput = document.getElementById('tv-search-input');
  if (searchInput) { searchInput.value = ''; }
  document.getElementById('tv-overlay').classList.remove('hidden');
  document.getElementById('tv-modal').classList.remove('hidden');
  document.getElementById('tv-chart-container').innerHTML =
    '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:0.85rem;">심볼을 입력하고 Go 또는 Enter를 누르세요</div>';
  if (searchInput) searchInput.focus();
  lucide.createIcons();
}

function searchTVChart() {
  var input = document.getElementById('tv-search-input');
  if (!input) return;
  var symbol = input.value.trim();
  if (!symbol) return;
  document.getElementById('tv-title').textContent = symbol;
  loadTVWidget(symbol, currentTVTimeframe);
}

function closeTVChart() {
  document.getElementById('tv-overlay').classList.add('hidden');
  document.getElementById('tv-modal').classList.add('hidden');
  document.getElementById('tv-chart-container').innerHTML = '';
}

function setTVTimeframe(tf) {
  currentTVTimeframe = tf;
  document.querySelectorAll('.tv-tf-btn').forEach(function (b) { b.classList.remove('active'); });
  document.querySelector('.tv-tf-btn[data-tf="' + tf + '"]').classList.add('active');
  // 현재 심볼로 재로드
  var container = document.getElementById('tv-chart-container');
  var iframe = container.querySelector('iframe');
  if (iframe) {
    var src = iframe.src;
    // interval 파라미터 교체
    iframe.src = src.replace(/interval=[^&]+/, 'interval=' + tf);
  }
}

function loadTVWidget(symbol, interval) {
  var container = document.getElementById('tv-chart-container');
  var isDark = document.documentElement.getAttribute('data-theme') !== 'light';
  var config = {
    symbol: symbol,
    interval: interval,
    theme: isDark ? 'dark' : 'light',
    style: '1',
    locale: 'kr',
    timezone: 'Asia/Seoul',
    allow_symbol_change: true,
    support_host: 'https://www.tradingview.com',
    width: '100%',
    height: '100%'
  };
  var url = 'https://s.tradingview.com/embed-widget/advanced-chart/?locale=kr#' +
    encodeURIComponent(JSON.stringify(config));
  container.innerHTML = '<iframe src="' + url + '" style="width:100%;height:100%;border:none;" allowfullscreen></iframe>';
}

// ── Helpers ────────────────────────────────────────────────
function formatNumber(n) {
  if (n === undefined || n === null) return '-';
  if (typeof n === 'string') return n;
  return n.toLocaleString('ko-KR', { maximumFractionDigits: 2 });
}

function formatDate(dateStr) {
  if (!dateStr || dateStr.length !== 8) return dateStr;
  var y = dateStr.slice(0, 4);
  var m = dateStr.slice(4, 6);
  var d = dateStr.slice(6, 8);
  var date = new Date(parseInt(y), parseInt(m) - 1, parseInt(d));
  var days = ['일', '월', '화', '수', '목', '금', '토'];
  return y + '.' + m + '.' + d + ' (' + days[date.getDay()] + ')';
}

function getScoreColor(score) {
  if (score >= 70) return 'var(--green)';
  if (score >= 55) return 'var(--yellow)';
  return 'var(--red)';
}

function getTimingClass(timing) {
  if (!timing) return 'watch';
  if (timing.indexOf('\uB9E4\uC218') !== -1) return 'buy';
  if (timing.indexOf('\uB9E4\uB3C4') !== -1) return 'sell';
  return 'watch';
}

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Ticker Copy ───────────────────────────────────────────
function copyTicker(ticker, market, el) {
  // 클립보드 복사
  navigator.clipboard.writeText(ticker).catch(function () {});

  // 기존 팝업 제거
  var old = document.querySelector('.ticker-popup');
  if (old) old.remove();

  // 클릭 위치 기준 fixed 팝업
  var rect = el.getBoundingClientRect();
  var popup = document.createElement('div');
  popup.className = 'ticker-popup';
  popup.style.position = 'fixed';
  popup.style.left = rect.left + 'px';
  popup.style.top = (rect.bottom + 4) + 'px';
  popup.style.zIndex = '9999';

  // 화면 아래 넘치면 위로
  if (rect.bottom + 100 > window.innerHeight) {
    popup.style.top = '';
    popup.style.bottom = (window.innerHeight - rect.top + 4) + 'px';
  }

  var tossUrl = market === 'kr'
    ? 'https://tossinvest.com/stocks/A' + ticker
    : 'https://tossinvest.com/stocks/' + ticker;

  popup.innerHTML =
    '<span class="ticker-popup-copied">' + ticker + ' 복사됨</span>' +
    '<div class="ticker-popup-actions">' +
    '<a href="' + tossUrl + '" target="_blank" rel="noopener" class="ticker-popup-btn toss">' +
    '토스증권</a>' +
    '<button class="ticker-popup-btn tv" onclick="event.stopPropagation();closeTickerPopup();openTickerTV(\'' + ticker + '\',\'' + (market || 'us') + '\');">' +
    '트레이딩뷰</button>' +
    '</div>';

  document.body.appendChild(popup);
  setTimeout(function () { popup.classList.add('show'); }, 10);

  // 외부 클릭 시 닫기
  setTimeout(function () {
    document.addEventListener('click', closeTickerPopup);
  }, 100);
  setTimeout(closeTickerPopup, 6000);
}

function closeTickerPopup() {
  var popup = document.querySelector('.ticker-popup');
  if (popup) {
    popup.classList.remove('show');
    setTimeout(function () { popup.remove(); }, 200);
  }
  document.removeEventListener('click', closeTickerPopup);
}

function openTickerTV(ticker, market) {
  // 기존 팝업 닫기
  var old = document.querySelector('.ticker-popup');
  if (old) old.remove();

  var symbol;
  if (market === 'kr') {
    symbol = 'KRX:' + ticker;
  } else {
    symbol = ticker;
  }
  openTVChart(symbol, ticker);
}

// ── Rank Comparison ────────────────────────────────────────
function getRankChange(ticker) {
  if (!state.prevData) return { type: 'same', value: 0 };
  var prevRec = state.prevData.recommendations.find(function (r) {
    return r.ticker === ticker;
  });
  if (!prevRec) return { type: 'new', value: 0 };
  var currRec = state.data.recommendations.find(function (r) {
    return r.ticker === ticker;
  });
  if (!currRec) return { type: 'same', value: 0 };
  var diff = prevRec.rank - currRec.rank;
  if (diff > 0) return { type: 'up', value: diff };
  if (diff < 0) return { type: 'down', value: Math.abs(diff) };
  return { type: 'same', value: 0 };
}

function renderRankChange(change) {
  if (change.type === 'new')
    return '<span class="rank-change new">NEW</span>';
  if (change.type === 'up')
    return '<span class="rank-change up">&#9650;' + change.value + '</span>';
  if (change.type === 'down')
    return '<span class="rank-change down">&#9660;' + change.value + '</span>';
  return '<span class="rank-change same">-</span>';
}

// ── Error Display ──────────────────────────────────────────
function showError(msg) {
  document.getElementById('loading').classList.add('hidden');
  document.getElementById('dashboard').classList.add('hidden');
  document.getElementById('error').classList.remove('hidden');
  document.getElementById('error-message').textContent = msg;
}

// ── Data Loading ───────────────────────────────────────────
async function loadData(dateStr) {
  document.getElementById('loading').classList.remove('hidden');
  document.getElementById('dashboard').classList.add('hidden');
  document.getElementById('error').classList.add('hidden');

  try {
    var resp = await fetch('data/' + dateStr + '.json');
    if (!resp.ok) throw new Error(dateStr + ' \uB370\uC774\uD130 \uC5C6\uC74C');
    state.data = await resp.json();
    state.currentDate = dateStr;

    // Update date select
    document.getElementById('select-date').value = dateStr;

    // Update market count badge
    var badgeEl = document.getElementById('badge-market');
    if (badgeEl) {
      var c = state.data.counts || {};
      badgeEl.textContent = (c.kr || 0) + ' KR + ' + (c.us || 0) + ' US';
    }

    // Load previous day data for rank comparison
    state.prevData = null;
    var dateIdx = state.dates.indexOf(dateStr);
    if (dateIdx >= 0 && dateIdx < state.dates.length - 1) {
      try {
        var prevResp = await fetch('data/' + state.dates[dateIdx + 1] + '.json');
        if (prevResp.ok) state.prevData = await prevResp.json();
      } catch (e) {
        /* previous day not available, ignore */
      }
    }

    render();

    document.getElementById('loading').classList.add('hidden');
    document.getElementById('dashboard').classList.remove('hidden');

    // Init globe map if it's the default visible tab
    if (typeof initGlobeIfVisible === 'function') initGlobeIfVisible();

    // Reset filter tabs
    state.themeFilter = 'all';
    state.recFilter = 'all';
    document.querySelectorAll('.theme-tab').forEach(function (b) {
      b.classList.remove('active');
    });
    var themeAllTab = document.querySelector('.theme-tab[data-filter="all"]');
    if (themeAllTab) themeAllTab.classList.add('active');

    document.querySelectorAll('.rec-tab').forEach(function (b) {
      b.classList.remove('active');
    });
    var recAllTab = document.querySelector('.rec-tab[data-filter="all"]');
    if (recAllTab) recAllTab.classList.add('active');

    // Re-initialize lucide icons for any newly rendered content
    if (typeof lucide !== 'undefined') lucide.createIcons();
  } catch (e) {
    console.error('loadData error:', e);
    showError(e.message);
  }
}

// ── Rendering ──────────────────────────────────────────────
function render() {
  if (!state.data) return;
  try { renderMacro(); } catch(e) { console.error('renderMacro:', e); }
  try { renderStrategy(); } catch(e) { console.error('renderStrategy:', e); }
  try { renderSummary(); } catch(e) { console.error('renderSummary:', e); }
  try { renderThemes(); } catch(e) { console.error('renderThemes:', e); }
  try { renderRecommendations(); } catch(e) { console.error('renderRecommendations:', e); }
  try { renderAvoid(); } catch(e) { console.error('renderAvoid:', e); }
  try { renderFooter(); } catch(e) { console.error('renderFooter:', e); }
}

function renderMacro() {
  if (!state.data) return;
  var macro = state.data.macro || {};
  var container = document.getElementById('macro-cards');
  if (!container) return;
  var html = '';

  for (var i = 0; i < MACRO_ORDER.length; i++) {
    var key = MACRO_ORDER[i];
    var val = macro[key];
    if (!val || typeof val !== 'object') continue;

    var name = MACRO_NAMES[key] || key;
    var price = formatNumber(val.price);
    var chg = val.change_pct || 0;
    var chgSign = chg >= 0 ? '+' : '';
    var chgColor =
      chg > 0
        ? 'var(--green)'
        : chg < 0
          ? 'var(--red)'
          : 'var(--text-muted)';
    var arrow = chg > 0 ? '&#9650; ' : chg < 0 ? '&#9660; ' : '';

    var badge = '';
    if (key === 'vix') {
      var zone = macro.vix_zone || '';
      var zoneColor =
        zone === '\uADF9\uACF5\uD3EC' || zone === '\uACF5\uD3EC'
          ? 'var(--red)'
          : zone === '\uAE34\uC7A5'
            ? 'var(--yellow)'
            : 'var(--green)';
      badge =
        '<span class="badge" style="background:color-mix(in srgb, ' +
        zoneColor +
        ' 15%, transparent);color:' +
        zoneColor +
        '">' +
        escapeHtml(zone) +
        '</span>';
    }

    var tvSymbol = MACRO_TV_SYMBOLS[key] || '';

    html +=
      '<div class="macro-card fade-in">' +
      '<div class="label">' +
      escapeHtml(name) +
      '</div>' +
      '<div class="value">' +
      price +
      '</div>' +
      '<div class="change" style="color:' +
      chgColor +
      '">' +
      arrow +
      chgSign +
      chg.toFixed(1) +
      '%</div>' +
      badge +
      (tvSymbol ? '<div class="macro-chart-btns">' +
        '<a class="macro-chart-btn ext" href="https://www.tradingview.com/chart/?symbol=' + encodeURIComponent(tvSymbol) + '" target="_blank" rel="noopener">TradingView 차트보기</a>' +
      '</div>' : '') +
      '</div>';
  }

  container.innerHTML = html;
}

function renderStrategy() {
  if (!state.data) return;
  var strategyEl = document.getElementById('txt-strategy');
  var viewEl = document.getElementById('txt-market-view');
  if (strategyEl) strategyEl.textContent = state.data.strategy || '';
  if (viewEl) viewEl.textContent = state.data.market_view || '';
}

function renderSummary() {
  renderNews('all');
}

function renderNews(market) {
  var container = document.getElementById('news-content');
  if (!container) return;
  if (!state.data) return;
  var news = state.data.news || {};
  var html = '';

  // 전체 요약
  if (market === 'all' || market === 'us' || market === 'kr') {
    if (state.data.market_summary) {
      html += '<div class="news-card"><p class="text-sm leading-relaxed text-gray-300">' +
        escapeHtml(state.data.market_summary) + '</p></div>';
    }
  }

  var markets = market === 'all' ? ['us', 'kr'] : [market];
  for (var i = 0; i < markets.length; i++) {
    var mkt = markets[i];
    var n = news[mkt];
    if (!n) continue;
    var label = mkt === 'us' ? 'US' : 'KR';

    html += '<div class="news-card">';
    html += '<div class="news-market-label ' + mkt + '">' + label + ' 시장</div>';

    if (n.summary) {
      html += '<p class="text-sm text-gray-300 mb-3">' + escapeHtml(n.summary) + '</p>';
    }

    // 핫 테마
    var themes = n.hot_themes || [];
    if (themes.length) {
      html += '<p class="text-xs text-gray-500 mb-1 mt-2">핫 테마</p>';
      for (var t = 0; t < themes.length; t++) {
        html += '<div class="news-theme-item">' +
          '<span class="news-theme-badge">' + escapeHtml(themes[t].trading_type || '') + '</span>' +
          '<span>' + escapeHtml(themes[t].theme || '') + ' — ' + escapeHtml(themes[t].reason || '') + '</span>' +
          '</div>';
      }
    }

    // 리스크
    var risks = n.risk_factors || [];
    if (risks.length) {
      html += '<p class="text-xs text-gray-500 mb-1 mt-3">리스크 요인</p>';
      for (var r = 0; r < risks.length; r++) {
        var sev = risks[r].severity || 'low';
        html += '<div class="news-risk-item news-risk-' + sev + '">' +
          '[' + sev.toUpperCase() + '] ' + escapeHtml(risks[r].factor || '') +
          ': ' + escapeHtml(risks[r].description || '') + '</div>';
      }
    }

    html += '</div>';
  }

  container.innerHTML = html || '<p class="text-sm text-gray-500">뉴스 데이터 없음</p>';
}

function renderThemes() {
  if (!state.data) return;
  var themes = state.data.themes || [];
  var container = document.getElementById('theme-list');
  if (!container) return;
  var countEl = document.getElementById('theme-count');
  if (countEl) countEl.textContent = '(' + themes.length + '개)';
  var html = '';

  for (var i = 0; i < themes.length; i++) {
    var t = themes[i];
    var show =
      state.themeFilter === 'all' || t.strength === state.themeFilter;
    var dotClass =
      t.strength === '\uAC15'
        ? 's-strong'
        : t.strength === '\uC911'
          ? 's-mid'
          : 's-weak';

    var riskHtml = t.risk
      ? '<p class="text-xs text-red-400-70 mt-1">Risk: ' +
        escapeHtml(t.risk) +
        '</p>'
      : '';

    html +=
      '<div class="theme-card' +
      (show ? ' fade-in' : ' hidden-filter') +
      '">' +
      '<div class="flex items-start gap-2">' +
      '<span class="strength-dot ' +
      dotClass +
      '"></span>' +
      '<div class="flex-1 min-w-0">' +
      '<div class="flex items-center gap-2 flex-wrap">' +
      '<span class="text-sm font-semibold">' +
      escapeHtml(t.name) +
      '</span>' +
      '<span class="theme-tag">' +
      escapeHtml(t.trading_type) +
      ' / ' +
      escapeHtml(t.duration) +
      '</span>' +
      '</div>' +
      '<p class="text-xs text-muted mt-1 line-clamp-2">' +
      escapeHtml(t.reason) +
      '</p>' +
      riskHtml +
      '</div>' +
      '</div>' +
      '</div>';
  }

  container.innerHTML = html;
}

function isMobile() {
  return window.innerWidth <= 768;
}

function renderRecommendations() {
  if (!state.data) return;
  var recs = state.data.recommendations || [];
  var filtered = recs.filter(function (r) {
    if (state.recFilter === 'all') return true;
    if (state.recFilter === 'kr') return r.market === 'kr';
    return r.market !== 'kr';
  });

  var countEl = document.getElementById('rec-count');
  if (countEl) countEl.textContent = '(' + filtered.length + '\uAC1C)';

  // Desktop table
  var tbody = document.getElementById('rec-table-body');
  // Mobile card list
  var cardList = document.getElementById('rec-card-list');

  if (tbody) renderRecTable(filtered, tbody);
  if (cardList) renderRecCards(filtered, cardList);
}

function renderRecTable(filtered, tbody) {
  var html = '';
  for (var idx = 0; idx < filtered.length; idx++) {
    var rec = filtered[idx];
    var scoreColor = getScoreColor(rec.final_score);
    var timingClass = getTimingClass(rec.timing);
    var change = getRankChange(rec.ticker);
    var mktBadge = rec.market === 'kr' ? 'kr' : 'us';
    var mktLabel = rec.market === 'kr' ? 'KR' : 'US';

    var heat = rec.heat || {};
    var rsi = heat.rsi || 50;
    var heatLevel = rsi >= 70 ? 'overheat' : rsi <= 30 ? 'oversold' : 'neutral';
    var heatLabel = rsi >= 70 ? '\uACFC\uC5F4' : rsi <= 30 ? '\uACFC\uB9E4\uB3C4' : '\uBCF4\uD1B5';

    html +=
      '<tr class="fade-in" onclick="openDetail(' +
      idx +
      ')" style="animation-delay:' +
      idx * 30 +
      'ms">' +
      '<td class="col-rank">' +
      rec.rank +
      '</td>' +
      '<td class="col-name">' +
      '<div class="rec-name-cell">' +
      '<span class="market-badge ' + mktBadge + '">' + mktLabel + '</span>' +
      '<span class="rec-stock-name">' + escapeHtml(rec.name) + '</span>' +
      '</div>' +
      '</td>' +
      '<td class="col-ticker">' +
      '<span class="ticker-copy" onclick="event.stopPropagation();copyTicker(\'' + escapeHtml(rec.ticker) + '\',\'' + (rec.market || 'us') + '\',this)" title="\uD074\uB9AD \u2192 \uBCF5\uC0AC + \uD1A0\uC2A4/\uD2B8\uBDF0">' +
      escapeHtml(rec.ticker) +
      '</span>' +
      '</td>' +
      '<td class="col-theme hidden-mobile">' +
      escapeHtml(rec.theme) +
      '</td>' +
      '<td class="col-score">' +
      '<span class="score-value" style="color:' + scoreColor + '">' +
      rec.final_score.toFixed(1) +
      '</span>' +
      '</td>' +
      '<td class="col-mcap hidden-mobile">' +
      '<span class="mcap-value">' + formatMarketCap(rec.market_cap, rec.market) + '</span>' +
      '</td>' +
      '<td class="col-heat">' +
      '<div class="heat-indicator ' + heatLevel + '" title="RSI ' + rsi.toFixed(0) + '">' +
      '<div class="heat-bar" style="width:' + Math.min(rsi, 100) + '%"></div>' +
      '</div>' +
      '<span class="heat-label ' + heatLevel + '">' + heatLabel + '</span>' +
      '</td>' +
      '<td class="col-timing">' +
      '<span class="timing-badge ' + timingClass + '">' +
      escapeHtml(rec.timing) +
      '</span>' +
      '</td>' +
      '<td class="col-change hidden-tablet">' +
      renderRankChange(change) +
      '</td>' +
      '<td class="col-events hidden-tablet">' +
      escapeHtml(rec.upcoming_events || '-') +
      '</td>' +
      '</tr>';
  }
  tbody.innerHTML = html;
}

function renderRecCards(filtered, container) {
  var html = '';
  for (var idx = 0; idx < filtered.length; idx++) {
    var rec = filtered[idx];
    var scoreColor = getScoreColor(rec.final_score);
    var timingClass = getTimingClass(rec.timing);
    var change = getRankChange(rec.ticker);
    var mktBadge = rec.market === 'kr' ? 'kr' : 'us';
    var mktLabel = rec.market === 'kr' ? 'KR' : 'US';

    var heat = rec.heat || {};
    var rsi = heat.rsi || 50;
    var heatLevel = rsi >= 70 ? 'overheat' : rsi <= 30 ? 'oversold' : 'neutral';
    var heatLabel = rsi >= 70 ? '\uACFC\uC5F4' : rsi <= 30 ? '\uACFC\uB9E4\uB3C4' : '\uBCF4\uD1B5';

    var chg5d = heat.price_change_5d || 0;
    var chg5dSign = chg5d >= 0 ? '+' : '';
    var chg5dColor = chg5d > 0 ? 'var(--green)' : chg5d < 0 ? 'var(--red)' : 'var(--text-muted)';
    var chg5dArrow = chg5d > 0 ? '\u25B2' : chg5d < 0 ? '\u25BC' : '';

    var changeHtml = renderRankChange(change);

    var eventsText = rec.upcoming_events || '';
    var eventsHtml = eventsText && eventsText !== '-'
      ? '<div class="rec-card-events">' + escapeHtml(eventsText) + '</div>'
      : '';

    html +=
      '<div class="rec-card fade-in" onclick="openDetail(' + idx + ')" style="animation-delay:' + idx * 20 + 'ms">' +
        '<div class="rec-card-top">' +
          '<div class="rec-card-left">' +
            '<div class="rec-card-rank">' + rec.rank + '</div>' +
            '<div class="rec-card-info">' +
              '<div class="rec-card-name">' +
                '<span class="market-badge ' + mktBadge + '">' + mktLabel + '</span>' +
                escapeHtml(rec.name) +
              '</div>' +
              '<div class="rec-card-sub">' +
                '<span class="ticker-copy" onclick="event.stopPropagation();copyTicker(\'' + escapeHtml(rec.ticker) + '\',\'' + (rec.market || 'us') + '\',this)">' +
                  escapeHtml(rec.ticker) +
                '</span>' +
                ' · <span class="heat-label ' + heatLevel + '">' + heatLabel + '</span>' +
                (rec.market_cap ? ' · <span class="mcap-label">' + formatMarketCap(rec.market_cap, rec.market) + '</span>' : '') +
              '</div>' +
            '</div>' +
          '</div>' +
          '<div class="rec-card-right">' +
            '<div class="rec-card-badges">' +
              '<span class="timing-badge ' + timingClass + '">' + escapeHtml(rec.timing) + '</span>' +
            '</div>' +
            '<div class="rec-card-score" style="color:' + scoreColor + '">' + rec.final_score.toFixed(1) + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="rec-card-bottom">' +
          '<div class="rec-card-theme">' + escapeHtml(rec.theme) + '</div>' +
          '<div class="rec-card-meta">' +
            '<span class="rec-card-change" style="color:' + chg5dColor + '">' + chg5dArrow + chg5dSign + Math.abs(chg5d).toFixed(0) + '%</span>' +
            changeHtml +
          '</div>' +
        '</div>' +
        eventsHtml +
      '</div>';
  }
  container.innerHTML = html;
}

function renderAvoid() {
  if (!state.data) return;
  var avoid = state.data.avoid || [];
  var el = document.getElementById('txt-avoid');
  if (el)
    el.textContent = avoid.length
      ? avoid.join(', ')
      : '\uC5C6\uC74C';
}

function renderFooter() {
  if (!state.data) return;
  var gen = state.data.generated_at || '';
  var timeStr = '';
  if (gen) {
    try {
      var d = new Date(gen);
      timeStr =
        d.getFullYear() +
        '.' +
        String(d.getMonth() + 1).padStart(2, '0') +
        '.' +
        String(d.getDate()).padStart(2, '0') +
        ' ' +
        String(d.getHours()).padStart(2, '0') +
        ':' +
        String(d.getMinutes()).padStart(2, '0') +
        ' KST';
    } catch (e) {
      timeStr = gen;
    }
  }

  var genEl = document.getElementById('footer-generated');
  if (genEl)
    genEl.textContent = timeStr
      ? '\uC0DD\uC131: ' + timeStr
      : '';

  var c = state.data.counts || {};
  var cntEl = document.getElementById('footer-counts');
  if (cntEl)
    cntEl.textContent =
      '\uAD6D\uC7A5 ' +
      (c.kr || 0) +
      '\uAC1C + \uBBF8\uC7A5 ' +
      (c.us || 0) +
      '\uAC1C = ' +
      (c.total || 0) +
      '\uAC1C';
}

// ── Detail Panel ───────────────────────────────────────────
function openDetail(index) {
  var recs = (state.data.recommendations || []).filter(function (r) {
    if (state.recFilter === 'all') return true;
    if (state.recFilter === 'kr') return r.market === 'kr';
    return r.market !== 'kr';
  });
  var rec = recs[index];
  if (!rec) return;

  var titleEl = document.getElementById('detail-title');
  if (titleEl) titleEl.textContent = rec.name + ' (' + rec.ticker + ')';

  var content = document.getElementById('detail-content');
  if (!content) return;

  var detail = rec.score_detail || {};
  var wTheme = (detail.theme || 0) * 0.3;
  var wChart = (detail.chart || 0) * 0.3;
  var wSupply = (detail.supply_demand || 0) * 0.2;
  var wFinancial = (detail.financial || 0) * 0.2;
  var total = wTheme + wChart + wSupply + wFinancial;
  var safeTotal = Math.max(total, 1);

  var mktClass = rec.market === 'kr' ? 'kr' : 'us';
  var mktLabel = rec.market === 'kr' ? 'KR' : 'US';

  // Chart links
  var tossUrl = rec.market === 'kr'
    ? 'https://tossinvest.com/stocks/A' + rec.ticker
    : 'https://tossinvest.com/stocks/' + rec.ticker;
  var tvSymbol = rec.market === 'kr' ? 'KRX:' + rec.ticker : rec.ticker;

  // ── Header: badge row
  var html =
    '<div class="detail-header-row">' +
    '<span class="market-badge ' + mktClass + '">' + mktLabel + '</span>' +
    '<span class="detail-score" style="color:' + getScoreColor(rec.final_score) + '">' + rec.final_score.toFixed(1) + '<small>/100</small></span>' +
    '<span class="timing-badge ' + getTimingClass(rec.timing) + '">' + escapeHtml(rec.timing) + '</span>' +
    '</div>';

  // ── Chart action buttons
  html +=
    '<div class="detail-chart-actions">' +
    '<a href="' + tossUrl + '" target="_blank" rel="noopener" class="detail-chart-btn toss">' +
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>' +
    '\uD1A0\uC2A4\uC99D\uAD8C</a>' +
    '<button onclick="event.stopPropagation();closeDetail();openTVChart(\'' + escapeHtml(tvSymbol) + '\',\'' + escapeHtml(rec.name) + '\')" class="detail-chart-btn tv">' +
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>' +
    '\uD2B8\uB808\uC774\uB529\uBDF0</button>' +
    '</div>';

  // ── 향후 일정 (맨 위 강조 카드)
  var evtText = rec.upcoming_events || '';
  var hasEvents = evtText && evtText !== '-' && evtText.indexOf('\uC608\uC815\uB41C \uC77C\uC815 \uC5C6\uC74C') === -1 && evtText.indexOf('\uC5C6\uC74C') === -1;
  html +=
    '<div class="detail-events-card ' + (hasEvents ? 'has-events' : 'no-events') + '">' +
    '<div class="detail-events-header">' +
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' +
    '<span>\uD5A5\uD6C4 \uC77C\uC815</span>' +
    '</div>' +
    '<p class="detail-events-body">' +
    (hasEvents ? escapeHtml(evtText) : '\uD655\uC778\uB41C \uC608\uC815 \uC77C\uC815 \uC5C6\uC74C') +
    '</p></div>';

  // ── Why 분석
  html += '<div class="detail-why-card"><p class="detail-why">' + escapeHtml(rec.why || '') + '</p></div>';

  // ── 매매 전략 카드
  html +=
    '<div class="detail-trade-card">' +
    '<p class="detail-section-label">\uB9E4\uB9E4 \uC804\uB7B5</p>' +
    '<div class="detail-trade-grid">' +
    '<div class="detail-trade-item"><span class="detail-trade-label">\uD14C\uB9C8</span><span class="detail-trade-value">' + escapeHtml(rec.theme) + '</span></div>' +
    '<div class="detail-trade-item"><span class="detail-trade-label">\uC720\uD615</span><span class="detail-trade-value type">' + escapeHtml(rec.trading_type) + '</span></div>' +
    '<div class="detail-trade-item entry"><span class="detail-trade-label">\uC9C4\uC785</span><span class="detail-trade-value">' + escapeHtml(rec.entry || '-') + '</span></div>' +
    '<div class="detail-trade-item stop"><span class="detail-trade-label">\uC190\uC808</span><span class="detail-trade-value">' + escapeHtml(rec.stop_loss || '-') + '</span></div>' +
    '<div class="detail-trade-item target"><span class="detail-trade-label">\uBAA9\uD45C</span><span class="detail-trade-value">' + escapeHtml(rec.target || '-') + '</span></div>' +
    '<div class="detail-trade-item risk"><span class="detail-trade-label">\uB9AC\uC2A4\uD06C</span><span class="detail-trade-value">' + escapeHtml(rec.risk || '-') + '</span></div>' +
    '</div></div>';

  // ── 점수 구성
  html +=
    '<div class="detail-section">' +
    '<p class="detail-section-label">\uC810\uC218 \uAD6C\uC131</p>' +
    '<div class="score-bar-container">' +
    '<div class="score-bar-segment" style="width:' + ((wTheme / safeTotal) * 100).toFixed(1) + '%;background:#3b82f6"></div>' +
    '<div class="score-bar-segment" style="width:' + ((wChart / safeTotal) * 100).toFixed(1) + '%;background:#8b5cf6"></div>' +
    '<div class="score-bar-segment" style="width:' + ((wSupply / safeTotal) * 100).toFixed(1) + '%;background:#06b6d4"></div>' +
    '<div class="score-bar-segment" style="width:' + ((wFinancial / safeTotal) * 100).toFixed(1) + '%;background:#22c55e"></div>' +
    '</div>' +
    '<div class="score-bar-labels">' +
    '<span style="color:#3b82f6">\uD14C\uB9C8 ' + (detail.theme || 0) + '</span>' +
    '<span style="color:#8b5cf6">\uCC28\uD2B8 ' + (detail.chart || 0) + '</span>' +
    '<span style="color:#06b6d4">\uC218\uAE09 ' + (detail.supply_demand || 0) + '</span>' +
    '<span style="color:#22c55e">\uC7AC\uBB34 ' + (detail.financial || 0) + '</span>' +
    (detail.dart_penalty ? '<span style="color:var(--red)">\uD328\uB110\uD2F0 ' + detail.dart_penalty + '</span>' : '') +
    '</div></div>';

  // ── 과열 지표 (비주얼)
  var heat = rec.heat || {};
  if (heat.rsi) {
    var rsi = heat.rsi;
    var rsiPct = Math.min(rsi, 100);
    var rsiColor = rsi >= 70 ? 'var(--red)' : rsi <= 30 ? 'var(--green)' : 'var(--text-muted)';
    var bbPct = ((heat.bb_pct || 0) * 100);
    var volR = (heat.volume_ratio || 1);
    var chg5 = heat.price_change_5d || 0;
    var chg20 = heat.price_change_20d || 0;

    html +=
      '<div class="detail-section">' +
      '<p class="detail-section-label">\uACFC\uC5F4 \uC9C0\uD45C</p>' +
      '<div class="detail-heat-grid">' +
      '<div class="detail-heat-item">' +
        '<div class="detail-heat-gauge"><svg viewBox="0 0 48 28" class="detail-gauge-svg">' +
        '<path d="M4 24 A20 20 0 0 1 44 24" fill="none" stroke="var(--border)" stroke-width="4" stroke-linecap="round"/>' +
        '<path d="M4 24 A20 20 0 0 1 44 24" fill="none" stroke="' + rsiColor + '" stroke-width="4" stroke-linecap="round" stroke-dasharray="' + (rsiPct * 0.628).toFixed(1) + ' 62.8" opacity="0.8"/>' +
        '</svg><span class="detail-gauge-val" style="color:' + rsiColor + '">' + rsi.toFixed(0) + '</span></div>' +
        '<span class="detail-heat-name">RSI(14)</span></div>' +
      '<div class="detail-heat-item">' +
        '<div class="detail-heat-num" style="color:' + (bbPct > 80 ? 'var(--red)' : bbPct < 20 ? 'var(--green)' : 'var(--text-secondary)') + '">' + bbPct.toFixed(0) + '<small>%</small></div>' +
        '<span class="detail-heat-name">\uBCFC\uB9B0\uC800</span></div>' +
      '<div class="detail-heat-item">' +
        '<div class="detail-heat-num" style="color:' + (volR > 2 ? 'var(--yellow)' : 'var(--text-secondary)') + '">' + volR.toFixed(1) + '<small>x</small></div>' +
        '<span class="detail-heat-name">\uAC70\uB798\uB7C9</span></div>' +
      '<div class="detail-heat-item">' +
        '<div class="detail-heat-num" style="color:' + (chg5 >= 0 ? 'var(--green)' : 'var(--red)') + '">' + (chg5 >= 0 ? '+' : '') + chg5.toFixed(1) + '<small>%</small></div>' +
        '<span class="detail-heat-name">5\uC77C</span></div>' +
      '<div class="detail-heat-item">' +
        '<div class="detail-heat-num" style="color:' + (chg20 >= 0 ? 'var(--green)' : 'var(--red)') + '">' + (chg20 >= 0 ? '+' : '') + chg20.toFixed(1) + '<small>%</small></div>' +
        '<span class="detail-heat-name">20\uC77C</span></div>' +
      '<div class="detail-heat-item">' +
        '<div class="detail-heat-num trend">' + escapeHtml(heat.trend || '-') + '</div>' +
        '<span class="detail-heat-name">\uCD94\uC138</span></div>' +
      '</div></div>';
  }

  // ── 애널리스트 의견
  if (rec.analyst_view) {
    html +=
      '<div class="detail-section">' +
      '<p class="detail-section-label">\uC560\uB110\uB9AC\uC2A4\uD2B8 \uC758\uACAC</p>' +
      '<p class="detail-events-text">' + escapeHtml(rec.analyst_view) + '</p>' +
      '</div>';
  }

  content.innerHTML = html;

  document.getElementById('detail-overlay').classList.remove('hidden');
  document.getElementById('detail-panel').classList.remove('hidden');
  requestAnimationFrame(function () {
    document.getElementById('detail-panel').classList.add('open');
  });
}

function closeDetail() {
  var panel = document.getElementById('detail-panel');
  if (panel) panel.classList.remove('open');
  setTimeout(function () {
    var overlay = document.getElementById('detail-overlay');
    if (overlay) overlay.classList.add('hidden');
    if (panel) panel.classList.add('hidden');
  }, 300);
}

// ── Theme Toggle ───────────────────────────────────────────
function toggleTheme() {
  state.isDark = !state.isDark;
  applyTheme();
}

function setTheme(isDark) {
  state.isDark = isDark;
  applyTheme();
}

function applyTheme() {
  document.documentElement.setAttribute(
    'data-theme',
    state.isDark ? 'dark' : 'light'
  );
  localStorage.setItem('theme', state.isDark ? 'dark' : 'light');

  var btnLight = document.getElementById('btn-light');
  var btnDark = document.getElementById('btn-dark');
  if (btnLight) btnLight.classList.toggle('active', !state.isDark);
  if (btnDark) btnDark.classList.toggle('active', state.isDark);

  // Fallback for old toggle button
  var icon = document.getElementById('icon-theme');
  if (icon) {
    icon.setAttribute('data-lucide', state.isDark ? 'moon' : 'sun');
  }
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ── Date Navigation ────────────────────────────────────────
// dates array is sorted newest first: [0]=newest, [last]=oldest
function navigateDate(direction) {
  var idx = state.dates.indexOf(state.currentDate);
  if (idx === -1) return;

  if (direction === -1) {
    // prev = older = higher index in the array
    if (idx < state.dates.length - 1) loadData(state.dates[idx + 1]);
  } else {
    // next = newer = lower index in the array
    if (idx > 0) loadData(state.dates[idx - 1]);
  }
}

// ── Event Listeners ────────────────────────────────────────
function setupListeners() {
  // Date select dropdown
  var selectDate = document.getElementById('select-date');
  if (selectDate) {
    selectDate.addEventListener('change', function (e) {
      loadData(e.target.value);
    });
  }

  // Date navigation buttons
  var btnPrev = document.getElementById('btn-prev-date');
  if (btnPrev) {
    btnPrev.addEventListener('click', function () {
      navigateDate(-1);
    });
  }
  var btnNext = document.getElementById('btn-next-date');
  if (btnNext) {
    btnNext.addEventListener('click', function () {
      navigateDate(1);
    });
  }

  // Macro manual refresh
  var btnMacroRefresh = document.getElementById('btn-macro-refresh');
  if (btnMacroRefresh) {
    btnMacroRefresh.addEventListener('click', function () { refreshMacro(); });
  }

  // Theme toggle (legacy single button)
  var btnTheme = document.getElementById('btn-theme');
  if (btnTheme) {
    btnTheme.addEventListener('click', toggleTheme);
  }
  // Theme toggle (new light/dark buttons)
  var btnLight = document.getElementById('btn-light');
  var btnDark = document.getElementById('btn-dark');
  if (btnLight) btnLight.addEventListener('click', function () { setTheme(false); });
  if (btnDark) btnDark.addEventListener('click', function () { setTheme(true); });

  // Theme filter tabs
  document.querySelectorAll('.theme-tab').forEach(function (btn) {
    btn.addEventListener('click', function () {
      state.themeFilter = btn.dataset.filter;
      document.querySelectorAll('.theme-tab').forEach(function (b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
      renderThemes();
    });
  });

  // Recommendation filter tabs
  document.querySelectorAll('.rec-tab').forEach(function (btn) {
    btn.addEventListener('click', function () {
      state.recFilter = btn.dataset.filter;
      document.querySelectorAll('.rec-tab').forEach(function (b) {
        b.classList.remove('active');
      });
      btn.classList.add('active');
      renderRecommendations();
    });
  });

  // Detail overlay click to close
  var overlay = document.getElementById('detail-overlay');
  if (overlay) {
    overlay.addEventListener('click', closeDetail);
  }


  // Keyboard: Escape closes detail panel
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeDetail();
  });

  // News market tabs
  document.querySelectorAll('.news-tab').forEach(function (btn) {
    btn.addEventListener('click', function () {
      document.querySelectorAll('.news-tab').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      renderNews(btn.dataset.market);
    });
  });

  // Page tabs (시장 개요 / 종목 추천)
  document.querySelectorAll('.page-tab').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var page = btn.dataset.page;
      document.querySelectorAll('.page-tab').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      document.getElementById('page-overview').classList.toggle('hidden', page !== 'overview');
      var globeEl = document.getElementById('page-globe');
      if (globeEl) globeEl.classList.toggle('hidden', page !== 'globe');
      var nfEl = document.getElementById('page-newsfeed');
      if (nfEl) nfEl.classList.toggle('hidden', page !== 'newsfeed');
      document.getElementById('page-picks').classList.toggle('hidden', page !== 'picks');
      var chEl = document.getElementById('page-channels');
      if (chEl) chEl.classList.toggle('hidden', page !== 'channels');
      var abEl = document.getElementById('page-about');
      if (abEl) abEl.classList.toggle('hidden', page !== 'about');
    });
  });

  // Theme section collapse toggle
  var btnToggleThemes = document.getElementById('btn-toggle-themes');
  if (btnToggleThemes) {
    btnToggleThemes.addEventListener('click', function () {
      var list = document.getElementById('theme-list');
      var icon = document.getElementById('icon-themes-toggle');
      var tabs = document.getElementById('theme-tabs');
      list.classList.toggle('collapsed');
      icon.classList.toggle('rotated');
      if (tabs) tabs.classList.toggle('hidden', list.classList.contains('collapsed'));
    });
  }
}

// ── Init / Bootstrap ───────────────────────────────────────
async function init() {
  // Restore theme preference from localStorage
  var savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'light') {
    state.isDark = false;
  }
  applyTheme();

  setupListeners();

  try {
    var resp = await fetch('data/dates.json');
    if (!resp.ok) throw new Error('dates.json not found');
    var idx = await resp.json();
    state.dates = idx.dates || [];

    // Populate date select dropdown
    var sel = document.getElementById('select-date');
    if (sel) {
      sel.innerHTML = state.dates
        .map(function (d) {
          return '<option value="' + d + '">' + formatDate(d) + '</option>';
        })
        .join('');
    }

    if (idx.latest) {
      await loadData(idx.latest);
    } else if (state.dates.length > 0) {
      await loadData(state.dates[0]);
    } else {
      showError(
        '\uB9AC\uD3EC\uD2B8 \uB370\uC774\uD130\uAC00 \uC5C6\uC2B5\uB2C8\uB2E4. \uD30C\uC774\uD504\uB77C\uC778\uC744 \uBA3C\uC800 \uC2E4\uD589\uD558\uC138\uC694.'
      );
    }
  } catch (e) {
    showError(
      '\uB370\uC774\uD130\uB97C \uBD88\uB7EC\uC62C \uC218 \uC5C6\uC2B5\uB2C8\uB2E4: ' +
        e.message
    );
  }

  if (typeof lucide !== 'undefined') lucide.createIcons();
}

document.addEventListener('DOMContentLoaded', init);

// ── Real-time macro update (30s interval, yfinance, $0) ──
var macroRefreshTimer = null;

function updateLiveBadge() {
  var badge = document.getElementById('badge-live');
  if (!badge) return;
  if (macroRefreshTimer || newsRefreshTimer) {
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }
}

function startMacroRefresh() {
  if (macroRefreshTimer) return;
  refreshMacro();
  macroRefreshTimer = setInterval(refreshMacro, 30000);
  updateLiveBadge();
}

function stopMacroRefresh() {
  if (macroRefreshTimer) {
    clearInterval(macroRefreshTimer);
    macroRefreshTimer = null;
  }
  updateLiveBadge();
}

function refreshMacro() {
  var btn = document.getElementById('btn-macro-refresh');
  if (btn) btn.classList.add('spinning');

  fetch('/api/macro')
    .then(function (res) {
      if (!res.ok) return;
      return res.json();
    })
    .then(function (data) {
      if (!data || !state.data) return;
      state.data.macro = data;
      try { renderMacro(); } catch(e) { /* ignore */ }
      // 갱신 시각 표시
      var el = document.getElementById('macro-updated');
      if (el) {
        var now = new Date();
        el.textContent = '매크로 갱신: ' +
          now.getHours().toString().padStart(2,'0') + ':' +
          now.getMinutes().toString().padStart(2,'0') + ':' +
          now.getSeconds().toString().padStart(2,'0') + ' (30초 자동)';
      }
    })
    .catch(function () { /* silent fail */ })
    .finally(function () {
      if (btn) btn.classList.remove('spinning');
    });
}

// ── 실시간 속보 피드 (30초 폴링, RSS, $0) ──────────────────
var newsRefreshTimer = null;
var newsLiveItems = [];
var newsSourceFilter = 'all';
var newsLangKo = false;
var newsTranslations = {};

function startNewsRefresh() {
  if (newsRefreshTimer) return;
  refreshNewsLive();
  newsRefreshTimer = setInterval(refreshNewsLive, 30000);
  updateLiveBadge();
}

function stopNewsRefresh() {
  if (newsRefreshTimer) {
    clearInterval(newsRefreshTimer);
    newsRefreshTimer = null;
  }
  updateLiveBadge();
}

function refreshNewsLive() {
  var statusEl = document.getElementById('news-live-status');
  if (statusEl) statusEl.textContent = '갱신 중…';

  fetch('/api/news/live')
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (data) {
      if (!data || !data.items) return;
      newsLiveItems = data.items;
      renderNewsLive();
      if (statusEl) {
        var now = new Date();
        statusEl.textContent = now.getHours().toString().padStart(2,'0') + ':' +
          now.getMinutes().toString().padStart(2,'0') + ':' +
          now.getSeconds().toString().padStart(2,'0') + ' 갱신';
      }
    })
    .catch(function () {
      if (statusEl) statusEl.textContent = '갱신 실패';
    });
}

function newsTimeAgo(published, ts) {
  // ts(Unix초)가 있으면 그걸로 계산, 없으면 빈 문자열
  if (!ts || ts <= 0) return '';
  var diff = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (diff < 60) return '방금 전';
  if (diff < 3600) return Math.floor(diff / 60) + '분 전';
  if (diff < 86400) return Math.floor(diff / 3600) + '시간 전';
  return Math.floor(diff / 86400) + '일 전';
}

function renderNewsLive() {
  var container = document.getElementById('news-live-list');
  var countEl = document.getElementById('news-live-count');
  if (!container) return;

  var items = newsSourceFilter === 'all'
    ? newsLiveItems
    : newsLiveItems.filter(function (i) { return i.source === newsSourceFilter; });

  if (countEl) countEl.textContent = '(' + items.length + '건)';

  if (items.length === 0) {
    container.innerHTML = '<p class="text-gray-500 text-sm py-8 text-center">뉴스가 없습니다.</p>';
    return;
  }

  var SOURCE_COLORS = {
    Reuters: 'text-orange-400',
    Bloomberg: 'text-purple-400',
    CNBC: 'text-blue-400',
    WSJ: 'text-amber-300',
    MarketWatch: 'text-green-400',
    Investing: 'text-emerald-400',
    Fed: 'text-yellow-400',
  };

  var html = items.map(function (item) {
    var srcClass = SOURCE_COLORS[item.source] || 'text-gray-400';
    var ago = newsTimeAgo(item.published, item.ts);
    var timeStr = item.published || '';
    var displayTitle = (newsLangKo && newsTranslations[item.id])
      ? newsTranslations[item.id]
      : item.title;
    return (
      '<a href="' + item.link + '" target="_blank" rel="noopener" ' +
        'class="block rounded-lg border border-gray-800 bg-gray-900/50 px-4 py-3 hover:border-gray-600 hover:bg-gray-900 transition">' +
        '<div class="flex items-start justify-between gap-3">' +
          '<div class="flex-1 min-w-0">' +
            '<p class="text-sm font-medium text-gray-200 leading-snug">' + escapeHtml(displayTitle) + '</p>' +
            (item.summary ? '<p class="text-xs text-gray-500 mt-1 line-clamp-1">' + escapeHtml(item.summary) + '</p>' : '') +
          '</div>' +
          '<div class="shrink-0 text-right">' +
            '<span class="text-[11px] font-semibold ' + srcClass + '">' + item.source + '</span>' +
            (ago ? '<br><span class="text-[11px] text-blue-400 font-medium">' + ago + '</span>' : '') +
            (timeStr ? '<br><span class="text-[10px] text-gray-600">' + timeStr + '</span>' : '') +
          '</div>' +
        '</div>' +
      '</a>'
    );
  }).join('');

  container.innerHTML = html;
}

// 소스 탭 클릭
document.addEventListener('click', function (e) {
  var tab = e.target.closest('.news-src-tab');
  if (!tab) return;
  newsSourceFilter = tab.getAttribute('data-src');
  document.querySelectorAll('.news-src-tab').forEach(function (t) {
    if (t.getAttribute('data-src') === newsSourceFilter) {
      t.classList.add('active', 'bg-gray-800', 'text-gray-300');
      t.classList.remove('text-gray-500');
    } else {
      t.classList.remove('active', 'bg-gray-800', 'text-gray-300');
      t.classList.add('text-gray-500');
    }
  });
  renderNewsLive();
});

// 한국어 번역 토글
document.addEventListener('click', function (e) {
  if (!e.target.closest('#btn-news-lang')) return;
  var btn = document.getElementById('btn-news-lang');
  if (newsLangKo) {
    // 영어로 복귀
    newsLangKo = false;
    btn.textContent = '한국어';
    btn.classList.remove('bg-blue-600', 'border-blue-500', 'text-white');
    renderNewsLive();
  } else {
    // 번역 요청
    btn.textContent = '번역 중…';
    btn.classList.add('opacity-50');
    fetch('/api/news/translate')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.translations) newsTranslations = data.translations;
        newsLangKo = true;
        btn.textContent = 'English';
        btn.classList.remove('opacity-50');
        btn.classList.add('bg-blue-600', 'border-blue-500', 'text-white');
        renderNewsLive();
      })
      .catch(function () {
        btn.textContent = '한국어';
        btn.classList.remove('opacity-50');
      });
  }
});

// HTML escape helper (skip if already defined above)
if (typeof escapeHtml === 'undefined') {
  // already defined earlier in file
}
function escapeHtml(str) {
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

// 탭 전환 시 매크로/속보 자동 시작/정지
document.addEventListener('click', function (e) {
  var tab = e.target.closest('.page-tab');
  if (!tab) return;
  var page = tab.getAttribute('data-page');
  if (page === 'overview') {
    startMacroRefresh();
  } else {
    stopMacroRefresh();
  }
  if (page === 'newsfeed') {
    startNewsRefresh();
  } else {
    stopNewsRefresh();
  }
});

// ── AI 분석 탭 비밀번호 잠금 ──────────────────────────────
(function () {
  var PICKS_PW = '2759';
  var unlocked = false;

  function applyLockState() {
    var lock = document.getElementById('picks-lock');
    var content = document.getElementById('picks-content');
    if (!lock || !content) return;
    if (unlocked) {
      lock.classList.add('hidden');
      content.classList.add('unlocked');
    } else {
      lock.classList.remove('hidden');
      content.classList.remove('unlocked');
    }
  }

  function tryUnlock() {
    var input = document.getElementById('picks-pw');
    var err = document.getElementById('picks-pw-err');
    if (!input) return;
    if (input.value === PICKS_PW) {
      unlocked = true;
      applyLockState();
    } else {
      if (err) err.classList.remove('hidden');
      input.value = '';
      input.focus();
    }
  }

  document.addEventListener('click', function (e) {
    if (e.target.closest('#picks-pw-btn')) tryUnlock();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && document.activeElement && document.activeElement.id === 'picks-pw') tryUnlock();
  });

  // 페이지 로드 시 상태 적용
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applyLockState);
  } else {
    applyLockState();
  }
})();

// ── AI 종목 집중분석 모달 (폴링 방식 + 히스토리) ──────────

var deepPollTimer = null;

function openDeepAnalyze() {
  document.getElementById('deep-overlay').classList.remove('hidden');
  document.getElementById('deep-modal').classList.remove('hidden');
  var input = document.getElementById('deep-query');
  if (input) { input.value = ''; input.focus(); }
  loadDeepHistory();
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function closeDeepAnalyze() {
  document.getElementById('deep-overlay').classList.add('hidden');
  document.getElementById('deep-modal').classList.add('hidden');
  if (deepPollTimer) { clearInterval(deepPollTimer); deepPollTimer = null; }
}

var deepAnalyzing = false;

function setDeepLock(locked) {
  deepAnalyzing = locked;
  var btn = document.getElementById('deep-search-btn');
  var input = document.getElementById('deep-query');
  if (btn) {
    btn.disabled = locked;
    btn.style.opacity = locked ? '0.4' : '1';
    btn.style.pointerEvents = locked ? 'none' : 'auto';
  }
  if (input) {
    input.disabled = locked;
    input.style.opacity = locked ? '0.5' : '1';
  }
}

function runDeepAnalyze() {
  if (deepAnalyzing) return;
  var input = document.getElementById('deep-query');
  var resultEl = document.getElementById('deep-result');
  if (!input || !resultEl) return;
  var query = input.value.trim();
  if (!query) return;

  // 확인 팝업
  if (!confirm(query + ' AI 집중분석을 시작할까요?')) return;

  // 분석 중 잠금
  setDeepLock(true);

  resultEl.innerHTML =
    '<div class="deep-loading">' +
      '<div class="deep-loading-spinner"></div>' +
      '<p class="text-sm text-gray-400">AI가 <strong>' + escapeHtml(query) + '</strong>을(를) 분석 중...</p>' +
      '<p class="text-xs text-gray-600 mt-2">WebSearch + 종합 분석 (30초~2분 소요)</p>' +
      '<p class="text-xs text-gray-600">새로고침해도 백그라운드에서 계속 진행되며, 완료 후 기록에서 확인 가능합니다.</p>' +
    '</div>';

  fetch('/api/stock/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: query }),
  })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) {
        resultEl.innerHTML = '<div class="text-center py-8"><p class="text-red-400 text-sm">' + escapeHtml(data.error) + '</p></div>';
        setDeepLock(false);
        return;
      }
      if (data.task_id) {
        pollDeepResult(data.task_id, resultEl, query);
      }
    })
    .catch(function (err) {
      resultEl.innerHTML = '<div class="text-center py-8"><p class="text-red-400 text-sm">요청 실패: ' + escapeHtml(err.message) + '</p></div>';
      setDeepLock(false);
    });
}

function pollDeepResult(taskId, resultEl, query) {
  if (deepPollTimer) clearInterval(deepPollTimer);
  var elapsed = 0;
  deepPollTimer = setInterval(function () {
    elapsed += 3;
    var loadingP = resultEl.querySelector('.deep-loading p:first-of-type');
    if (loadingP) {
      loadingP.innerHTML = 'AI가 <strong>' + escapeHtml(query) + '</strong>을(를) 분석 중... (' + elapsed + '초)';
    }

    fetch('/api/stock/analyze/' + taskId)
      .then(function (r) { return r.json(); })
      .then(function (task) {
        if (task.status === 'done') {
          clearInterval(deepPollTimer);
          deepPollTimer = null;
          setDeepLock(false);
          renderDeepResult(resultEl, task.result);
          loadDeepHistory();
        } else if (task.status === 'error') {
          clearInterval(deepPollTimer);
          deepPollTimer = null;
          setDeepLock(false);
          resultEl.innerHTML = '<div class="text-center py-8"><p class="text-red-400 text-sm">' + escapeHtml(task.error || '분석 실패') + '</p></div>';
        }
      })
      .catch(function () { /* 다음 폴링에서 재시도 */ });
  }, 3000);
}

function renderDeepResult(container, d) {
  var html = '';

  html += '<div class="deep-header">';
  html += '<span class="deep-ticker">' + escapeHtml(d.ticker || '') + '</span>';
  html += '<span class="deep-name">' + escapeHtml(d.name || '') + '</span>';
  if (d.current_price) html += '<span class="deep-price">' + escapeHtml(d.current_price) + '</span>';
  html += '</div>';

  if (d.summary) {
    html += '<div class="deep-summary">' + escapeHtml(d.summary) + '</div>';
  }

  var hasAnalystTable = d.analyst_ratings && d.analyst_ratings.length;

  if (d.main_analysis && d.main_analysis.length) {
    html += '<div class="deep-section-title"><i data-lucide="briefcase" class="w-4 h-4"></i> 주요 정보</div>';
    html += '<table class="deep-table"><thead><tr><th>분석 요소</th><th>분석 결과</th></tr></thead><tbody>';
    d.main_analysis.forEach(function (item) {
      var isAnalyst = item.category.indexOf('애널리스트') >= 0;
      html += '<tr><td>' + escapeHtml(item.category) + '</td><td>' + escapeHtml(item.result);
      if (isAnalyst && hasAnalystTable) {
        html += ' <button class="analyst-toggle-btn" onclick="toggleAnalystTable()">요약표 보기</button>';
      }
      html += '</td></tr>';
    });
    html += '</tbody></table>';
  }

  // 애널리스트 상세 테이블 (접힌 상태)
  if (hasAnalystTable) {
    html += '<div id="analyst-detail-table" class="analyst-detail hidden">';
    html += '<div class="deep-section-title"><i data-lucide="users" class="w-4 h-4"></i> 애널리스트 상세 (최근 1~2개월)</div>';
    html += '<table class="deep-table analyst-table"><thead><tr>' +
      '<th>날짜</th><th>투자기관</th><th>목표주가</th><th>의견</th><th>코멘트</th>' +
      '</tr></thead><tbody>';
    d.analyst_ratings.forEach(function (r) {
      html += '<tr>' +
        '<td class="mono">' + escapeHtml(r.date || '') + '</td>' +
        '<td>' + escapeHtml(r.firm || '') + '</td>' +
        '<td class="mono">' + escapeHtml(r.target || '') + '</td>' +
        '<td><span class="analyst-rating-badge">' + escapeHtml(r.rating || '') + '</span></td>' +
        '<td>' + escapeHtml(r.comment || '') + '</td>' +
        '</tr>';
    });
    html += '</tbody></table></div>';
  }

  if (d.swing_analysis && d.swing_analysis.length) {
    html += '<div class="deep-section-title"><i data-lucide="zap" class="w-4 h-4"></i> 단타 정보</div>';
    html += '<table class="deep-table"><thead><tr><th>분석 요소</th><th>분석 결과</th></tr></thead><tbody>';
    d.swing_analysis.forEach(function (item) {
      html += '<tr><td>' + escapeHtml(item.category) + '</td><td>' + escapeHtml(item.result) + '</td></tr>';
    });
    html += '</tbody></table>';
  }

  if (d.verify) {
    html += '<div class="deep-section-title"><i data-lucide="shield-check" class="w-4 h-4"></i> 수급 검증 (Verify)</div>';
    html += '<div class="deep-verify">' + escapeHtml(d.verify) + '</div>';
  }

  if (d._analyzed_at) {
    html += '<p class="text-[11px] text-gray-600 mt-3 text-right">분석 시각: ' + escapeHtml(d._analyzed_at) + '</p>';
  }

  container.innerHTML = html;
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

function toggleAnalystTable() {
  var el = document.getElementById('analyst-detail-table');
  var btn = document.querySelector('.analyst-toggle-btn');
  if (!el) return;
  el.classList.toggle('hidden');
  if (btn) btn.textContent = el.classList.contains('hidden') ? '요약표 보기' : '요약표 닫기';
}

// ── 분석 히스토리 ────────────────────────────────────────

function loadDeepHistory() {
  var sidebar = document.getElementById('deep-history');
  if (!sidebar) return;

  fetch('/api/stock/history')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!data.dates || !data.dates.length) {
        sidebar.innerHTML = '<p class="text-xs text-gray-600 p-3">분석 기록이 없습니다.</p>';
        return;
      }
      var html = '';
      data.dates.forEach(function (day) {
        var label = day.date.slice(0,4) + '.' + day.date.slice(4,6) + '.' + day.date.slice(6,8);
        html += '<div class="deep-hist-date">' + label + '</div>';
        day.items.forEach(function (item) {
          html += '<div class="deep-hist-item" onclick="loadDeepHistoryItem(\'' + day.date + '\',\'' + escapeHtml(item.filename) + '\')">';
          html += '<span class="deep-hist-ticker">' + escapeHtml(item.ticker) + '</span>';
          html += '<span class="deep-hist-name">' + escapeHtml(item.name) + '</span>';
          html += '<span class="deep-hist-time">' + escapeHtml((item.analyzed_at || '').slice(11,16)) + '</span>';
          html += '</div>';
        });
      });
      sidebar.innerHTML = html;
    })
    .catch(function () {
      sidebar.innerHTML = '<p class="text-xs text-gray-600 p-3">기록 로드 실패</p>';
    });
}

function loadDeepHistoryItem(date, filename) {
  var resultEl = document.getElementById('deep-result');
  if (!resultEl) return;
  resultEl.innerHTML = '<div class="deep-loading"><div class="deep-loading-spinner"></div><p class="text-sm text-gray-400">로딩 중...</p></div>';

  fetch('/api/stock/history/' + date + '/' + filename)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) {
        resultEl.innerHTML = '<div class="text-center py-8"><p class="text-red-400 text-sm">' + escapeHtml(data.error) + '</p></div>';
        return;
      }
      renderDeepResult(resultEl, data);
    })
    .catch(function (err) {
      resultEl.innerHTML = '<div class="text-center py-8"><p class="text-red-400 text-sm">로드 실패</p></div>';
    });
}

// 이벤트 바인딩
document.addEventListener('click', function (e) {
  if (e.target.closest('#btn-deep-analyze')) openDeepAnalyze();
  if (e.target.closest('#deep-search-btn')) runDeepAnalyze();
});
document.addEventListener('keydown', function (e) {
  if (e.key === 'Enter' && document.activeElement && document.activeElement.id === 'deep-query') runDeepAnalyze();
  if (e.key === 'Escape') closeDeepAnalyze();
});
