/* ═══════════════════════════════════════════════════════════
   TitanX Control Panel — Premium JS v5
   ═══════════════════════════════════════════════════════════ */

// ── Theme ────────────────────────────────────────────────────
const THEME_KEY = 'titanx_theme';
function applyTheme(t) { document.documentElement.setAttribute('data-theme', t); }
function toggleTheme() {
  const cur  = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = cur === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  localStorage.setItem(THEME_KEY, next);
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = next === 'dark' ? '☀️' : '🌙';
}
(function () { applyTheme(localStorage.getItem(THEME_KEY) || 'dark'); })();

// ── Back Button ───────────────────────────────────────────────
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    var fixedBtn = document.getElementById('fixed-back-btn');
    if (fixedBtn) {
      var p = window.location.pathname;
      if (p !== '/' && p !== '/panel' && p !== '/login') {
        fixedBtn.classList.add('visible');
      }
      fixedBtn.addEventListener('click', function () {
        // Navigate without showing loading overlay (instant back)
        if (document.referrer && document.referrer !== window.location.href &&
            document.referrer.indexOf(window.location.host) !== -1) {
          window.history.back();
        } else {
          window.location.href = '/';
        }
      });
    }
  });
})();

// ── Page Loader — hide as fast as possible ───────────────────
(function () {
  var loader = document.getElementById('page-loader');
  if (!loader) return;
  function hideLoader() {
    loader.classList.add('hidden');
    // CSS .page-loader.hidden already applies display:none !important
    // No JS setTimeout needed
  }
  if (document.readyState === 'complete') {
    hideLoader();
  } else {
    document.addEventListener('DOMContentLoaded', hideLoader);
    window.addEventListener('load', hideLoader);
  }
})();

// ── Loading Overlay ───────────────────────────────────────────
var _loadingTimer = null;
function showLoading(msg) {
  var overlay = document.getElementById('loading-overlay');
  var text    = document.getElementById('loading-text');
  if (!overlay) return;
  if (text) text.textContent = msg || 'جاري التحميل...';
  overlay.classList.add('active');
  // Auto-hide after 8s to prevent permanent blur
  if (_loadingTimer) clearTimeout(_loadingTimer);
  _loadingTimer = setTimeout(hideLoading, 8000);
}
function hideLoading() {
  var overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.classList.remove('active');
  if (_loadingTimer) { clearTimeout(_loadingTimer); _loadingTimer = null; }
}

// ── Sidebar ───────────────────────────────────────────────────
function toggleSidebar() {
  var sb      = document.querySelector('.sidebar');
  var main    = document.querySelector('.main');
  var overlay = document.getElementById('mobile-overlay');
  if (!sb) return;
  if (window.innerWidth <= 768) {
    var isOpen = sb.classList.toggle('mobile-open');
    if (overlay) {
      if (isOpen) {
        overlay.classList.add('visible');
        overlay.style.display      = 'block';
        overlay.style.pointerEvents = 'all';
      } else {
        _clearOverlay(overlay);
      }
    }
  } else {
    var collapsed = sb.classList.toggle('collapsed');
    if (main) main.classList.toggle('expanded', collapsed);
  }
}

function closeSidebar() {
  var sb      = document.querySelector('.sidebar');
  var overlay = document.getElementById('mobile-overlay');
  if (sb) sb.classList.remove('mobile-open');
  if (overlay) _clearOverlay(overlay);
}

function _clearOverlay(overlay) {
  overlay.classList.remove('visible');
  overlay.style.display       = 'none';
  overlay.style.pointerEvents = 'none';
  overlay.style.opacity       = '';
}

// Close sidebar on outside click
document.addEventListener('DOMContentLoaded', function () {
  document.addEventListener('click', function (e) {
    var sb = document.querySelector('.sidebar');
    if (!sb) return;
    if (window.innerWidth > 768) return;
    if (!sb.classList.contains('mobile-open')) return;
    var btn = document.querySelector('.header-menu-btn');
    if (sb.contains(e.target) || (btn && btn.contains(e.target))) return;
    closeSidebar();
  });
});

