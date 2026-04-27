/* ══════════════════════════════════════════════════════════════
   CodeSense — App JS
   - User-scoped data: all API calls include JWT
   - Auth gates on every data view
   - Clean SPA routing
══════════════════════════════════════════════════════════════ */

const API_BASE = '/api';

/* ── State ─────────────────────────────────────────────────── */
const state = {
  token: localStorage.getItem('cs_token') || null,
  user: (() => { try { return JSON.parse(localStorage.getItem('cs_user') || 'null'); } catch { return null; } })(),
  reports: [],
  currentReportId: null,
  currentPage: 'overview',
  activeFilter: 'all',
  activeSort: 'newest',
  searchQuery: '',
  pollTimer: null,
  filterTimer: null,
};

/* ── API Helper ─────────────────────────────────────────────── */
function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  return fetch(API_BASE + path, { ...opts, headers });
}

/* ── Utilities ─────────────────────────────────────────────── */
function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function sevClass(score) {
  return score >= 7 ? 'sev-high' : score >= 4 ? 'sev-med' : 'sev-low';
}

function fmtDate(iso) {
  if (!iso) return '—';
  const s = iso.includes('Z') || iso.includes('+') ? iso : iso + 'Z';
  const d = new Date(s);
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) + ' ' +
    d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
}

function repoShort(full) {
  return full ? full.split('/').pop() : '—';
}

/* ── Page Routing ───────────────────────────────────────────── */
function showPage(name) {
  state.currentPage = name;
  document.querySelectorAll('.page').forEach(p => {
    p.classList.remove('active');
    p.classList.add('hidden');
  });
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  
  const activePage = document.getElementById('page' + name.charAt(0).toUpperCase() + name.slice(1));
  if (activePage) {
    activePage.classList.add('active');
    activePage.classList.remove('hidden');
  }
  
  document.getElementById('nav' + name.charAt(0).toUpperCase() + name.slice(1))?.classList.add('active');

  if (name === 'overview') loadOverview();
  else if (name === 'reports') loadReports();
  else if (name === 'jobs') loadJobs();
  else if (name === 'setup') renderSetup();
}

/* ── Health Check ───────────────────────────────────────────── */
async function checkHealth() {
  try {
    const res = await fetch(API_BASE + '/health');
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    if (res.ok) {
      dot.className = 'status-dot ok';
      txt.textContent = 'API online';
    } else {
      dot.className = 'status-dot error';
      txt.textContent = 'API error';
    }
  } catch {
    document.getElementById('statusDot').className = 'status-dot error';
    document.getElementById('statusText').textContent = 'Offline';
  }
}

/* ── Auth Modal ─────────────────────────────────────────────── */
function openAuthModal(mode = 'login') {
  document.getElementById('authModal').classList.remove('hidden');
  mode === 'login' ? switchToLogin() : switchToSignup();
}

function closeAuthModal() {
  document.getElementById('authModal').classList.add('hidden');
  clearAuthError();
}

function switchToLogin() {
  document.getElementById('authModalTitle').textContent = 'Welcome back';
  document.getElementById('authModalSub').textContent = 'Sign in to your account';
  document.getElementById('loginForm').classList.remove('hidden');
  document.getElementById('signupForm').classList.add('hidden');
  clearAuthError();
}

function switchToSignup() {
  document.getElementById('authModalTitle').textContent = 'Create an account';
  document.getElementById('authModalSub').textContent = 'Start analyzing your code today';
  document.getElementById('loginForm').classList.add('hidden');
  document.getElementById('signupForm').classList.remove('hidden');
  clearAuthError();
}

function showAuthError(msg) {
  const el = document.getElementById('authError');
  el.textContent = msg;
  el.classList.remove('hidden');
}
function clearAuthError() { document.getElementById('authError').classList.add('hidden'); }

