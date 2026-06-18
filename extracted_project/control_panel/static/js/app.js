/* ═══════════════════════════════════════════════════════════
   TitanX Control Panel — Premium JS v4
   ═══════════════════════════════════════════════════════════ */

// ── Theme ────────────────────────────────────────────────────
const THEME_KEY = 'titanx_theme';
function applyTheme(t) { document.documentElement.setAttribute('data-theme', t); }
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = cur === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  localStorage.setItem(THEME_KEY, next);
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = next === 'dark' ? '☀️' : '🌙';
}
(function () { applyTheme(localStorage.getItem(THEME_KEY) || 'dark'); })();

// ── Back Button (fixed floating button, all pages) ───────────
(function () {
  document.addEventListener('DOMContentLoaded', function () {
    // Fixed floating back button (new design)
    var fixedBtn = document.getElementById('fixed-back-btn');
    if (fixedBtn) {
      var p = window.location.pathname;
      if (p !== '/' && p !== '/panel' && p !== '/login') {
        fixedBtn.classList.add('visible');
      }
      fixedBtn.addEventListener('click', function () {
        if (document.referrer && document.referrer !== window.location.href &&
            document.referrer.indexOf(window.location.host) !== -1) {
          window.history.back();
        } else {
          window.location.href = '/';
        }
      });
    }
    // Legacy back-btn (header button — kept for compatibility)
    var btn = document.getElementById('back-btn');
    if (btn) {
      var p2 = window.location.pathname;
      if (p2 !== '/' && p2 !== '/panel' && p2 !== '/login') {
        btn.classList.add('visible');
      }
      btn.addEventListener('click', function () {
        if (document.referrer && document.referrer !== window.location.href) {
          window.history.back();
        } else {
          window.location.href = '/';
        }
      });
    }
  });
})();

// ── Page Loader ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  const loader = document.getElementById('page-loader');
  if (!loader) return;
  setTimeout(function () {
    loader.classList.add('hidden');
    setTimeout(function () { if (loader) loader.style.display = 'none'; }, 450);
  }, 400);
});

// ── Loading Overlay ──────────────────────────────────────────
function showLoading(msg) {
  const overlay = document.getElementById('loading-overlay');
  const text = document.getElementById('loading-text');
  if (!overlay) return;
  if (text) text.textContent = msg || 'جاري التحميل...';
  overlay.classList.add('active');
}
function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.classList.remove('active');
}

// ── Sidebar ──────────────────────────────────────────────────
function toggleSidebar() {
  const sb = document.querySelector('.sidebar');
  const main = document.querySelector('.main');
  const overlay = document.getElementById('mobile-overlay');
  if (!sb) return;
  if (window.innerWidth <= 768) {
    const isOpen = sb.classList.toggle('mobile-open');
    if (overlay) overlay.classList.toggle('visible', isOpen);
  } else {
    const collapsed = sb.classList.toggle('collapsed');
    if (main) main.classList.toggle('expanded', collapsed);
  }
}
function closeSidebar() {
  const sb = document.querySelector('.sidebar');
  const overlay = document.getElementById('mobile-overlay');
  if (sb) sb.classList.remove('mobile-open');
  if (overlay) overlay.classList.remove('visible');
}

// ── Toast Notifications ──────────────────────────────────────
function showToast(msg, type, duration) {
  type = type || 'info';
  duration = duration || 4000;
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  const toast = document.createElement('div');
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

// ── API Helpers ──────────────────────────────────────────────
async function apiGet(url) {
  const r = await fetch(url, { credentials: 'include' });
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

async function apiPost(url, body) {
  const isForm = body instanceof FormData;
  const opts = { method: 'POST', credentials: 'include', body: isForm ? body : JSON.stringify(body) };
  if (!isForm) opts.headers = { 'Content-Type': 'application/json' };
  const r = await fetch(url, opts);
  return r.json();
}

async function apiDelete(url) {
  const r = await fetch(url, { method: 'DELETE', credentials: 'include' });
  return r.json();
}

// ── Animated Counter ─────────────────────────────────────────
function animateCounters() {
  document.querySelectorAll('[data-count]').forEach(function (el) {
    const target = parseInt(el.getAttribute('data-count')) || 0;
    if (target === 0) { el.textContent = '0'; return; }
    const duration = 900;
    const steps = 45;
    const step = Math.ceil(target / steps);
    let current = 0;
    const timer = setInterval(function () {
      current = Math.min(current + step, target);
      el.textContent = current.toLocaleString('ar-SA');
      if (current >= target) clearInterval(timer);
    }, duration / steps);
  });
}
document.addEventListener('DOMContentLoaded', function () {
  setTimeout(animateCounters, 300);
});

// ── Tabs ─────────────────────────────────────────────────────
function switchTab(btn, groupId) {
  const group = groupId ? document.getElementById(groupId) : btn.closest('[data-tab-group]');
  const target = btn.getAttribute('data-tab');
  const scope = group || document;
  scope.querySelectorAll('.tab-btn').forEach(function (b) { b.classList.remove('active'); });
  scope.querySelectorAll('.tab-pane').forEach(function (p) { p.classList.remove('active'); });
  btn.classList.add('active');
  const pane = document.getElementById(target);
  if (pane) pane.classList.add('active');
}

// ── Modal helpers ────────────────────────────────────────────
function openModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.remove('hidden'); m.style.display = 'flex'; }
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.add('hidden'); m.style.display = ''; }
}
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(function (m) {
      m.classList.add('hidden'); m.style.display = '';
    });
  }
});

