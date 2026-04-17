/* =========================================================
   Economic YouTube Channels - channel.js
   LIVE + VOD → 공유 패널, 탭 사이 시각적 구분선
   ========================================================= */

var CHANNELS = [
  // Live 24h streams
  { name: 'Bloomberg', channelId: 'UCIALMKvObZNtJ6AmdCLP7Lg', type: 'live', lang: 'en' },
  { name: 'CNBC', channelId: 'UCvJJ_dzjViJCoLf5uKUTwoA', type: 'live', lang: 'en' },
  { name: 'Sky News', channelId: 'UCoMdktPbSTixAyNGwb-UYkQ', type: 'live', lang: 'en', liveVideoId: 'LNdCC6hs8kI' },
  { name: 'Al Jazeera', channelId: 'UCNye-wNBqNL5ZzHSJj3l8Bg', type: 'live', lang: 'en' },
  { name: '\uD55C\uAD6D\uACBD\uC81CTV', channelId: 'UCF8AeLlUbEpKju6v1H6p8Eg', type: 'live', lang: 'ko' },
  { name: '\uC5F0\uD569\uB274\uC2A4TV', channelId: 'UCTHCOPwqNfZ0uiKOvFyhGwg', type: 'live', lang: 'ko' },
  { name: 'YTN', channelId: 'UChlgI3UHCOnwUGzWzbJ3H5w', type: 'live', lang: 'ko' },
  // VOD channels
  { name: '\uACBD\uC81C\uC0AC\uB0E5\uAFBC', channelId: 'UC7usMJDHmtbs_oegmzQKKMA', type: 'vod', lang: 'ko' },
  { name: '\uBC18\uAD50\uC218', channelId: 'UCczff_dQVVb9sSEULFUJ-sw', type: 'vod', lang: 'ko' },
  { name: '\uC18C\uC218\uBABD\uD0A4', channelId: 'UCC3yfxS5qC6PCwDzetUuEWg', type: 'vod', lang: 'ko' },
  { name: '\uBBF8\uB798\uB294\uC9C0\uAE08', channelId: 'UC_JJ_NhRqPKcIOj5Ko3W_3w', type: 'vod', lang: 'ko' },
  { name: 'SBS \uC2A4\uBE0C\uC2A4\uB274\uC2A4', channelId: 'UChY8VUjXv0aA7RF9hDQ0ISg', type: 'vod', lang: 'ko' },
];

var chState = {
  currentChannel: 0,
  videos: [],
  currentVideo: null,
  loaded: false,
};

function fetchRSS(channelId) {
  return fetch('/api/youtube/rss/' + channelId)
    .then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.text();
    });
}

function fetchChannelVideos(channelIndex) {
  var ch = CHANNELS[channelIndex];
  if (!ch) return;

  chState.currentChannel = channelIndex;
  chState.loaded = true;

  var listEl = document.getElementById('ch-video-list');
  var player = document.getElementById('ch-player');
  var info = document.getElementById('ch-now-info');

  if (ch.type === 'live') {
    if (player) player.innerHTML = '<div class="ch-player-placeholder">\uB77C\uC774\uBE0C \uB85C\uB529 \uC911...</div>';
    if (listEl) listEl.innerHTML = '<div class="ch-loading">\uCD5C\uADFC \uD074\uB9BD \uB85C\uB529 \uC911...</div>';
    playLiveChannel(ch);
    fetchRSS(ch.channelId)
      .then(function (xml) {
        var videos = parseRSS(xml);
        chState.videos = videos;
        renderVideoList(videos);
      })
      .catch(function () {
        if (listEl) listEl.innerHTML = '<div class="ch-loading">\uCD5C\uADFC \uD074\uB9BD \uC5C6\uC74C</div>';
      });
    return;
  }

  // VOD
  if (listEl) listEl.innerHTML = '<div class="ch-loading">\uB85C\uB529 \uC911...</div>';
  if (player) player.innerHTML = '<div class="ch-player-placeholder">\uC601\uC0C1 \uB85C\uB529 \uC911...</div>';

  fetchRSS(ch.channelId)
    .then(function (xml) {
      var videos = parseRSS(xml);
      chState.videos = videos;
      renderVideoList(videos);
      if (videos.length > 0) {
        playVideo(0);
      } else {
        if (listEl) listEl.innerHTML = '<div class="ch-loading">\uC601\uC0C1\uC774 \uC5C6\uC2B5\uB2C8\uB2E4</div>';
      }
    })
    .catch(function () {
      if (listEl) listEl.innerHTML = '<div class="ch-loading">\uC601\uC0C1 \uBAA9\uB85D\uC744 \uBD88\uB7EC\uC62C \uC218 \uC5C6\uC2B5\uB2C8\uB2E4</div>';
    });
}