async function handleLogin() {
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  if (!email || !password) return showAuthError('Email and password required');

  const btn = document.querySelector('#loginForm .btn-primary');
  btn.textContent = 'Signing in...';
  btn.disabled = true;

  try {
    const res = await fetch(API_BASE + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) { showAuthError(data.detail || 'Login failed'); return; }
    setAuth(data.access_token, data.user);
    closeAuthModal();
    showPage('overview');
  } catch { showAuthError('Network error — check your connection'); }
  finally { btn.textContent = 'Sign in'; btn.disabled = false; }
}

async function handleSignup() {
  const username = document.getElementById('signupUsername').value.trim();
  const email = document.getElementById('signupEmail').value.trim();
  const password = document.getElementById('signupPassword').value;
  if (!username || !email || !password) return showAuthError('All fields required');
  if (password.length < 6) return showAuthError('Password must be at least 6 characters');

  const btn = document.querySelector('#signupForm .btn-primary');
  btn.textContent = 'Creating account...';
  btn.disabled = true;

  try {
    const res = await fetch(API_BASE + '/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password }),
    });
    const data = await res.json();
    if (!res.ok) { showAuthError(data.detail || 'Signup failed'); return; }
    setAuth(data.access_token, data.user);
    closeAuthModal();
    showPage('setup'); // Take new users to setup
  } catch { showAuthError('Network error'); }
  finally { btn.textContent = 'Create account'; btn.disabled = false; }
}

function setAuth(token, user) {
  state.token = token;
  state.user = user;
  localStorage.setItem('cs_token', token);
  localStorage.setItem('cs_user', JSON.stringify(user));
  renderUserUI();
}

function signOut() {
  state.token = null;
  state.user = null;
  state.reports = [];
  localStorage.removeItem('cs_token');
  localStorage.removeItem('cs_user');
  renderUserUI();
  showPage('overview');
}

function renderUserUI() {
  const user = state.user;
  const sidebarUser = document.getElementById('sidebarUser');
  const signOutBtn = document.getElementById('signOutBtn');
  const signInBtn = document.getElementById('signInBtnSidebar');

  if (user) {
    // Sidebar user info
    sidebarUser.classList.remove('hidden');
    document.getElementById('userAvatar').textContent = user.username.charAt(0).toUpperCase();
    document.getElementById('userName').textContent = user.username;
    document.getElementById('userEmail').textContent = user.email;
    signOutBtn.classList.remove('hidden');
    signInBtn.classList.add('hidden');
  } else {
    sidebarUser.classList.add('hidden');
    signOutBtn.classList.add('hidden');
    signInBtn.classList.remove('hidden');
  }
}

/* ── Overview Page ─────────────────────────────────────────── */
async function loadOverview() {
  const gate = document.getElementById('overviewAuthGate');
  const content = document.getElementById('overviewContent');
  const sub = document.getElementById('overviewSub');

  if (!state.user) {
    gate.classList.remove('hidden');
    content.classList.add('hidden');
    sub.textContent = 'Your code intelligence dashboard';
    return;
  }

  gate.classList.add('hidden');
  content.classList.remove('hidden');
  sub.textContent = `Welcome back, ${state.user.username}`;

  try {
    const res = await api('/reports?limit=100');
    if (res.status === 401) { signOut(); return; }
    const reports = await res.json();
    state.reports = Array.isArray(reports) ? reports : [];
    renderOverviewStats(state.reports);
    renderOverviewRecent(state.reports);
  } catch (e) {
    document.getElementById('overviewRecentList').innerHTML =
      `<div class="empty-state"><p style="color:var(--red)">Error loading data: ${esc(e.message)}</p></div>`;
  }

  // Check active jobs
  try {
    const res = await api('/jobs?limit=10&status=processing');
    if (res.ok) {
      const jobs = await res.json();
      const section = document.getElementById('overviewJobsSection');
      if (jobs.length > 0) {
        section.style.display = 'block';
        document.getElementById('overviewJobsList').innerHTML = jobs.slice(0, 3).map(j => jobRowHTML(j)).join('');
      } else {
        section.style.display = 'none';
      }
    }
  } catch { }
}