// ── Toast Notifications ───────────────────────────────────────
function showToast(msg, type, duration) {
  type     = type     || 'info';
  duration = duration || 4000;
  var container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  var icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  var toast = document.createElement('div');
  toast.className = 'toast ' + type;
  toast.innerHTML =
    '<span class="toast-icon">' + (icons[type] || 'ℹ️') + '</span>' +
    '<span class="toast-msg">' + msg + '</span>' +
    '<button class="toast-close" onclick="this.parentElement.remove()">✕</button>';
  container.appendChild(toast);
  setTimeout(function () {
    toast.classList.add('removing');
    setTimeout(function () { if (toast.parentNode) toast.remove(); }, 320);
  }, duration);
}

// ── API Helpers ───────────────────────────────────────────────
async function apiGet(url) {
  var r = await fetch(url, { credentials: 'include' });
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

async function apiPost(url, body) {
  var isForm = body instanceof FormData;
  var opts   = { method: 'POST', credentials: 'include', body: isForm ? body : JSON.stringify(body) };
  if (!isForm) opts.headers = { 'Content-Type': 'application/json' };
  var r = await fetch(url, opts);
  return r.json();
}

async function apiDelete(url) {
  var r = await fetch(url, { method: 'DELETE', credentials: 'include' });
  return r.json();
}

// ── Animated Counter ──────────────────────────────────────────
function animateCounters() {
  document.querySelectorAll('[data-count]').forEach(function (el) {
    var target = parseInt(el.getAttribute('data-count')) || 0;
    if (target === 0) { el.textContent = '0'; return; }
    var duration = 900, steps = 45, step = Math.ceil(target / steps), current = 0;
    var timer = setInterval(function () {
      current = Math.min(current + step, target);
      el.textContent = current.toLocaleString('ar-SA');
      if (current >= target) clearInterval(timer);
    }, duration / steps);
  });
}
document.addEventListener('DOMContentLoaded', function () { setTimeout(animateCounters, 300); });

// ── Tabs ──────────────────────────────────────────────────────
function switchTab(btn, groupId) {
  var group  = groupId ? document.getElementById(groupId) : btn.closest('[data-tab-group]');
  var target = btn.getAttribute('data-tab');
  var scope  = group || document;
  scope.querySelectorAll('.tab-btn').forEach(function (b) { b.classList.remove('active'); });
  scope.querySelectorAll('.tab-pane').forEach(function (p) { p.classList.remove('active'); });
  btn.classList.add('active');
  var pane = document.getElementById(target);
  if (pane) pane.classList.add('active');
}

// ── Modals ────────────────────────────────────────────────────
function openModal(id) {
  var m = document.getElementById(id);
  if (m) { m.classList.remove('hidden'); m.style.display = 'flex'; }
}
function closeModal(id) {
  var m = document.getElementById(id);
  if (m) { m.classList.add('hidden'); m.style.display = ''; }
}
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(function (m) {
      m.classList.add('hidden'); m.style.display = '';
    });
  }
});

// ── File Editor ───────────────────────────────────────────────
var _editorPath = '', _editorOriginal = '';

async function openFile(path) {
  try {
    showLoading('جاري تحميل الملف...');
    var data = await apiGet('/files/api/read?path=' + encodeURIComponent(path));
    hideLoading();
    if (!data.content && data.error) { showToast(data.error, 'error'); return; }
    _editorPath     = path;
    _editorOriginal = data.content || '';
    var epEl = document.getElementById('editor-path');
    var feEl = document.getElementById('file-editor');
    var dv   = document.getElementById('diff-view');
    if (epEl) epEl.textContent = path;
    if (feEl) feEl.value = _editorOriginal;
    if (dv)   { dv.style.display = 'none'; dv.textContent = ''; }
    openModal('editor-modal');
  } catch (e) { hideLoading(); showToast('فشل تحميل الملف', 'error'); }
}