function playLiveChannel(ch) {
  var player = document.getElementById('ch-player');
  if (!player) return;
  if (ch.liveVideoId) {
    player.innerHTML = '<iframe src="https://www.youtube.com/embed/' + ch.liveVideoId +
      '?autoplay=1&mute=1&rel=0" frameborder="0" allowfullscreen ' +
      'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" ' +
      'style="width:100%;height:100%;border:none;"></iframe>';
  } else {
    player.innerHTML = '<iframe src="https://www.youtube.com/embed/live_stream?channel=' + ch.channelId +
      '&autoplay=1&mute=1" frameborder="0" allowfullscreen ' +
      'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" ' +
      'style="width:100%;height:100%;border:none;"></iframe>';
  }
  var info = document.getElementById('ch-now-info');
  if (info) {
    info.innerHTML = '<div class="ch-now-title"><span class="ch-live-badge">LIVE</span> ' + escapeHtml(ch.name) + '</div>' +
      '<div class="ch-now-meta">24\uC2DC\uAC04 \uC2E4\uC2DC\uAC04 \uC2A4\uD2B8\uB9BC' +
      ' \xB7 <a href="https://www.youtube.com/channel/' + ch.channelId + '/live" target="_blank" class="ch-yt-link">YouTube\uC5D0\uC11C \uBCF4\uAE30</a></div>' +
      '<div id="ch-summary-area"></div>';
  }
}

function parseRSS(xmlText) {
  var parser = new DOMParser();
  var doc = parser.parseFromString(xmlText, 'text/xml');
  var entries = doc.querySelectorAll('entry');
  var videos = [];
  entries.forEach(function (entry, idx) {
    if (idx >= 7) return;
    var videoId = '';
    var vidIdEl = entry.getElementsByTagNameNS('http://www.youtube.com/xml/schemas/2015', 'videoId')[0];
    if (vidIdEl) videoId = vidIdEl.textContent;
    else {
      var idEl = entry.querySelector('id');
      if (idEl) videoId = idEl.textContent.replace('yt:video:', '');
    }
    var title = (entry.querySelector('title') || {}).textContent || '';
    var published = (entry.querySelector('published') || {}).textContent || '';
    var thumbnail = 'https://i.ytimg.com/vi/' + videoId + '/mqdefault.jpg';
    if (videoId) videos.push({ videoId: videoId, title: title, published: published, thumbnail: thumbnail });
  });
  return videos;
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  var d = new Date(dateStr);
  var now = new Date();
  var diff = Math.floor((now - d) / 1000);
  if (isNaN(diff) || diff < 0) return '';
  if (diff < 60) return '\uBC29\uAE08 \uC804';
  if (diff < 3600) return Math.floor(diff / 60) + '\uBD84 \uC804';
  if (diff < 86400) return Math.floor(diff / 3600) + '\uC2DC\uAC04 \uC804';
  if (diff < 604800) return Math.floor(diff / 86400) + '\uC77C \uC804';
  return d.toLocaleDateString('ko-KR');
}