// ── File Editor ──────────────────────────────────────────────
var _editorPath = '';
var _editorOriginal = '';

async function openFile(path) {
  try {
    showLoading('جاري تحميل الملف...');
    const data = await apiGet('/files/api/read?path=' + encodeURIComponent(path));
    hideLoading();
    if (!data.content && data.error) { showToast(data.error, 'error'); return; }
    _editorPath = path;
    _editorOriginal = data.content || '';
    const epEl = document.getElementById('editor-path');
    const feEl = document.getElementById('file-editor');
    const dv   = document.getElementById('diff-view');
    if (epEl) epEl.textContent = path;
    if (feEl) feEl.value = _editorOriginal;
    if (dv) { dv.style.display = 'none'; dv.textContent = ''; }
    openModal('editor-modal');
  } catch (e) {
    hideLoading();
    showToast('فشل تحميل الملف', 'error');
  }
}

async function saveFile() {
  const feEl = document.getElementById('file-editor');
  const content = feEl ? feEl.value : '';
  const btn = document.getElementById('save-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ حفظ...'; }
  showLoading('جاري الحفظ...');
  try {
    const data = await apiPost('/files/api/write', { path: _editorPath, content: content });
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '💾 حفظ'; }
    if (data.ok) {
      showToast('تم الحفظ بنجاح ✅', 'success');
      _editorOriginal = content;
      closeModal('editor-modal');
    } else {
      showToast(data.error || 'فشل الحفظ', 'error');
    }
  } catch (e) {
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '💾 حفظ'; }
    showToast('خطأ في الاتصال', 'error');
  }
}

// ── User Detail Modal ────────────────────────────────────────
async function showUserDetail(userId) {
  try {
    showLoading('جاري تحميل بيانات المستخدم...');
    const u = await apiGet('/users/api/detail/' + userId);
    hideLoading();
    if (!u || u.error) { showToast(u && u.error ? u.error : 'لم يُعثر على المستخدم', 'error'); return; }
    var setT = function(id, val) { var el = document.getElementById(id); if (el) el.textContent = val; };
    var setH = function(id, val) { var el = document.getElementById(id); if (el) el.innerHTML = val; };
    setT('ud-name', u.first_name || '---');
    setT('ud-id', u.user_id || u.id || '');
    setT('ud-username', u.username ? '@' + u.username : '---');
    setT('ud-lang', u.language_code || '---');
    setT('ud-points', (u.points || 0).toLocaleString());
    setT('ud-downloads', (u.total_downloads || 0).toLocaleString());
    setT('ud-referrals', (u.total_referrals || 0).toLocaleString());
    setH('ud-banned', u.is_banned
      ? '<span class="badge badge-red">🚫 محظور</span>'
      : '<span class="badge badge-green">✅ نشط</span>');
    setT('ud-vip', u.vip_until || '---');
    const uid = u.user_id || u.id;
    var eb = document.getElementById('ud-ban-btn');
    var eu = document.getElementById('ud-unban-btn');
    var ep = document.getElementById('ud-premium-btn');
    var ept = document.getElementById('ud-points-btn');
    if (eb) eb.onclick = function() { userAction(uid, 'ban'); };
    if (eu) eu.onclick = function() { userAction(uid, 'unban'); };
    if (ep) ep.onclick = function() { userAction(uid, 'vip'); };
    if (ept) ept.onclick = function() { userAction(uid, 'points'); };
    openModal('user-detail-modal');
  } catch (e) {
    hideLoading();
    showToast('خطأ في تحميل البيانات', 'error');
  }
}