async function saveFile() {
  var feEl = document.getElementById('file-editor');
  var content = feEl ? feEl.value : '';
  var btn     = document.getElementById('save-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ حفظ...'; }
  showLoading('جاري الحفظ...');
  try {
    var data = await apiPost('/files/api/write', { path: _editorPath, content: content });
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '💾 حفظ'; }
    if (data.ok) { showToast('تم الحفظ بنجاح ✅', 'success'); _editorOriginal = content; closeModal('editor-modal'); }
    else { showToast(data.error || 'فشل الحفظ', 'error'); }
  } catch (e) { hideLoading(); if (btn) { btn.disabled = false; btn.textContent = '💾 حفظ'; } showToast('خطأ في الاتصال', 'error'); }
}

// ── User Detail Modal ─────────────────────────────────────────
async function showUserDetail(userId) {
  try {
    showLoading('جاري تحميل بيانات المستخدم...');
    var u = await apiGet('/users/api/detail/' + userId);
    hideLoading();
    if (!u || u.error) { showToast(u && u.error ? u.error : 'لم يُعثر على المستخدم', 'error'); return; }
    var setT = function (id, val) { var el = document.getElementById(id); if (el) el.textContent = val; };
    var setH = function (id, val) { var el = document.getElementById(id); if (el) el.innerHTML  = val; };
    setT('ud-name',      u.first_name || '---');
    setT('ud-id',        u.user_id || u.id || '');
    setT('ud-username',  u.username ? '@' + u.username : '---');
    setT('ud-lang',      u.language_code || '---');
    setT('ud-points',    (u.points || 0).toLocaleString());
    setT('ud-downloads', (u.total_downloads || 0).toLocaleString());
    setT('ud-referrals', (u.total_referrals || 0).toLocaleString());
    setH('ud-banned',    u.is_banned ? '<span class="badge badge-red">🚫 محظور</span>' : '<span class="badge badge-green">✅ نشط</span>');
    setT('ud-vip',       u.vip_until || '---');
    var uid  = u.user_id || u.id;
    var eb   = document.getElementById('ud-ban-btn');
    var eu   = document.getElementById('ud-unban-btn');
    var ep   = document.getElementById('ud-premium-btn');
    var ept  = document.getElementById('ud-points-btn');
    if (eb)  eb.onclick  = function () { userAction(uid, 'ban'); };
    if (eu)  eu.onclick  = function () { userAction(uid, 'unban'); };
    if (ep)  ep.onclick  = function () { userAction(uid, 'vip'); };
    if (ept) ept.onclick = function () { userAction(uid, 'points'); };
    openModal('user-detail-modal');
  } catch (e) { hideLoading(); showToast('خطأ في تحميل البيانات', 'error'); }
}

async function userAction(userId, action) {
  try {
    showLoading('جاري التنفيذ...');
    var pts  = action === 'points' ? (prompt('عدد النقاط:') || '0') : undefined;
    var body = { user_id: userId, action: action };
    if (pts !== undefined) body.points = parseInt(pts) || 0;
    var data = await apiPost('/users/api/action', body);
    hideLoading();
    showToast(data.msg || (data.ok ? 'تم بنجاح' : 'فشل'), data.ok ? 'success' : 'error');
    if (data.ok) closeModal('user-detail-modal');
  } catch (e) { hideLoading(); showToast('خطأ في الاتصال', 'error'); }
}

// ── GitHub helpers ────────────────────────────────────────────
async function gitPull() {
  var btn = document.getElementById('pull-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ جاري السحب...'; }
  showLoading('جاري Pull من GitHub...');
  try {
    var data = await apiPost('/github/api/pull', {});
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '⬇️ Pull'; }
    showToast(data.output || (data.ok ? 'تم Pull بنجاح ✅' : 'فشل Pull'), data.ok ? 'success' : 'error');
    if (typeof refreshGitInfo === 'function') refreshGitInfo();
  } catch (e) { hideLoading(); if (btn) { btn.disabled = false; btn.textContent = '⬇️ Pull'; } showToast('فشل الاتصال بـ GitHub', 'error'); }
}