function renderOverviewStats(reports) {
  document.getElementById('statTotal').textContent = reports.length;
  document.getElementById('statCritical').textContent = reports.filter(r => r.severity_score >= 7).length;
  const avg = reports.length
    ? (reports.reduce((a, r) => a + r.severity_score, 0) / reports.length).toFixed(1) : '0.0';
  document.getElementById('statAvg').textContent = avg;
  document.getElementById('statLast').textContent = reports[0] ? fmtDate(reports[0].created_at) : 'No scans yet';
}

function renderOverviewRecent(reports) {
  const el = document.getElementById('overviewRecentList');
  if (!reports.length) {
    el.innerHTML = `
      <div class="empty-state">
        <h3>No scans yet</h3>
        <p>Connect a repository to get started</p>
      </div>`;
    return;
  }
  el.innerHTML = reports.slice(0, 5).map(r => `
    <div class="recent-item" onclick="goToReport('${r.id}')">
      <div>
        <div class="recent-repo">${esc(r.repository)}</div>
        <div class="recent-meta">${esc(r.branch)} · ${esc(r.commit_id)} · ${r.issue_count} issues · ${fmtDate(r.created_at)}</div>
      </div>
      <span class="sev-chip ${sevClass(r.severity_score)}">${r.severity_score.toFixed(1)}</span>
    </div>
  `).join('');
}

function goToReport(id) {
  showPage('reports');
  setTimeout(() => loadDetail(id), 50);
}

/* ── Reports Page ──────────────────────────────────────────── */
async function loadReports() {
  if (!state.user) {
    document.getElementById('reportsList').innerHTML =
      `<div class="empty-state"><p>Please <span class="link" onclick="openAuthModal()">sign in</span> to view reports</p></div>`;
    return;
  }

  document.getElementById('reportsList').innerHTML =
    '<div class="skeleton-list"><div class="skeleton-row"></div><div class="skeleton-row"></div><div class="skeleton-row"></div></div>';

  try {
    const res = await api('/reports?limit=100');
    if (res.status === 401) { signOut(); return; }
    state.reports = await res.json();
    renderReportsList();
  } catch (e) {
    document.getElementById('reportsList').innerHTML =
      `<div class="empty-state"><p style="color:var(--red)">Error: ${esc(e.message)}</p></div>`;
  }
}

function filterReports(reports) {
  let filtered = [...reports];
  if (state.searchQuery) {
    const q = state.searchQuery.toLowerCase();
    filtered = filtered.filter(r =>
      r.repository.toLowerCase().includes(q) || r.branch.toLowerCase().includes(q)
    );
  }
  if (state.activeFilter === 'high') filtered = filtered.filter(r => r.severity_score >= 7);
  else if (['security', 'error', 'warning', 'dependency'].includes(state.activeFilter)) {
    // Filter is shown in detail, list shows all but we note filter
  }
  if (state.activeSort === 'severity') filtered.sort((a, b) => b.severity_score - a.severity_score);
  else if (state.activeSort === 'issues') filtered.sort((a, b) => b.issue_count - a.issue_count);
  else filtered.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  return filtered;
}

function renderReportsList() {
  const el = document.getElementById('reportsList');
  const filtered = filterReports(state.reports);
  document.getElementById('reportCount').textContent =
    `${filtered.length} of ${state.reports.length} reports`;

  // Update badge
  const badge = document.getElementById('reportsBadge');
  if (state.reports.length > 0) { badge.textContent = state.reports.length; badge.classList.remove('hidden'); }
  else badge.classList.add('hidden');

  if (!filtered.length) {
    el.innerHTML = `<div class="empty-state"><p>${state.reports.length ? 'No reports match your filters.' : 'No scans yet — connect a repository to get started.'}</p></div>`;
    return;
  }

  el.innerHTML = filtered.map(r => `
    <div class="report-row ${r.id === state.currentReportId ? 'active' : ''}" onclick="loadDetail('${r.id}')">
      <div class="rr-body">
        <div class="rr-repo" title="${esc(r.repository)}">${esc(r.repository)}</div>
        <div class="rr-meta">${esc(r.branch)} · ${esc(r.commit_id)} · ${r.issue_count} issues</div>
        <div class="rr-date">${fmtDate(r.created_at)}</div>
      </div>
      <span class="sev-chip ${sevClass(r.severity_score)}">${r.severity_score.toFixed(1)}</span>
    </div>
  `).join('');
}