function escapeHtml(str) {
  var div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

function renderVideoList(videos) {
  var listEl = document.getElementById('ch-video-list');
  if (!listEl) return;
  if (!videos.length) {
    listEl.innerHTML = '<div class="ch-loading">\uC601\uC0C1\uC774 \uC5C6\uC2B5\uB2C8\uB2E4</div>';
    return;
  }
  var ch = CHANNELS[chState.currentChannel] || {};
  var html = videos.map(function (v, i) {
    return '<div class="ch-video-item" data-vidx="' + i + '" onclick="playVideo(' + i + ')">' +
      '<div class="ch-video-thumb-wrap">' +
        '<img class="ch-video-thumb" src="' + v.thumbnail + '" alt="" loading="lazy">' +
      '</div>' +
      '<div class="ch-video-info">' +
        '<div class="ch-video-title">' + escapeHtml(v.title) + '</div>' +
        '<div class="ch-video-meta">' + escapeHtml(ch.name || '') + ' \xB7 ' + timeAgo(v.published) + '</div>' +
        (ch.type === 'vod' ? '<button class="ch-summary-btn" onclick="event.stopPropagation();requestSummary(\'' + v.videoId + '\',' + i + ')">AI \uC694\uC57D</button>' : '') +
      '</div>' +
    '</div>';
  }).join('');
  listEl.innerHTML = html;
}

function playVideo(idx) {
  var video = chState.videos[idx];
  if (!video) return;
  chState.currentVideo = idx;
  var player = document.getElementById('ch-player');
  if (player) {
    player.innerHTML = '<iframe src="https://www.youtube.com/embed/' + video.videoId +
      '?autoplay=1&rel=0" frameborder="0" allowfullscreen ' +
      'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" ' +
      'style="width:100%;height:100%;border:none;"></iframe>';
  }
  var info = document.getElementById('ch-now-info');
  if (info) {
    var ch = CHANNELS[chState.currentChannel] || {};
    info.innerHTML = '<div class="ch-now-title">' + escapeHtml(video.title) + '</div>' +
      '<div class="ch-now-meta">' + escapeHtml(ch.name || '') + ' \xB7 ' + timeAgo(video.published) +
      ' \xB7 <a href="https://www.youtube.com/watch?v=' + video.videoId + '" target="_blank" class="ch-yt-link">YouTube\uC5D0\uC11C \uBCF4\uAE30</a></div>' +
      '<div id="ch-summary-area"></div>';
  }
  document.querySelectorAll('.ch-video-item').forEach(function (el) { el.classList.remove('active'); });
  var activeItem = document.querySelector('.ch-video-item[data-vidx="' + idx + '"]');
  if (activeItem) activeItem.classList.add('active');
}

// ── Tab clicks ──────────────────────────────────────────
document.addEventListener('click', function (e) {
  var chTab = e.target.closest('.ch-tab');
  if (!chTab) return;
  document.querySelectorAll('.ch-tab').forEach(function (b) { b.classList.remove('active'); });
  chTab.classList.add('active');
  var chIdx = parseInt(chTab.getAttribute('data-ch'));
  fetchChannelVideos(chIdx);
});

// ── Auto-load first channel when tab shown ──────────────
document.addEventListener('click', function (e) {
  var pageTab = e.target.closest('.page-tab');
  if (!pageTab) return;
  if (pageTab.getAttribute('data-page') === 'channels') {
    if (!chState.loaded) {
      setTimeout(function () { fetchChannelVideos(0); }, 100);
    }
  }
});

// ── AI Summary ──────────────────────────────────────────
function requestSummary(videoId, vidIdx) {
  var area = document.getElementById('ch-summary-area');
  if (!area) return;
  var video = chState.videos[vidIdx];
  var title = video ? video.title : '';
  area.innerHTML = '<div class="ch-summary-loading"><div class="ch-summary-spinner"></div> AI \uC694\uC57D \uC0DD\uC131 \uC911...</div>';
  var btn = document.querySelector('.ch-summary-btn');
  if (btn) { btn.disabled = true; btn.textContent = '\uC694\uC57D \uC911...'; }
  fetch('/api/youtube/summary', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_id: videoId, title: title }),
  })
    .then(function (res) { return res.json(); })
    .then(function (data) {
      if (data.error) area.innerHTML = '<div class="ch-summary-error">' + escapeHtml(data.error) + '</div>';
      else renderChSummary(area, data);
      if (btn) { btn.disabled = false; btn.textContent = 'AI \uC694\uC57D'; }
    })
    .catch(function (err) {
      area.innerHTML = '<div class="ch-summary-error">\uC694\uC57D \uC2E4\uD328: ' + escapeHtml(err.message) + '</div>';
      if (btn) { btn.disabled = false; btn.textContent = 'AI \uC694\uC57D'; }
    });
}

function renderChSummary(container, data) {
  var html = '<div class="ch-summary-card"><div class="ch-summary-header">AI \uC694\uC57D</div>' +
    '<div class="ch-summary-text">' + escapeHtml(data.summary || '') + '</div>';
  var points = data.key_points || [];
  if (points.length) {
    html += '<div class="ch-summary-points">';
    points.forEach(function (p) { html += '<div class="ch-summary-point">\u2022 ' + escapeHtml(p) + '</div>'; });
    html += '</div>';
  }
  var tickers = data.mentioned_tickers || [];
  if (tickers.length) {
    html += '<div class="ch-summary-tickers">\uC5B8\uAE09 \uC885\uBAA9: ';
    tickers.forEach(function (t) { html += '<span class="ch-ticker-tag">' + escapeHtml(t) + '</span>'; });
    html += '</div>';
  }
  html += '</div>';
  container.innerHTML = html;
}