async function gitPush() {
  var btn   = document.getElementById('push-btn');
  var msgEl = document.getElementById('commit-msg');
  var msg   = msgEl ? msgEl.value : 'Update via TitanX Control Panel';
  if (btn) { btn.disabled = true; btn.textContent = '⏳ جاري الرفع...'; }
  showLoading('جاري Push إلى GitHub...');
  try {
    var data = await apiPost('/github/api/push', { message: msg });
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '⬆️ Push'; }
    showToast(data.output || (data.ok ? 'تم Push بنجاح ✅' : 'فشل Push'), data.ok ? 'success' : 'error');
    if (typeof refreshGitInfo === 'function') refreshGitInfo();
  } catch (e) { hideLoading(); if (btn) { btn.disabled = false; btn.textContent = '⬆️ Push'; } showToast('فشل الاتصال بـ GitHub', 'error'); }
}

async function refreshGitInfo() {
  try {
    var data     = await apiGet('/github/api/info');
    var branchEl = document.getElementById('git-branch');
    if (branchEl) branchEl.textContent = '🌿 ' + (data.branch || 'unknown');
    var commitsEl = document.getElementById('git-commits');
    if (commitsEl && data.commits) {
      commitsEl.innerHTML = data.commits.length
        ? data.commits.map(function (c) {
            return '<div class="scroll-list-item"><code style="font-size:.75rem;color:var(--text2)">' + c + '</code></div>';
          }).join('')
        : '<div style="color:var(--text2);padding:16px;text-align:center">لا توجد commits</div>';
    }
  } catch (e) {}
}

async function configureGit() {
  var repo  = (document.getElementById('cfg-repo')  || {}).value || '';
  var token = (document.getElementById('cfg-token') || {}).value || '';
  var name  = (document.getElementById('cfg-name')  || {}).value || '';
  var email = (document.getElementById('cfg-email') || {}).value || '';
  showLoading('جاري حفظ إعدادات Git...');
  try {
    var data = await apiPost('/github/api/configure', { repo, token, name, email });
    hideLoading();
    if (data.ok) showToast('تم حفظ الإعدادات: ' + data.results.join(', '), 'success');
    else showToast(data.error || 'فشل', 'error');
  } catch (e) { hideLoading(); showToast('خطأ في الاتصال', 'error'); }
}

async function gitCommit() {
  var msg = (document.getElementById('commit-msg') || {}).value || 'Update via TitanX';
  showLoading('جاري Commit...');
  try {
    var data = await apiPost('/github/api/commit', { message: msg });
    hideLoading();
    showToast(data.output || (data.ok ? 'تم Commit' : 'فشل'), data.ok ? 'success' : 'error');
    if (typeof refreshGitInfo === 'function') refreshGitInfo();
  } catch (e) { hideLoading(); showToast('خطأ في الاتصال', 'error'); }
}

// ── System stats live ─────────────────────────────────────────
var _statsInterval = null;
function startStatsPolling(interval) {
  interval = interval || 5000;
  if (_statsInterval) clearInterval(_statsInterval);
  _statsInterval = setInterval(_fetchStats, interval);
  _fetchStats();
}

async function _fetchStats() {
  try {
    var d = await apiGet('/system/api/stats');
    _uel('cpu-val',   d.cpu_percent + '%');  _ubar('cpu-bar',  d.cpu_percent);
    _uel('mem-val',   Math.round(d.mem_used / 1048576) + ' MB'); _ubar('mem-bar', d.mem_percent);
    _uel('mem-total', 'من ' + Math.round(d.mem_total / 1048576) + ' MB');
    _uel('disk-val',  Math.round(d.disk_used / 1073741824) + ' GB'); _ubar('disk-bar', d.disk_percent);
    _uel('uptime-val', d.uptime);
    _uel('net-sent',  Math.round(d.net_sent / 1048576) + ' MB');
    _uel('net-recv',  Math.round(d.net_recv / 1048576) + ' MB');
    _uel('mp-cpu',  d.cpu_percent + '%');
    _uel('mp-ram',  Math.round(d.mem_percent) + '%');
    _uel('mp-disk', Math.round(d.disk_percent) + '%');
    _uel('mp-up',   d.uptime);
    _ubarColor('mp-cpu-bar',  d.cpu_percent,  d.cpu_percent  > 80 ? 'var(--red)'    : 'var(--accent)');
    _ubarColor('mp-ram-bar',  d.mem_percent,  d.mem_percent  > 80 ? 'var(--yellow)' : 'var(--green)');
    _ubarColor('mp-disk-bar', d.disk_percent, d.disk_percent > 85 ? 'var(--red)'    : 'var(--cyan)');
  } catch (e) {}
}