function setFilter(filter, btn) {
  state.activeFilter = filter;
  document.querySelectorAll('.filter-tabs .tab').forEach(t => t.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderReportsList();
}

function debounceFilter() {
  clearTimeout(state.filterTimer);
  state.filterTimer = setTimeout(() => {
    state.searchQuery = document.getElementById('searchInput').value.trim();
    renderReportsList();
  }, 200);
}

/* ── Report Detail ─────────────────────────────────────────── */
async function loadDetail(id) {
  state.currentReportId = id;
  renderReportsList();

  const emptyEl = document.getElementById('reportDetailEmpty');
  const detailEl = document.getElementById('reportDetail');

  emptyEl.classList.add('hidden');
  detailEl.classList.remove('hidden');
  detailEl.innerHTML = `
    <div class="skeleton-list" style="padding:20px">
      <div class="skeleton-row"></div>
      <div class="skeleton-row tall"></div>
      <div class="skeleton-row tall"></div>
    </div>`;

  try {
    const res = await api(`/reports/${id}`);
    if (!res.ok) throw new Error('Report not found');
    const report = await res.json();

    let issues = report.issues || [];
    if (!['all', 'high'].includes(state.activeFilter) && ['security', 'error', 'warning', 'dependency'].includes(state.activeFilter)) {
      issues = issues.filter(({ issue }) => issue.type === state.activeFilter);
    }

    const score = report.severity_score;
    const scoreClass = sevClass(score);

    const autoFixBanner = report.autofix_pr_url ? `
      <div class="autofix-banner">
        ⚡ Auto-fix PR opened:
        <a href="${esc(report.autofix_pr_url)}" target="_blank" class="autofix-link">View Pull Request →</a>
      </div>` : '';

    const canAutoFix = state.user && state.user.github_username;

    detailEl.innerHTML = `
      <div class="detail-header">
        <div class="detail-header-left">
          <h2>${esc(report.repository)}</h2>
          <p>${esc(report.branch)} · ${esc(report.commit_id.slice(0, 8))}</p>
        </div>
        <div class="detail-actions">
          <span class="sev-chip score-badge ${scoreClass}">${score.toFixed(1)}/10</span>
          ${canAutoFix ? `<button class="btn-primary small" id="autofixBtn" onclick="triggerAutoFix('${id}')">⚡ Auto-fix PR</button>` : ''}
          <button class="btn-ghost small" onclick="confirmDeleteReport('${id}')">Delete</button>
        </div>
      </div>
      <div class="detail-meta-row">
        <div class="detail-meta-cell">
          <div class="dmc-label">Repository</div>
          <div class="dmc-value">${esc(report.repository)}</div>
        </div>
        <div class="detail-meta-cell">
          <div class="dmc-label">Commit</div>
          <div class="dmc-value">${esc(report.commit_id.slice(0, 8))}</div>
        </div>
        <div class="detail-meta-cell">
          <div class="dmc-label">Issues Found</div>
          <div class="dmc-value">${report.issues.length}</div>
        </div>
      </div>
      <div class="detail-body">
        ${autoFixBanner}
        ${issues.length === 0 && report.issues.length === 0 ? `
          <div class="empty-success">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="20" stroke="#22C55E" stroke-width="2"/><path d="M16 24l6 6 10-12" stroke="#22C55E" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            <h3>All clear!</h3>
            <p>No issues detected in this commit.</p>
          </div>
        ` : issues.length === 0 ? `
          <div class="empty-state"><p>No ${state.activeFilter} issues in this report.</p></div>
        ` : issues.map(({ issue, suggestion }) => `
          <div class="issue-card">
            <div class="issue-hdr">
              <span class="type-badge type-${esc(issue.type)}">${esc(issue.type)}</span>
              <span class="issue-loc">${esc(issue.file)}:${issue.line}</span>
              <span class="issue-tool">${esc(issue.tool)}</span>
            </div>
            <div class="issue-msg">${esc(issue.message)}</div>
            ${suggestion ? `
              <div class="ai-block">
                <div class="ai-label">AI Analysis</div>
                <div class="ai-line"><strong>Root cause:</strong> ${esc(suggestion.explanation)}</div>
                <div class="ai-line"><strong>Fix:</strong> ${esc(suggestion.fix)}</div>
                ${suggestion.improved_code ? `
                  <div class="ai-line" style="margin-top:10px"><strong>Corrected code:</strong></div>
                  <div class="code-block">${esc(suggestion.improved_code)}</div>
                ` : ''}
              </div>
            ` : ''}
          </div>
        `).join('')}
      </div>`;
  } catch (e) {
    detailEl.innerHTML = `<div class="empty-state"><p style="color:var(--red)">Error: ${esc(e.message)}</p></div>`;
  }
}

/* ── Auto-Fix ────────────────────────────────────────────────── */
async function triggerAutoFix(reportId) {
  const btn = document.getElementById('autofixBtn');
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = 'Queuing...';

  try {
    const res = await api(`/reports/${reportId}/autofix`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed');
    btn.textContent = '✓ Queued!';
    setTimeout(() => showPage('jobs'), 800);
  } catch (e) {
    btn.disabled = false;
    btn.textContent = '⚡ Auto-fix PR';
    alert('Auto-fix error: ' + e.message);
  }
}

async function confirmDeleteReport(reportId) {
  if (!confirm('Delete this report? This cannot be undone.')) return;
  try {
    const res = await api(`/reports/${reportId}`, { method: 'DELETE' });
    if (res.ok) {
      state.currentReportId = null;
      document.getElementById('reportDetail').classList.add('hidden');
      document.getElementById('reportDetailEmpty').classList.remove('hidden');
      await loadReports();
    } else {
      const err = await res.json().catch(() => ({}));
      alert('Delete failed: ' + (err.detail || res.statusText || 'Unknown error'));
    }
  } catch (e) { alert('Delete failed: ' + e.message); }
}

/* ── Jobs Page ──────────────────────────────────────────────── */
async function loadJobs() {
  const el = document.getElementById('jobsList');
  if (!el) return;

  if (!state.user) {
    el.innerHTML = `<div class="empty-state"><p>Please <span class="link" onclick="openAuthModal()">sign in</span> to view jobs</p></div>`;
    return;
  }

  try {
    const res = await api('/jobs?limit=50');
    if (res.status === 401) { signOut(); return; }
    const jobs = await res.json();

    // Update badge
    const activeJobs = jobs.filter(j => j.status === 'processing' || j.status === 'pending');
    const badge = document.getElementById('jobsBadge');
    if (activeJobs.length > 0) { badge.textContent = activeJobs.length; badge.classList.remove('hidden'); }
    else badge.classList.add('hidden');

    if (!jobs.length) {
      el.innerHTML = `<div class="empty-state"><h3>No jobs yet</h3><p>Jobs appear here when GitHub pushes trigger analysis via your webhook.</p></div>`;
      return;
    }

    el.innerHTML = jobs.map(j => jobRowHTML(j)).join('');

    if (activeJobs.length > 0) {
      clearTimeout(state.pollTimer);
      state.pollTimer = setTimeout(() => {
        if (state.currentPage === 'jobs') loadJobs();
        else loadBadgesOnly();
      }, 3000);
    }
  } catch (e) { el.innerHTML = `<div class="empty-state"><p style="color:var(--red)">Error: ${esc(e.message)}</p></div>`; }
}

function jobRowHTML(job) {
  return `
    <div class="job-card job-${job.status}">
      <div class="job-indicator"></div>
      <div>
        <div class="job-repo">${esc(job.repository)}</div>
        <div class="job-meta">${esc(job.branch)} · ${esc(job.commit_sha.slice(0, 8))} · ${fmtDate(job.created_at)}</div>
        ${job.error_message ? `<div class="job-err">${esc(job.error_message)}</div>` : ''}
      </div>
      <span class="job-status">${job.status}</span>
      ${job.report_id
      ? `<a class="job-action" href="#" onclick="goToReport('${job.report_id}');return false;">View report →</a>`
      : '<span></span>'}
    </div>`;
}

/* ── Background Badge Polling ───────────────────────────────── */
async function loadBadgesOnly() {
  if (!state.user) return;
  try {
    const res = await api('/jobs?limit=20&status=processing');
    if (!res.ok) return;
    const jobs = await res.json();
    const badge = document.getElementById('jobsBadge');
    if (jobs.length > 0) { badge.textContent = jobs.length; badge.classList.remove('hidden'); }
    else { badge.classList.add('hidden'); }
  } catch { }
}

/* ── Setup Page ─────────────────────────────────────────────── */
function renderSetup() {
  const urlSection = document.getElementById('webhookUrlSection');
  const authNeeded = document.getElementById('webhookAuthNeeded');
  const ghConnected = document.getElementById('ghTokenConnected');
  const ghForm = document.getElementById('ghTokenForm');

  if (state.user) {
    urlSection.classList.remove('hidden');
    authNeeded.classList.add('hidden');
    const baseUrl = window.location.origin;
    document.getElementById('webhookUrlInput').value =
      `${baseUrl}/api/webhook/github/${state.user.webhook_secret}`;

    // GitHub token status
    if (state.user.github_username) {
      ghConnected.classList.remove('hidden');
      ghForm.classList.add('hidden');
      document.getElementById('ghUsername').textContent = state.user.github_username;
    } else {
      ghConnected.classList.add('hidden');
      ghForm.classList.remove('hidden');
    }
  } else {
    urlSection.classList.add('hidden');
    authNeeded.classList.remove('hidden');
    ghConnected.classList.add('hidden');
    ghForm.classList.add('hidden');
  }
}

function copyWebhookUrl() {
  const input = document.getElementById('webhookUrlInput');
  input.select();
  document.execCommand('copy');
  const btn = event.target;
  const orig = btn.textContent;
  btn.textContent = 'Copied!';
  setTimeout(() => btn.textContent = orig, 2000);
}

async function regenerateSecret() {
  if (!confirm('This will invalidate your current webhook URL. All existing webhooks must be updated. Continue?')) return;
  try {
    const res = await api('/auth/webhook/regenerate', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      state.user.webhook_secret = data.webhook_secret;
      localStorage.setItem('cs_user', JSON.stringify(state.user));
      renderSetup();
    }
  } catch (e) { alert('Error: ' + e.message); }
}

async function connectGitHub() {
  const token = document.getElementById('ghTokenInput').value.trim();
  if (!token) return alert('Please enter a GitHub token');
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = 'Connecting...';
  try {
    const res = await api('/auth/github/connect', {
      method: 'POST',
      body: JSON.stringify({ github_token: token }),
    });
    const data = await res.json();
    if (!res.ok) { alert(data.detail || 'Failed to connect GitHub'); return; }
    state.user.github_username = data.github_username;
    localStorage.setItem('cs_user', JSON.stringify(state.user));
    document.getElementById('ghTokenInput').value = '';
    renderSetup();
  } catch (e) { alert('Error: ' + e.message); }
  finally { btn.disabled = false; btn.textContent = 'Connect GitHub'; }
}

async function disconnectGitHub() {
  if (!confirm('Disconnect GitHub? Auto-fix PRs will no longer work.')) return;
  try {
    await api('/auth/github/disconnect', { method: 'DELETE' });
    state.user.github_username = null;
    localStorage.setItem('cs_user', JSON.stringify(state.user));
    renderSetup();
  } catch (e) { alert('Error: ' + e.message); }
}

/* ── Init ────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  renderUserUI();
  checkHealth();
  setInterval(checkHealth, 30000);
  setInterval(loadBadgesOnly, 5000);

  showPage('overview');

  // Close modal on backdrop click
  document.getElementById('authModal')?.addEventListener('click', e => {
    if (e.target === e.currentTarget) closeAuthModal();
  });
});