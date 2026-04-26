/* ── Config ──────────────────────────────────────────────────── */
const API_BASE = '/api';

/* ── State ───────────────────────────────────────────────────── */
const state = {
  token: localStorage.getItem('ai_pm_token') || null,
  user: JSON.parse(localStorage.getItem('ai_pm_user') || 'null'),
  currentReportId: null,
  currentView: 'dashboard',
  reports: [],
  activeFilter: 'all',
  activeSort: 'newest',
  searchQuery: '',
  jobPollTimer: null,
  filterDebounceTimer: null,
};

/* ── Helpers ─────────────────────────────────────────────────── */
function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  return fetch(API_BASE + path, { ...opts, headers });
}

function esc(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function sevClass(score) {
  return score >= 7 ? 'sev-high' : score >= 4 ? 'sev-med' : 'sev-low';
}

function fmtDate(iso) {
  if (!iso) return '—';
  // If no timezone specified, append Z to force UTC interpretation
  const dateStr = (iso.includes('Z') || iso.includes('+')) ? iso : iso + 'Z';
  const d = new Date(dateStr);
  return d.toLocaleString('en-IN', { 
    day: '2-digit', 
    month: 'short', 
    hour: '2-digit', 
    minute: '2-digit',
    hour12: true
  });
}

/* ── Clock ───────────────────────────────────────────────────── */
setInterval(() => {
  const el = document.getElementById('footerClock');
  if (el) {
    const now = new Date();
    el.textContent = now.toLocaleString('en-IN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    }).replace(',', '') + ' LOCAL';
  }
}, 1000);

/* ── Health ──────────────────────────────────────────────────── */
async function checkHealth() {
  try {
    const res = await api('/health');
    const ok = res.ok;
    document.getElementById('statusDot').className = `status-dot ${ok ? 'ok' : 'error'}`;
    document.getElementById('statusText').textContent = ok ? 'ONLINE' : 'ERROR';
  } catch {
    document.getElementById('statusDot').className = 'status-dot error';
    document.getElementById('statusText').textContent = 'OFFLINE';
  }
}
checkHealth();
setInterval(checkHealth, 30000);

/* ── Views ───────────────────────────────────────────────────── */
function showView(view) {
  state.currentView = view;
  document.getElementById('viewDashboard').classList.toggle('hidden', view !== 'dashboard');
  document.getElementById('viewJobs').classList.toggle('hidden', view !== 'jobs');
  document.getElementById('navDashboard').classList.toggle('active', view === 'dashboard');
  document.getElementById('navJobs').classList.toggle('active', view === 'jobs');

  if (view === 'jobs') loadJobs();
  else loadReports();
}

/* ── Auth ────────────────────────────────────────────────────── */
function openAuthModal(mode = 'login') {
  document.getElementById('authModal').classList.remove('hidden');
  if (mode === 'login') switchToLogin();
  else switchToSignup();
}

function closeAuthModal() {
  document.getElementById('authModal').classList.add('hidden');
  clearAuthError();
}

function switchToLogin() {
  document.getElementById('authModalTitle').textContent = '// SIGN IN';
  document.getElementById('loginForm').classList.remove('hidden');
  document.getElementById('signupForm').classList.add('hidden');
  clearAuthError();
}

function switchToSignup() {
  document.getElementById('authModalTitle').textContent = '// CREATE ACCOUNT';
  document.getElementById('loginForm').classList.add('hidden');
  document.getElementById('signupForm').classList.remove('hidden');
  clearAuthError();
}

function showAuthError(msg) {
  const el = document.getElementById('authError');
  el.textContent = msg;
  el.classList.remove('hidden');
}

function clearAuthError() {
  document.getElementById('authError').classList.add('hidden');
}

async function handleLogin() {
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  if (!email || !password) return showAuthError('Email and password required');

  try {
    const res = await fetch(API_BASE + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) return showAuthError(data.detail || 'Login failed');
    setAuth(data.access_token, data.user);
    closeAuthModal();
    loadReports();
  } catch {
    showAuthError('Network error');
  }
}

async function handleSignup() {
  const username = document.getElementById('signupUsername').value.trim();
  const email = document.getElementById('signupEmail').value.trim();
  const password = document.getElementById('signupPassword').value;
  if (!username || !email || !password) return showAuthError('All fields required');

  try {
    const res = await fetch(API_BASE + '/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    });
    const data = await res.json();
    if (!res.ok) return showAuthError(data.detail || 'Signup failed');
    setAuth(data.access_token, data.user);
    closeAuthModal();
    loadReports();
  } catch {
    showAuthError('Network error');
  }
}

function setAuth(token, user) {
  state.token = token;
  state.user = user;
  localStorage.setItem('ai_pm_token', token);
  localStorage.setItem('ai_pm_user', JSON.stringify(user));
  renderUserArea();
}

function signOut() {
  state.token = null;
  state.user = null;
  localStorage.removeItem('ai_pm_token');
  localStorage.removeItem('ai_pm_user');
  renderUserArea();
  loadReports();
}

function renderUserArea() {
  const area = document.getElementById('userArea');
  if (state.user) {
    area.innerHTML = `
      <div class="user-info">
        <span class="user-chip">@<span>${esc(state.user.username)}</span></span>
        <button class="btn-signout" onclick="signOut()">SIGN OUT</button>
      </div>`;
    
    // Update Webhook URL
    const baseUrl = window.location.origin;
    const webhookUrl = `${baseUrl}/api/webhook/github/${state.user.webhook_secret}`;
    const input = document.getElementById('webhookUrlInput');
    if (input) input.value = webhookUrl;
    document.getElementById('webhookInfoPanel')?.classList.remove('hidden');
  } else {
    area.innerHTML = `<button class="btn-ghost" onclick="openAuthModal()">SIGN IN</button>`;
    document.getElementById('webhookInfoPanel')?.classList.add('hidden');
  }
}

function copyWebhookUrl() {
  const input = document.getElementById('webhookUrlInput');
  input.select();
  document.execCommand('copy');
  const btn = event.target;
  const originalText = btn.textContent;
  btn.textContent = 'COPIED!';
  setTimeout(() => btn.textContent = originalText, 2000);
}

/* ── Trend Chart ─────────────────────────────────────────────── */
async function loadTrendChart() {
  try {
    const res = await api('/reports/trend?days=30');
    if (!res.ok) return;
    const data = await res.json();
    if (!data.length) return;

    const canvas = document.getElementById('trendChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const scores = data.map(d => d.avg_score);
    const max = Math.max(...scores, 1);
    const step = w / (scores.length - 1 || 1);

    // Draw sparkline
    ctx.strokeStyle = '#f0a500';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    scores.forEach((s, i) => {
      const x = i * step;
      const y = h - (s / max) * (h - 4) - 2;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Fill gradient
    ctx.lineTo((scores.length - 1) * step, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = 'rgba(240,165,0,0.08)';
    ctx.fill();
  } catch { /* silent */ }
}

/* ── Filters ─────────────────────────────────────────────────── */
function setFilter(filter) {
  state.activeFilter = filter;
  document.querySelectorAll('.pill').forEach(p => {
    p.classList.toggle('active', p.dataset.filter === filter);
  });
  renderReportsList();
}

function setSortAndReload(sort) {
  state.activeSort = sort;
  renderReportsList();
}

function debounceFilter() {
  clearTimeout(state.filterDebounceTimer);
  state.filterDebounceTimer = setTimeout(() => {
    state.searchQuery = document.getElementById('searchInput').value.trim().toLowerCase();
    renderReportsList();
  }, 250);
}

function filterReports(reports) {
  let filtered = [...reports];
  if (state.searchQuery) {
    filtered = filtered.filter(r =>
      r.repository.toLowerCase().includes(state.searchQuery) ||
      r.branch.toLowerCase().includes(state.searchQuery)
    );
  }
  if (state.activeFilter === 'high') {
    filtered = filtered.filter(r => r.severity_score >= 7);
  }
  // Sort
  if (state.activeSort === 'severity') filtered.sort((a,b) => b.severity_score - a.severity_score);
  else if (state.activeSort === 'issues') filtered.sort((a,b) => b.issue_count - a.issue_count);
  else filtered.sort((a,b) => new Date(b.created_at) - new Date(a.created_at));
  return filtered;
}

/* ── Reports ─────────────────────────────────────────────────── */
async function loadReports() {
  const listEl = document.getElementById('reportsList');
  listEl.innerHTML = '<div class="state-loading"><span class="blink">█</span> Loading...</div>';

  try {
    const res = await api('/reports?limit=100');
    state.reports = await res.json();
    renderStats(state.reports);
    renderReportsList();
    loadTrendChart();
  } catch (e) {
    listEl.innerHTML = `<div class="state-loading" style="color:var(--red)">Error: ${esc(e.message)}</div>`;
  }
}

function renderStats(reports) {
  document.getElementById('statTotal').textContent = reports.length;
  document.getElementById('statCritical').textContent = reports.filter(r => r.severity_score >= 7).length;
  const avg = reports.length
    ? (reports.reduce((a, r) => a + r.severity_score, 0) / reports.length).toFixed(1)
    : '0.0';
  document.getElementById('statAvg').textContent = avg;
  document.getElementById('statLast').textContent = reports[0] ? fmtDate(reports[0].created_at) : '—';
  document.getElementById('apiEndpoint').textContent = `API: ${API_BASE || 'localhost:8000'}`;
}

function renderReportsList() {
  const listEl = document.getElementById('reportsList');
  const filtered = filterReports(state.reports);
  document.getElementById('reportCount').textContent = `${filtered.length} reports`;

  if (!filtered.length) {
    listEl.innerHTML = '<div class="state-loading">No reports match current filters.</div>';
    return;
  }

  listEl.innerHTML = filtered.map(r => `
    <div class="report-row ${r.id === state.currentReportId ? 'active' : ''}" onclick="loadDetail('${r.id}')">
      <div>
        <div class="rr-repo">${esc(r.repository)}</div>
        <div class="rr-meta">${esc(r.branch)} · ${esc(r.commit_id)} · ${r.issue_count} issues</div>
        <div class="rr-date">${fmtDate(r.created_at)}</div>
      </div>
      <span class="sev-badge ${sevClass(r.severity_score)}">${r.severity_score.toFixed(1)}</span>
    </div>
  `).join('');
}

async function loadDetail(id) {
  state.currentReportId = id;
  renderReportsList(); // update active state

  const detailEl = document.getElementById('reportDetail');
  detailEl.innerHTML = '<div class="state-loading"><span class="blink">█</span> Fetching analysis...</div>';
  document.getElementById('detailActions').style.display = 'none';

  try {
    const res = await api(`/reports/${id}`);
    if (!res.ok) throw new Error('Report not found');
    const report = await res.json();

    document.getElementById('detailTitle').textContent = `// ${report.repository.split('/').pop().toUpperCase()}`;

    // Score pill
    const score = report.severity_score;
    const scoreEl = document.getElementById('detailScore');
    scoreEl.textContent = `${score}/10`;
    scoreEl.className = `score-pill ${score >= 7 ? 'score-high' : score >= 4 ? 'score-med' : 'score-low'}`;

    document.getElementById('detailActions').style.display = 'flex';

    // Auto-fix button (only for authenticated users with GH token)
    const fixBtn = document.getElementById('autofixBtn');
    if (state.user && state.user.github_username) {
      fixBtn.style.display = 'inline-block';
      fixBtn.disabled = false;
      fixBtn.onclick = () => triggerAutoFix(id);
    } else {
      fixBtn.style.display = 'none';
    }

    const summary = `
      <div class="detail-summary">
        <div class="ds-cell"><div class="ds-label">REPOSITORY</div><div class="ds-value">${esc(report.repository)}</div></div>
        <div class="ds-cell"><div class="ds-label">COMMIT</div><div class="ds-value">${esc(report.commit_id.slice(0,8))}</div></div>
        <div class="ds-cell"><div class="ds-label">BRANCH</div><div class="ds-value">${esc(report.branch)}</div></div>
      </div>
    `;

    const autofixBanner = report.autofix_pr_url ? `
      <div class="autofix-banner">
        ⚡ Auto-fix PR opened:
        <a href="${esc(report.autofix_pr_url)}" target="_blank" class="autofix-link">View Pull Request →</a>
      </div>
    ` : '';

    if (!report.issues?.length) {
      detailEl.innerHTML = summary + autofixBanner + '<div class="state-empty"><div class="empty-glyph">✓</div><p>No issues detected — clean build!</p></div>';
      return;
    }

    // Filter issues if a type filter is active
    let issues = report.issues;
    if (state.activeFilter && !['all','high'].includes(state.activeFilter)) {
      issues = issues.filter(({issue}) => issue.type === state.activeFilter);
    }

    const cards = issues.map(({issue, suggestion}) => `
      <div class="issue-card">
        <div class="issue-hdr">
          <span class="type-badge type-${esc(issue.type)}">${issue.type.toUpperCase()}</span>
          <span class="issue-loc">${esc(issue.file)}:${issue.line}</span>
          <span class="issue-tool">${esc(issue.tool)}</span>
        </div>
        <div class="issue-msg">${esc(issue.message)}</div>
        ${suggestion ? `
        <div class="ai-block">
          <div class="ai-section-label">AI ANALYSIS</div>
          <div class="ai-text"><strong>Explanation:</strong> ${esc(suggestion.explanation)}</div>
          <div class="ai-text"><strong>Fix:</strong> ${esc(suggestion.fix)}</div>
          ${suggestion.improved_code ? `
            <div class="ai-section-label" style="margin-top:0.8rem">IMPROVED CODE</div>
            <div class="code-block">${esc(suggestion.improved_code)}</div>
          ` : ''}
        </div>` : ''}
      </div>
    `).join('');

    detailEl.innerHTML = summary + autofixBanner + cards;

  } catch (e) {
    detailEl.innerHTML = `<div class="state-loading" style="color:var(--red)">Error: ${esc(e.message)}</div>`;
  }
}

/* ── Auto-Fix ────────────────────────────────────────────────── */
async function triggerAutoFix(reportId) {
  if (!state.user) return openAuthModal();
  const btn = document.getElementById('autofixBtn');
  btn.disabled = true;
  btn.textContent = '⏳ QUEUING...';

  try {
    const res = await api(`/reports/${reportId}/autofix`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to queue autofix');
    btn.textContent = '✓ QUEUED';
    showView('jobs');
    setTimeout(loadJobs, 1000);
  } catch (e) {
    btn.disabled = false;
    btn.textContent = '⚡ AUTO-FIX PR';
    alert('Auto-fix error: ' + e.message);
  }
}

/* ── Jobs ────────────────────────────────────────────────────── */
async function loadJobs() {
  const listEl = document.getElementById('jobsList');
  if (!listEl) return;

  try {
    const res = await api('/jobs?limit=30');
    const jobs = await res.json();

    // Update badge
    const activeCount = jobs.filter(j => j.status === 'processing' || j.status === 'pending').length;
    const badge = document.getElementById('activeJobsBadge');
    if (activeCount > 0) {
      badge.textContent = activeCount;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }

    if (!jobs.length) {
      listEl.innerHTML = '<div class="state-loading">No jobs yet. Configure a GitHub webhook to trigger analysis.</div>';
      return;
    }

    listEl.innerHTML = jobs.map(job => `
      <div class="job-card job-${job.status}">
        <div class="job-status-dot"></div>
        <div class="job-info">
          <div class="job-repo">${esc(job.repository)}</div>
          <div class="job-meta">${esc(job.branch)} · ${esc(job.commit_sha.slice(0,8))} · ${fmtDate(job.created_at)}</div>
          ${job.error_message ? `<div class="job-meta" style="color:var(--red)">${esc(job.error_message)}</div>` : ''}
        </div>
        <span class="job-status-label">${job.status.toUpperCase()}</span>
        ${job.report_id ? `<a href="#" class="job-action" onclick="showReportFromJob('${job.report_id}')">VIEW REPORT →</a>` : '<span></span>'}
      </div>
    `).join('');

    // Auto-poll if there are active jobs
    if (activeCount > 0) {
      clearTimeout(state.jobPollTimer);
      state.jobPollTimer = setTimeout(loadJobs, 3000);
    }

  } catch (e) {
    if (listEl) listEl.innerHTML = `<div class="state-loading" style="color:var(--red)">Error: ${esc(e.message)}</div>`;
  }
}

function showReportFromJob(reportId) {
  showView('dashboard');
  setTimeout(() => loadDetail(reportId), 100);
}

/* ── Init ────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  renderUserArea();
  loadReports();
  // Poll for active jobs every 5s even on dashboard
  setInterval(() => {
    api('/jobs?limit=30&status=processing')
      .then(r => r.json())
      .then(jobs => {
        const badge = document.getElementById('activeJobsBadge');
        if (jobs.length > 0) {
          badge.textContent = jobs.length;
          badge.classList.remove('hidden');
          if (state.currentView === 'jobs') loadJobs();
          else loadReports(); // refresh reports if a job just completed
        } else {
          badge.classList.add('hidden');
        }
      })
      .catch(() => {});
  }, 5000);
});

// Close modal on backdrop click
document.getElementById('authModal')?.addEventListener('click', function(e) {
  if (e.target === this) closeAuthModal();
});