function _uel(id, val) { var el = document.getElementById(id); if (el && el.textContent !== val) el.textContent = val; }
function _ubar(id, pct) { var el = document.getElementById(id); if (el) el.style.width = Math.min(100, Math.max(0, pct)) + '%'; }
function _ubarColor(id, pct, color) {
  var el = document.getElementById(id);
  if (el) { el.style.width = Math.min(100, Math.max(0, pct)) + '%'; if (color) el.style.background = color; }
}

// ── Bot status live — 4 states: running / stopped / restarting / error ──
var _botInterval = null;
function startBotPolling(interval) {
  interval = interval || 6000;
  if (_botInterval) clearInterval(_botInterval);
  _botInterval = setInterval(_fetchBotStatus, interval);
  _fetchBotStatus();
}

async function _fetchBotStatus() {
  try {
    var bots = await apiGet('/bots/api/status');
    bots.forEach(function (bot) {
      var state      = bot.state || (bot.running ? 'running' : 'stopped');
      var statusEl   = document.getElementById('bot-status-' + bot.key);
      var dotEl      = document.getElementById('bot-dot-'    + bot.key);
      var pidEl      = document.getElementById('bot-pid-'    + bot.key);
      var dashEl     = document.getElementById('dash-bot-'   + bot.key);
      var topbarEl   = document.getElementById('bot-topbar-' + bot.key);
      var startBtn   = document.getElementById('bot-start-'  + bot.key);
      var stopBtn    = document.getElementById('bot-stop-'   + bot.key);

      if (pidEl) pidEl.textContent = bot.pid ? 'PID: ' + bot.pid : '—';
      if (startBtn) startBtn.disabled = state === 'running';
      if (stopBtn)  stopBtn.disabled  = state === 'stopped';

      var pillHtml = _statePill(state);
      var dotClass = _stateDot(state);
      var barColor = _stateBarColor(state);

      if (statusEl) statusEl.innerHTML = pillHtml;
      if (dotEl)    dotEl.className    = 'dot ' + dotClass;
      if (dashEl)   dashEl.innerHTML   = pillHtml;
      if (topbarEl) topbarEl.style.background = 'linear-gradient(90deg,' + barColor + ',transparent)';
    });
  } catch (e) {}
}

function _statePill(state) {
  if (state === 'running')    return '<span class="status-pill status-pill-online"><span class="dot dot-green"></span>🟢 يعمل</span>';
  if (state === 'restarting') return '<span class="status-pill status-pill-restart"><span class="dot dot-yellow dot-blink"></span>🟡 جاري التشغيل...</span>';
  if (state === 'error')      return '<span class="status-pill status-pill-error"><span class="dot dot-red dot-blink-fast"></span>🔴 خطأ</span>';
  return '<span class="status-pill status-pill-offline"><span class="dot dot-red"></span>🔴 متوقف</span>';
}
function _stateDot(state) {
  if (state === 'running')    return 'dot-green';
  if (state === 'restarting') return 'dot-yellow dot-blink';
  return 'dot-red';
}
function _stateBarColor(state) {
  if (state === 'running')    return 'var(--green)';
  if (state === 'restarting') return 'var(--yellow)';
  return 'var(--red)';
}

