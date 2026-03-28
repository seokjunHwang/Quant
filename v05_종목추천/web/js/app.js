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
  vix: 'TVC:VIX',
  sp500: 'FOREXCOM:SPXUSD',
  nasdaq: 'FOREXCOM:NSXUSD',
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

function openTVChart(symbol, title) {
  document.getElementById('tv-title').textContent = title;
  document.getElementById('tv-overlay').classList.remove('hidden');
  document.getElementById('tv-modal').classList.remove('hidden');
  loadTVWidget(symbol, currentTVTimeframe);
  lucide.createIcons();
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
    showError(e.message);
  }
}

// ── Rendering ──────────────────────────────────────────────
function render() {
  renderMacro();
  renderStrategy();
  renderSummary();
  renderThemes();
  renderRecommendations();
  renderAvoid();
  renderFooter();
}

function renderMacro() {
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
      '<div class="macro-card fade-in' + (tvSymbol ? ' clickable' : '') + '"' +
      (tvSymbol ? ' onclick="openTVChart(\'' + tvSymbol + '\',\'' + escapeHtml(name) + '\')"' : '') +
      '>' +
      '<div class="label">' +
      escapeHtml(name) +
      (tvSymbol ? ' <span class="tv-hint">chart</span>' : '') +
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
      '</div>';
  }

  container.innerHTML = html;
}