async function userAction(userId, action) {
  try {
    showLoading('جاري التنفيذ...');
    const pts = action === 'points' ? (prompt('عدد النقاط:') || '0') : undefined;
    const body = { user_id: userId, action: action };
    if (pts !== undefined) body.points = parseInt(pts) || 0;
    const data = await apiPost('/users/api/action', body);
    hideLoading();
    showToast(data.msg || (data.ok ? 'تم بنجاح' : 'فشل'), data.ok ? 'success' : 'error');
    if (data.ok) closeModal('user-detail-modal');
  } catch (e) {
    hideLoading();
    showToast('خطأ في الاتصال', 'error');
  }
}

// ── GitHub helpers ────────────────────────────────────────────
async function gitPull() {
  var btn = document.getElementById('pull-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ جاري السحب...'; }
  showLoading('جاري Pull من GitHub...');
  try {
    const data = await apiPost('/github/api/pull', {});
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '⬇️ Pull'; }
    showToast(data.output || (data.ok ? 'تم Pull بنجاح ✅' : 'فشل Pull'), data.ok ? 'success' : 'error');
    if (typeof refreshGitInfo === 'function') refreshGitInfo();
  } catch (e) {
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '⬇️ Pull'; }
    showToast('فشل الاتصال بـ GitHub', 'error');
  }
}

async function gitPush() {
  var btn = document.getElementById('push-btn');
  var msgEl = document.getElementById('commit-msg');
  var msg = msgEl ? msgEl.value : 'Update via TitanX Control Panel';
  if (btn) { btn.disabled = true; btn.textContent = '⏳ جاري الرفع...'; }
  showLoading('جاري Push إلى GitHub...');
  try {
    const data = await apiPost('/github/api/push', { message: msg });
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '⬆️ Push'; }
    showToast(data.output || (data.ok ? 'تم Push بنجاح ✅' : 'فشل Push'), data.ok ? 'success' : 'error');
    if (typeof refreshGitInfo === 'function') refreshGitInfo();
  } catch (e) {
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '⬆️ Push'; }
    showToast('فشل الاتصال بـ GitHub', 'error');
  }
}

async function refreshGitInfo() {
  try {
    const data = await apiGet('/github/api/info');
    var branchEl = document.getElementById('git-branch');
    if (branchEl) branchEl.textContent = '🌿 ' + (data.branch || 'unknown');
    var commitsEl = document.getElementById('git-commits');
    if (commitsEl && data.commits) {
      commitsEl.innerHTML = data.commits.length
        ? data.commits.map(function(c) {
            return '<div class="scroll-list-item"><code style="font-size:.75rem;color:var(--text2)">' + c + '</code></div>';
          }).join('')
        : '<div style="color:var(--text2);padding:16px;text-align:center">لا توجد commits</div>';
    }
  } catch (e) {}
}

async function configureGit() {
  const repo  = (document.getElementById('cfg-repo') || {}).value || '';
  const token = (document.getElementById('cfg-token') || {}).value || '';
  const name  = (document.getElementById('cfg-name') || {}).value || '';
  const email = (document.getElementById('cfg-email') || {}).value || '';
  showLoading('جاري حفظ إعدادات Git...');
  try {
    const data = await apiPost('/github/api/configure', { repo, token, name, email });
    hideLoading();
    if (data.ok) showToast('تم حفظ الإعدادات: ' + data.results.join(', '), 'success');
    else showToast(data.error || 'فشل', 'error');
  } catch (e) {
    hideLoading();
    showToast('خطأ في الاتصال', 'error');
  }
}

async function gitCommit() {
  var msg = (document.getElementById('commit-msg') || {}).value || 'Update via TitanX';
  showLoading('جاري Commit...');
  try {
    const data = await apiPost('/github/api/commit', { message: msg });
    hideLoading();
    showToast(data.output || (data.ok ? 'تم Commit' : 'فشل'), data.ok ? 'success' : 'error');
    if (typeof refreshGitInfo === 'function') refreshGitInfo();
  } catch (e) {
    hideLoading();
    showToast('خطأ في الاتصال', 'error');
  }
}