// ── Bot actions ───────────────────────────────────────────────
async function botAction(key, action) {
  var btn      = document.getElementById('bot-' + action + '-' + key);
  var origText = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '⟳ جاري...'; }

  // Show restarting/stopping state immediately
  var immediateState = (action === 'stop') ? 'stopped' : 'restarting';
  var statusEl = document.getElementById('bot-status-' + key);
  var dashEl   = document.getElementById('dash-bot-'   + key);
  var topbarEl = document.getElementById('bot-topbar-' + key);
  var transitionPill = action === 'stop'
    ? '<span class="status-pill status-pill-restart"><span class="dot dot-yellow dot-blink"></span>🟡 جاري الإيقاف...</span>'
    : '<span class="status-pill status-pill-restart"><span class="dot dot-yellow dot-blink"></span>🟡 جاري الإعادة...</span>';
  if (statusEl) statusEl.innerHTML = transitionPill;
  if (dashEl)   dashEl.innerHTML   = transitionPill;
  if (topbarEl) topbarEl.style.background = 'linear-gradient(90deg,var(--yellow),transparent)';

  var labels = { start: 'تشغيل', stop: 'إيقاف', restart: 'إعادة التشغيل' };
  showToast((labels[action] || action) + ' البوت...', 'info', 1500);
  try {
    var data = await apiPost('/bots/api/' + action + '/' + key, {});
    if (btn) { btn.disabled = false; btn.innerHTML = origText; }
    showToast(data.msg || (data.ok ? 'تم بنجاح ✅' : 'فشل العملية'), data.ok ? 'success' : 'error');
    // Refresh quickly to get real state
    setTimeout(_fetchBotStatus, 1200);
    setTimeout(_fetchBotStatus, 3500);
  } catch (e) {
    if (btn) { btn.disabled = false; btn.innerHTML = origText; }
    showToast('فشل الاتصال', 'error');
    setTimeout(_fetchBotStatus, 1500);
  }
}

async function restartAllBots() {
  var btn = document.getElementById('restart-all-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⟳ جاري الإعادة...'; }
  showLoading('إعادة تشغيل جميع البوتات...');
  try {
    var data = await apiPost('/bots/api/restart_all', {});
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '🔄 إعادة تشغيل الكل'; }
    showToast('تم إعادة تشغيل جميع البوتات ✅', 'success');
    setTimeout(_fetchBotStatus, 2500);
    setTimeout(_fetchBotStatus, 5000);
  } catch (e) {
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '🔄 إعادة تشغيل الكل'; }
    showToast('فشل الاتصال', 'error');
  }
}

// ── Refresh System Stats ──────────────────────────────────────
async function refreshStats() {
  showLoading('تحديث البيانات...');
  await _fetchStats();
  hideLoading();
  showToast('تم التحديث ✅', 'success', 2000);
}

// ── Progress Bar Helper ───────────────────────────────────────
function setProgressBar(id, pct, color) {
  var el = document.getElementById(id);
  if (!el) return;
  setTimeout(function () {
    el.style.width = Math.min(100, Math.max(0, pct)) + '%';
    if (color) el.style.background = color;
  }, 50);
}