function renderStrategy() {
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

function renderRecommendations() {
  var recs = state.data.recommendations || [];
  var filtered = recs.filter(function (r) {
    if (state.recFilter === 'all') return true;
    if (state.recFilter === 'kr') return r.market === 'kr';
    return r.market !== 'kr';
  });

  var countEl = document.getElementById('rec-count');
  if (countEl) countEl.textContent = '(' + filtered.length + '\uAC1C)';

  var tbody = document.getElementById('rec-table-body');
  if (!tbody) return;
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
    var heatLabel = rsi >= 70 ? '과열' : rsi <= 30 ? '과매도' : '보통';

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
      '<span class="ticker-copy" onclick="event.stopPropagation();copyTicker(\'' + escapeHtml(rec.ticker) + '\',\'' + (rec.market || 'us') + '\',this)" title="클릭 → 복사 + 토스/트뷰">' +
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

function renderAvoid() {
  var avoid = state.data.avoid || [];
  var el = document.getElementById('txt-avoid');
  if (el)
    el.textContent = avoid.length
      ? avoid.join(', ')
      : '\uC5C6\uC74C';
}

function renderFooter() {
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

  var html =
    '<div class="detail-header-row">' +
    '<span class="market-badge ' +
    mktClass +
    '">' +
    mktLabel +
    '</span>' +
    '<span class="score-value" style="color:' +
    getScoreColor(rec.final_score) +
    '">' +
    rec.final_score.toFixed(1) +
    '</span>' +
    '<span class="timing-badge ' +
    getTimingClass(rec.timing) +
    '">' +
    escapeHtml(rec.timing) +
    '</span>' +
    '</div>';

  html +=
    '<p class="detail-why">' + escapeHtml(rec.why || '') + '</p>';

  html +=
    '<div class="detail-section">' +
    '<dl class="detail-grid">' +
    '<dt>\uD14C\uB9C8</dt><dd>' +
    escapeHtml(rec.theme) +
    '</dd>' +
    '<dt>\uC720\uD615</dt><dd>' +
    escapeHtml(rec.trading_type) +
    '</dd>' +
    '<dt>\uC9C4\uC785</dt><dd>' +
    escapeHtml(rec.entry || '-') +
    '</dd>' +
    '<dt>\uC190\uC808</dt><dd>' +
    escapeHtml(rec.stop_loss || '-') +
    '</dd>' +
    '<dt>\uBAA9\uD45C</dt><dd>' +
    escapeHtml(rec.target || '-') +
    '</dd>' +
    '<dt>\uB9AC\uC2A4\uD06C</dt><dd>' +
    escapeHtml(rec.risk || '-') +
    '</dd>' +
    '</dl>' +
    '</div>';

  html +=
    '<div class="detail-section">' +
    '<p class="detail-section-label">\uC810\uC218 \uAD6C\uC131</p>' +
    '<div class="score-bar-container">' +
    '<div class="score-bar-segment" style="width:' +
    ((wTheme / safeTotal) * 100).toFixed(1) +
    '%;background:#3b82f6" title="\uD14C\uB9C8 ' +
    (detail.theme || 0) +
    '"></div>' +
    '<div class="score-bar-segment" style="width:' +
    ((wChart / safeTotal) * 100).toFixed(1) +
    '%;background:#8b5cf6" title="\uCC28\uD2B8 ' +
    (detail.chart || 0) +
    '"></div>' +
    '<div class="score-bar-segment" style="width:' +
    ((wSupply / safeTotal) * 100).toFixed(1) +
    '%;background:#06b6d4" title="\uC218\uAE09 ' +
    (detail.supply_demand || 0) +
    '"></div>' +
    '<div class="score-bar-segment" style="width:' +
    ((wFinancial / safeTotal) * 100).toFixed(1) +
    '%;background:#22c55e" title="\uC7AC\uBB34 ' +
    (detail.financial || 0) +
    '"></div>' +
    '</div>' +
    '<div class="score-bar-labels">' +
    '<span style="color:#3b82f6">\uD14C\uB9C8 ' +
    (detail.theme || 0) +
    '</span>' +
    '<span style="color:#8b5cf6">\uCC28\uD2B8 ' +
    (detail.chart || 0) +
    '</span>' +
    '<span style="color:#06b6d4">\uC218\uAE09 ' +
    (detail.supply_demand || 0) +
    '</span>' +
    '<span style="color:#22c55e">\uC7AC\uBB34 ' +
    (detail.financial || 0) +
    '</span>' +
    (detail.dart_penalty
      ? '<span style="color:var(--red)">\uD328\uB110\uD2F0 ' +
        detail.dart_penalty +
        '</span>'
      : '') +
    '</div>' +
    '</div>';

  // 과열 지표
  var heat = rec.heat || {};
  if (heat.rsi) {
    var rsi = heat.rsi;
    var heatLevel = rsi >= 70 ? 'overheat' : rsi <= 30 ? 'oversold' : 'neutral';
    html +=
      '<div class="detail-section">' +
      '<p class="detail-section-label">과열 지표</p>' +
      '<dl class="detail-grid">' +
      '<dt>RSI(14)</dt><dd><span class="heat-label ' + heatLevel + '">' + rsi.toFixed(1) + '</span></dd>' +
      '<dt>볼린저 위치</dt><dd>' + ((heat.bb_pct || 0) * 100).toFixed(0) + '% (0=하단, 100=상단)</dd>' +
      '<dt>추세</dt><dd>' + escapeHtml(heat.trend || '-') + '</dd>' +
      '<dt>거래량 비율</dt><dd>' + (heat.volume_ratio || 1).toFixed(1) + 'x (20일 대비)</dd>' +
      '<dt>5일 등락</dt><dd style="color:' + ((heat.price_change_5d || 0) >= 0 ? 'var(--green)' : 'var(--red)') + '">' + (heat.price_change_5d >= 0 ? '+' : '') + (heat.price_change_5d || 0).toFixed(1) + '%</dd>' +
      '<dt>20일 등락</dt><dd style="color:' + ((heat.price_change_20d || 0) >= 0 ? 'var(--green)' : 'var(--red)') + '">' + (heat.price_change_20d >= 0 ? '+' : '') + (heat.price_change_20d || 0).toFixed(1) + '%</dd>' +
      '</dl></div>';
  }

  // 애널리스트 목표주가
  if (rec.analyst_view) {
    html +=
      '<div class="detail-section">' +
      '<p class="detail-section-label">애널리스트 의견</p>' +
      '<p class="detail-events-text">' + escapeHtml(rec.analyst_view) + '</p>' +
      '</div>';
  }

  // 향후 일정
  if (rec.upcoming_events) {
    html +=
      '<div class="detail-section">' +
      '<p class="detail-section-label">향후 일정</p>' +
      '<p class="detail-events-text">' +
      escapeHtml(rec.upcoming_events) +
      '</p>' +
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
  document.documentElement.setAttribute(
    'data-theme',
    state.isDark ? 'dark' : 'light'
  );
  localStorage.setItem('theme', state.isDark ? 'dark' : 'light');

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

  // Theme toggle
  var btnTheme = document.getElementById('btn-theme');
  if (btnTheme) {
    btnTheme.addEventListener('click', toggleTheme);
  }

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
      document.getElementById('page-picks').classList.toggle('hidden', page !== 'picks');
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
    document.documentElement.setAttribute('data-theme', 'light');
    var iconTheme = document.getElementById('icon-theme');
    if (iconTheme) iconTheme.setAttribute('data-lucide', 'sun');
  }

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