// ── System stats live ────────────────────────────────────────
var _statsInterval = null;
function startStatsPolling(interval) {
  interval = interval || 5000;
  if (_statsInterval) clearInterval(_statsInterval);
  _statsInterval = setInterval(_fetchStats, interval);
  _fetchStats();
}

async function _fetchStats() {
  try {
    const d = await apiGet('/system/api/stats');
    _uel('cpu-val',   d.cpu_percent + '%');
    _ubar('cpu-bar',  d.cpu_percent);
    _uel('mem-val',   Math.round(d.mem_used / 1048576) + ' MB');
    _ubar('mem-bar',  d.mem_percent);
    _uel('mem-total', 'من ' + Math.round(d.mem_total / 1048576) + ' MB');
    _uel('disk-val',  Math.round(d.disk_used / 1073741824) + ' GB');
    _ubar('disk-bar', d.disk_percent);
    _uel('uptime-val', d.uptime);
    _uel('net-sent',  Math.round(d.net_sent / 1048576) + ' MB');
    _uel('net-recv',  Math.round(d.net_recv / 1048576) + ' MB');
    // Dashboard metric pills
    _uel('mp-cpu',  d.cpu_percent + '%');
    _uel('mp-ram',  Math.round(d.mem_percent) + '%');
    _uel('mp-disk', Math.round(d.disk_percent) + '%');
    _uel('mp-up',   d.uptime);
    _ubarColor('mp-cpu-bar',  d.cpu_percent,  d.cpu_percent > 80  ? 'var(--red)'    : 'var(--accent)');
    _ubarColor('mp-ram-bar',  d.mem_percent,  d.mem_percent > 80  ? 'var(--yellow)' : 'var(--green)');
    _ubarColor('mp-disk-bar', d.disk_percent, d.disk_percent > 85 ? 'var(--red)'    : 'var(--cyan)');
  } catch (e) {}
}
function _uel(id, val) {
  var el = document.getElementById(id);
  if (el && el.textContent !== val) el.textContent = val;
}
function _ubar(id, pct) {
  var el = document.getElementById(id);
  if (el) el.style.width = Math.min(100, Math.max(0, pct)) + '%';
}
function _ubarColor(id, pct, color) {
  var el = document.getElementById(id);
  if (el) { el.style.width = Math.min(100, Math.max(0, pct)) + '%'; if (color) el.style.background = color; }
}

// ── Bot status live ──────────────────────────────────────────
var _botInterval = null;
function startBotPolling(interval) {
  interval = interval || 8000;
  if (_botInterval) clearInterval(_botInterval);
  _botInterval = setInterval(_fetchBotStatus, interval);
  _fetchBotStatus();
}

async function _fetchBotStatus() {
  try {
    const bots = await apiGet('/bots/api/status');
    bots.forEach(function (bot) {
      var statusEl = document.getElementById('bot-status-' + bot.key);
      var dotEl    = document.getElementById('bot-dot-' + bot.key);
      var pidEl    = document.getElementById('bot-pid-' + bot.key);
      var dashEl   = document.getElementById('dash-bot-' + bot.key);
      if (statusEl) statusEl.textContent = bot.running ? '🟢 يعمل' : '🔴 متوقف';
      if (dotEl)    dotEl.className = 'dot ' + (bot.running ? 'dot-green' : 'dot-red');
      if (pidEl)    pidEl.textContent = bot.pid ? '(PID: ' + bot.pid + ')' : '';
      if (dashEl)   dashEl.innerHTML = bot.running
        ? '<span class="dot dot-green"></span> يعمل'
        : '<span class="dot dot-red"></span> متوقف';
    });
  } catch (e) {}
}

// ── Bot actions ──────────────────────────────────────────────
async function botAction(key, action) {
  var btn = document.getElementById('bot-' + action + '-' + key);
  var origText = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '⟳ جاري...'; }
  var labels = { start: 'تشغيل', stop: 'إيقاف', restart: 'إعادة التشغيل' };
  showToast((labels[action] || action) + ' البوت...', 'info', 1500);
  try {
    const data = await apiPost('/bots/api/' + action + '/' + key, {});
    if (btn) { btn.disabled = false; btn.innerHTML = origText; }
    showToast(data.msg || (data.ok ? 'تم بنجاح ✅' : 'فشل العملية'), data.ok ? 'success' : 'error');
    setTimeout(_fetchBotStatus, 1800);
  } catch (e) {
    if (btn) { btn.disabled = false; btn.innerHTML = origText; }
    showToast('فشل الاتصال', 'error');
  }
}