// ── Animate number ────────────────────────────────────────────
function animateNumber(el, from, to, duration) {
  duration = duration || 800;
  var start = null;
  var step = function (ts) {
    if (!start) start = ts;
    var progress = Math.min((ts - start) / duration, 1);
    var eased    = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(from + (to - from) * eased).toLocaleString('ar-SA');
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// ── Flash update ──────────────────────────────────────────────
function flashUpdate(id, val) {
  var el = document.getElementById(id);
  if (!el) return;
  el.textContent = val;
  el.classList.remove('count-updated');
  void el.offsetWidth;
  el.classList.add('count-updated');
}

// ── Copy to clipboard ─────────────────────────────────────────
function copyText(text, label) {
  label = label || 'النص';
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(function () { showToast('تم نسخ ' + label + ' ✅', 'success', 2000); });
  } else {
    var ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove();
    showToast('تم نسخ ' + label + ' ✅', 'success', 2000);
  }
}

// ── Live Header Clock ─────────────────────────────────────────
(function initHeaderClock() {
  document.addEventListener('DOMContentLoaded', function () {
    var clockEl = document.getElementById('header-clock');
    if (!clockEl) return;
    // Only show on wider screens
    if (window.innerWidth > 768) clockEl.style.display = 'block';
    function tick() {
      var now = new Date();
      var h = now.getHours().toString().padStart(2, '0');
      var m = now.getMinutes().toString().padStart(2, '0');
      var s = now.getSeconds().toString().padStart(2, '0');
      clockEl.textContent = h + ':' + m + ':' + s;
    }
    tick();
    setInterval(tick, 1000);
    window.addEventListener('resize', function () {
      clockEl.style.display = window.innerWidth > 768 ? 'block' : 'none';
    });
  });
})();

// ── Header sys pill live update (all pages) ───────────────────
// Runs on every page to keep the header CPU/RAM pill fresh.
// Dashboard overrides _fetchStats with a richer version that also updates the pill.
var _globalPillActive = false;
(function initGlobalStatsPoll() {
  document.addEventListener('DOMContentLoaded', function () {
    var hasDashboardCharts = !!document.getElementById('downloads-chart');
    if (hasDashboardCharts) return; // dashboard handles its own polling including the pill
    _globalPillActive = true;
    (async function globalPillPoll() {
      if (!_globalPillActive) return;
      try {
        var d = await apiGet('/system/api/stats');
        _uel('hdr-cpu', d.cpu_percent + '%');
        _uel('hdr-ram', Math.round(d.mem_percent) + '%');
        var hdrDot = document.getElementById('hdr-dot');
        if (hdrDot) hdrDot.className = 'dot dot-blink ' + (d.cpu_percent > 80 ? 'dot-red' : 'dot-green');
      } catch(e) {}
      setTimeout(globalPillPoll, 10000);
    })();
  });
})();

// ── Particles Background ──────────────────────────────────────
(function initParticles() {
  document.addEventListener('DOMContentLoaded', function () {
    var canvas = document.getElementById('particles-canvas');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    var W, H, particles = [];
    var PARTICLE_COUNT = 55;

    function resize() {
      W = canvas.width  = window.innerWidth;
      H = canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resize);
    resize();

    function rand(a, b) { return a + Math.random() * (b - a); }

    function Particle() {
      this.x  = rand(0, W);
      this.y  = rand(0, H);
      this.vx = rand(-0.22, 0.22);
      this.vy = rand(-0.22, 0.22);
      this.r  = rand(0.8, 2.4);
      this.a  = rand(0.06, 0.28);
      var palette = ['59,130,246', '168,85,247', '6,182,212', '34,197,94', '249,115,22'];
      this.c = palette[Math.floor(Math.random() * palette.length)];
    }
    Particle.prototype.update = function () {
      this.x += this.vx;
      this.y += this.vy;
      if (this.x < 0) this.x = W;
      if (this.x > W) this.x = 0;
      if (this.y < 0) this.y = H;
      if (this.y > H) this.y = 0;
    };
    Particle.prototype.draw = function () {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(' + this.c + ',' + this.a + ')';
      ctx.fill();
    };

    for (var i = 0; i < PARTICLE_COUNT; i++) particles.push(new Particle());

    function drawLines() {
      var MAX_DIST = 130;
      for (var i = 0; i < particles.length; i++) {
        for (var j = i + 1; j < particles.length; j++) {
          var dx = particles[i].x - particles[j].x;
          var dy = particles[i].y - particles[j].y;
          var d  = Math.sqrt(dx * dx + dy * dy);
          if (d < MAX_DIST) {
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(59,130,246,' + (0.06 * (1 - d / MAX_DIST)) + ')';
            ctx.lineWidth   = 0.6;
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }
    }

    function animate() {
      ctx.clearRect(0, 0, W, H);
      particles.forEach(function (p) { p.update(); p.draw(); });
      drawLines();
      requestAnimationFrame(animate);
    }
    animate();
  });
})();