async function restartAllBots() {
  var btn = document.getElementById('restart-all-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⟳ جاري الإعادة...'; }
  showLoading('إعادة تشغيل جميع البوتات...');
  try {
    const data = await apiPost('/bots/api/restart_all', {});
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '🔄 إعادة تشغيل الكل'; }
    showToast('تم إعادة تشغيل جميع البوتات ✅', 'success');
    setTimeout(_fetchBotStatus, 2200);
  } catch (e) {
    hideLoading();
    if (btn) { btn.disabled = false; btn.textContent = '🔄 إعادة تشغيل الكل'; }
    showToast('فشل الاتصال', 'error');
  }
}

// ── Refresh System Stats ─────────────────────────────────────
async function refreshStats() {
  showLoading('تحديث البيانات...');
  await _fetchStats();
  hideLoading();
  showToast('تم التحديث ✅', 'success', 2000);
}

// ── Progress Bar Animated Helper ─────────────────────────────
function setProgressBar(id, pct, color) {
  var el = document.getElementById(id);
  if (!el) return;
  setTimeout(function() {
    el.style.width = Math.min(100, Math.max(0, pct)) + '%';
    if (color) el.style.background = color;
  }, 50);
}

// ── Animate number smoothly ──────────────────────────────────
function animateNumber(el, from, to, duration) {
  duration = duration || 800;
  var start = null;
  var step = function(ts) {
    if (!start) start = ts;
    var progress = Math.min((ts - start) / duration, 1);
    var eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(from + (to - from) * eased).toLocaleString('ar-SA');
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// ── Element value update with flash animation ─────────────────
function flashUpdate(id, val) {
  var el = document.getElementById(id);
  if (!el) return;
  el.textContent = val;
  el.classList.remove('count-updated');
  void el.offsetWidth; // trigger reflow
  el.classList.add('count-updated');
}

// ── Copy to clipboard helper ──────────────────────────────────
function copyText(text, label) {
  label = label || 'النص';
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(function() {
      showToast('تم نسخ ' + label + ' ✅', 'success', 2500);
    }).catch(function() { _fallbackCopy(text, label); });
  } else { _fallbackCopy(text, label); }
}
function _fallbackCopy(text, label) {
  var ta = document.createElement('textarea');
  ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
  document.body.appendChild(ta); ta.focus(); ta.select();
  try { document.execCommand('copy'); showToast('تم نسخ ' + label + ' ✅', 'success', 2500); }
  catch(e) { showToast('فشل النسخ', 'error'); }
  document.body.removeChild(ta);
}

// ── Confirm Action Helper ─────────────────────────────────────
function confirmAction(msg, callback) {
  if (window.confirm(msg)) callback();
}

// ── Page transition on internal link clicks ───────────────────
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('a[href]').forEach(function(a) {
    var href = a.getAttribute('href');
    if (!href || href.startsWith('#') || href.startsWith('http') ||
        href.startsWith('mailto') || href.startsWith('javascript') ||
        a.target === '_blank') return;
    a.addEventListener('click', function(e) {
      var loader = document.getElementById('page-loader');
      if (loader) {
        loader.classList.remove('hidden');
        loader.style.display = '';
      }
    });
  });
});

// ── Scroll-in animation for cards ────────────────────────────
(function() {
  if (!window.IntersectionObserver) return;
  var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.style.animationPlayState = 'running';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08 });
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.fade-up, .slide-in, .scale-in').forEach(function(el) {
      el.style.animationPlayState = 'paused';
      observer.observe(el);
    });
  });
})();

// ── Auto-update counter values with locale ───────────────────
function updateCounter(id, val) {
  var el = document.getElementById(id);
  if (!el) return;
  var prev = parseInt(el.getAttribute('data-count') || el.textContent.replace(/\D/g, '')) || 0;
  el.setAttribute('data-count', val);
  animateNumber(el, prev, val, 600);
}

// ── Table row highlight on click ──────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('tbody').forEach(function(tbody) {
    tbody.addEventListener('click', function(e) {
      var row = e.target.closest('tr');
      if (!row) return;
      tbody.querySelectorAll('tr').forEach(function(r) { r.style.background = ''; });
      row.style.background = 'rgba(59,130,246,0.06)';
    });
  });
});
