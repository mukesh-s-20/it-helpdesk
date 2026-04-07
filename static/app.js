/* ═══════════════════════════════════════════════════════════
   IT Helpdesk Incident Triage · OpenEnv — app.js
   ═══════════════════════════════════════════════════════════ */

'use strict';

/* ── State ── */
const S = {
  taskId: 'easy_vpn_lock',
  taskData: null,
  lastStep: null,
  lastGrade: null,
  episodeDone: false,
  usedActions: new Set(),
  validActions: [],
  invalidActions: [],
};

/* ── DOM helpers ── */
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

/* ── Panel navigation ── */
function showPanel(name, btn) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const p = $('panel-' + name);
  if (p) p.classList.add('active');
  if (btn) btn.classList.add('active');
  else {
    const nb = document.querySelector(`[data-panel="${name}"]`);
    if (nb) nb.classList.add('active');
  }
}

/* ── Task selection ── */
function selectTask(taskId) {
  S.taskId = taskId;
  document.querySelectorAll('.task-pill').forEach(p => p.classList.remove('selected-task'));
  const pill = $('pill-' + taskId);
  if (pill) pill.classList.add('selected-task');
  $('topbarCrumb').textContent = 'OpenEnv · Task selected — click Start Task';
}

/* ── Loading mask ── */
function showLoading(msg) {
  $('loadingMsg').textContent = msg || 'Executing...';
  $('loadingMask').style.display = 'flex';
}
function hideLoading() { $('loadingMask').style.display = 'none'; }

/* ── Toast ── */
function toast(msg, type = 'info', ms = 2800) {
  const wrap = $('toastWrap');
  const div = document.createElement('div');
  div.className = `toast ${type}`;
  div.textContent = msg;
  wrap.appendChild(div);
  setTimeout(() => div.remove(), ms);
}

/* ══════════════════════════════════════
   API helpers
══════════════════════════════════════ */
async function apiPost(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}
async function apiGet(path) {
  const r = await fetch(path);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

/* ══════════════════════════════════════
   RESET
══════════════════════════════════════ */
async function doReset() {
  showLoading('Initializing incident...');
  try {
    const data = await apiPost('/reset', { task_id: S.taskId });
    S.taskData = data;
    S.episodeDone = false;
    S.usedActions.clear();
    S.lastStep = null;
    S.lastGrade = null;

    // Extract valid/invalid from task JSON via /tasks
    const tasksRes = await apiGet('/tasks');
    const meta = (tasksRes.tasks || []).find(t => t.task_id === S.taskId);

    // Classify actions
    const riskyKeywords = ['reboot', 'reset_password', 'restart_vpn_gateway', 'clear_disk_space', 'renew_ssl_cert_wrong'];
    S.validActions   = (data.available_actions || []).filter(a => !riskyKeywords.some(k => a.includes(k.split('_wrong')[0]) && isRisky(a)));
    S.invalidActions = (data.available_actions || []).filter(a => isRisky(a));

    renderReset(data);
    toast('Task started: ' + (data.title || S.taskId), 'success');
  } catch (e) {
    toast('Reset failed: ' + e.message, 'error');
  } finally {
    hideLoading();
  }
}

function isRisky(action) {
  return /reboot_server|reset_password|restart_vpn_gateway/.test(action);
}

/* ══════════════════════════════════════
   STEP
══════════════════════════════════════ */
async function doStep(action) {
  if (S.episodeDone) { toast('Episode is complete. Click Start Task to reset.', 'info'); return; }
  showLoading(`Executing: ${action}`);
  try {
    const data = await apiPost('/step', { action });
    S.lastStep = data;
    S.usedActions.add(action);

    renderStep(data);

    if (data.done) {
      S.episodeDone = true;
      setBadge(data.success ? 'success' : 'fail');
      toast(data.success ? '✓ Incident resolved! Running grader...' : '✗ Episode ended. Check grader.', data.success ? 'success' : 'error', 4000);
      disableActions();
      // Auto-grade
      await doGrade(true);
    }
  } catch (e) {
    toast('Step failed: ' + e.message, 'error');
  } finally {
    hideLoading();
  }
}

/* ══════════════════════════════════════
   GRADE
══════════════════════════════════════ */
async function doGrade(silent = false) {
  if (!S.taskData) { toast('No active task. Click Start Task first.', 'error'); return; }
  if (!silent) showLoading('Computing score...');
  try {
    const g = await apiGet('/grade');
    S.lastGrade = g;
    renderGrade(g);
    if (!silent) { toast(`Score: ${(g.score * 100).toFixed(1)}% — ${g.passed ? 'PASSED' : 'FAILED'}`, g.passed ? 'success' : 'error', 4000); }
    // Switch to grade panel if auto
    if (silent) {
      setTimeout(() => {
        showPanel('grade', document.querySelector('[data-panel="grade"]'));
      }, 800);
    }
  } catch (e) {
    toast('Grade failed: ' + e.message, 'error');
  } finally {
    if (!silent) hideLoading();
  }
}

/* ══════════════════════════════════════
   RENDERERS
══════════════════════════════════════ */
function renderReset(data) {
  // Show active layout
  $('emptyState').style.display = 'none';
  $('activeLayout').style.display = '';

  // Topbar
  $('topbarTitle').textContent = data.title || 'Incident Triage';
  $('topbarCrumb').textContent = `OpenEnv · ${data.task_id} · ${data.difficulty.toUpperCase()}`;

  // Chips
  $('scSteps').textContent = `0 / ${data.max_steps}`;
  $('scReward').textContent = '+0.0000';
  $('scProg').textContent = '0%';

  // Status
  setBadge('active');
  $('epStatus').textContent = 'ACTIVE';
  $('epStatus').style.color = 'var(--accent-green)';

  // Ticket
  const t = data.ticket || {};
  $('tidBadge').textContent  = t.id || '—';
  $('tSubject').textContent  = t.subject || '—';
  $('tFrom').textContent     = `From: ${t.user || '—'} · ${t.created_at || ''}`;
  $('tBody').textContent     = t.body || '—';

  const pb = $('priBadge');
  const pri = (t.priority || 'medium').toLowerCase();
  pb.textContent = pri.toUpperCase();
  pb.className = 'pri-badge pri-' + pri;

  // Terminal
  $('termOutput').textContent = data.observation || 'Ready.';

  // Reward strip
  $('rsValue').textContent = '+0.0000';
  $('rsValue').style.color = 'var(--text-secondary)';
  $('rsCumul').textContent = '0.0000';
  $('rsBarFill').style.width = '50%';
  $('rsBarFill').style.background = 'var(--accent-blue)';

  // Progress ring
  setRing($('prFg'), 0, 188.5);
  $('prPct').textContent = '0%';
  $('psSteps').textContent = `0/${data.max_steps}`;
  $('psReq').textContent = `0/${data.max_steps}`;
  $('psRew').textContent = '0.00';
  $('psDiff').textContent = data.difficulty || '—';
  $('stepBarFill').style.width = '0%';
  $('stepBarLabel').textContent = `0 / ${data.max_steps} steps`;

  // Actions
  renderActions(data.available_actions || []);

  // Logs
  renderLogs(data.logs || []);

  // Facts
  renderFacts(data.system_facts || {});

  // Mini history
  $('miniHist').innerHTML = '<div class="mh-empty">No steps taken yet.</div>';

  // History panel
  $('histTableWrap').innerHTML = '<div class="hist-ph">No actions taken yet.</div>';
  $('histCountBadge').textContent = '0 actions';

  // Grade panel reset
  $('gradeIdle').style.display = '';
  $('gradeResultInner').style.display = 'none';
  $('gradeComponents').style.display = 'none';
  $('gradeFbPre').textContent = 'Run the grader to see detailed scoring breakdown...';

  // Enable grade btn
  $('gradeBtn').disabled = false;
}

function renderStep(data) {
  // Terminal
  $('termOutput').textContent = data.observation || '';

  // Reward strip
  const rew = data.reward || 0;
  const rstr = (rew >= 0 ? '+' : '') + rew.toFixed(4);
  $('rsValue').textContent = rstr;
  $('rsValue').style.color = rew > 0 ? 'var(--accent-green)' : rew < 0 ? 'var(--accent-red)' : 'var(--text-secondary)';
  $('rsCumul').textContent = (data.cumulative_reward || 0).toFixed(4);

  // Bar fill: 0 = left, negative red, positive green
  const barPct = Math.min(Math.max((data.cumulative_reward + 1) / 2 * 100, 5), 95);
  $('rsBarFill').style.width = barPct + '%';
  $('rsBarFill').style.background = data.cumulative_reward > 0 ? 'var(--accent-green)' : 'var(--accent-red)';

  // Topbar chips
  $('scSteps').textContent = `${data.steps} / ${data.max_steps}`;
  $('scReward').textContent = (data.cumulative_reward >= 0 ? '+' : '') + data.cumulative_reward.toFixed(4);

  // Fetch state for progress
  apiGet('/state').then(state => {
    const pct = state.progress_pct || 0;
    $('scProg').textContent = pct + '%';

    // Progress ring
    setRing($('prFg'), pct / 100, 188.5);
    $('prPct').textContent = pct + '%';
    $('psSteps').textContent = `${state.steps}/${state.max_steps}`;
    $('psReq').textContent = `${state.required_actions_completed}/${state.required_actions_total}`;
    $('psRew').textContent = (state.cumulative_reward || 0).toFixed(2);

    // Step bar
    const stepPct = Math.min((state.steps / Math.max(state.max_steps, 1)) * 100, 100);
    $('stepBarFill').style.width = stepPct + '%';
    $('stepBarLabel').textContent = `${state.steps} / ${state.max_steps} steps`;

    // Mini history
    renderMiniHistory(state.action_history || []);

    // History panel
    renderHistoryTable(state.action_history || []);
    $('histCountBadge').textContent = (state.action_history || []).length + ' actions';
  }).catch(() => {});

  // Mark used action
  markUsed(data.action);
}

function renderActions(actions) {
  const grid = $('actionGrid');
  grid.innerHTML = '';
  if (!actions || actions.length === 0) {
    grid.innerHTML = '<div class="actions-empty">No actions available.</div>';
    return;
  }
  $('actionGrid');
  actions.forEach(action => {
    const btn = document.createElement('button');
    btn.className = 'action-btn ' + (isRisky(action) ? 'risky' : 'helpful');
    btn.textContent = action.replace(/_/g, '_\u200B'); // allow wrap on underscores
    btn.dataset.action = action;
    btn.title = isRisky(action) ? '⚠ Potentially harmful/irrelevant action' : '✓ Diagnostic or remediation action';
    btn.addEventListener('click', () => doStep(action));
    grid.appendChild(btn);
  });
}

function markUsed(action) {
  document.querySelectorAll('.action-btn').forEach(btn => {
    if (S.usedActions.has(btn.dataset.action)) {
      btn.classList.add('used');
    }
  });
}

function disableActions() {
  document.querySelectorAll('.action-btn').forEach(btn => btn.disabled = true);
}

function renderLogs(logs) {
  const term = $('logTerminal');
  $('logCountBadge').textContent = logs.length + ' entries';
  if (!logs.length) { term.innerHTML = '<div class="log-ph">No logs available.</div>'; return; }
  term.innerHTML = logs.map(line => {
    // Colorize log parts
    const colored = line
      .replace(/\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]/g, '<span class="log-ts">[$1]</span>')
      .replace(/([A-Z0-9\-]+):(?=\s)/g, '<span class="log-svc">$1:</span>')
      .replace(/(ERROR|FATAL|FAILED|LOCKED|EXPIRED|CRITICAL)/gi, '<span class="log-error">$1</span>')
      .replace(/(WARNING|WARN|ALERT)/gi, '<span class="log-warn">$1</span>');
    return `<div class="log-line">${colored}</div>`;
  }).join('');
}

function renderFacts(facts) {
  const grid = $('factsGrid');
  const entries = Object.entries(facts);
  if (!entries.length) { grid.innerHTML = '<div class="facts-ph">No system facts available.</div>'; return; }
  grid.innerHTML = entries.map(([k, v]) => {
    let valClass = '';
    let valStr = String(v);
    if (v === true)  { valClass = 'fact-true';  valStr = 'true'; }
    else if (v === false) { valClass = 'fact-false'; valStr = 'false'; }
    else if (typeof v === 'number') {
      valClass = 'fact-num';
      // Highlight dangerous values
      if ((k.includes('usage') || k.includes('pct')) && v > 90) valClass = 'fact-warn';
      if (k.includes('expiry_days') && v < 7) valClass = 'fact-warn';
      if (k.includes('expiry_days') && v < 0) valClass = 'fact-false';
    }
    return `<div class="fact-card">
      <div class="fact-key">${esc(k.replace(/_/g,' '))}</div>
      <div class="fact-val ${valClass}">${esc(valStr)}</div>
    </div>`;
  }).join('');
}

function renderMiniHistory(history) {
  const el = $('miniHist');
  if (!history.length) { el.innerHTML = '<div class="mh-empty">No steps taken yet.</div>'; return; }
  const last5 = [...history].reverse().slice(0, 5);
  el.innerHTML = last5.map(e => {
    const rew = e.reward || 0;
    const rewStr = (rew >= 0 ? '+' : '') + rew.toFixed(4);
    const rewClass = rew > 0 ? 'rew-pos' : rew < 0 ? 'rew-neg' : 'rew-zero';
    return `<div class="mh-entry">
      <span class="mh-step">#${e.step}</span>
      <div>
        <div class="mh-act">${esc(e.action)}</div>
        <div class="mh-prev">${esc((e.observation_preview || '').slice(0,80))}${(e.observation_preview||'').length > 80 ? '…' : ''}</div>
      </div>
      <span class="mh-rew ${rewClass}">${rewStr}</span>
    </div>`;
  }).join('');
}

function renderHistoryTable(history) {
  const wrap = $('histTableWrap');
  if (!history.length) { wrap.innerHTML = '<div class="hist-ph">No actions taken yet.</div>'; return; }
  const rows = [...history].reverse().map(e => {
    const rew = e.reward || 0;
    const rewStr = (rew >= 0 ? '+' : '') + rew.toFixed(4);
    const rewClass = rew > 0 ? 'rew-pos' : rew < 0 ? 'rew-neg' : 'rew-zero';
    return `<tr>
      <td><span class="hist-step-num">#${e.step}</span></td>
      <td><span class="hist-action">${esc(e.action)}</span></td>
      <td><span class="mh-rew ${rewClass}">${rewStr}</span></td>
      <td class="hist-preview">${esc((e.observation_preview || '').slice(0, 100))}${(e.observation_preview||'').length>100?'…':''}</td>
    </tr>`;
  }).join('');
  wrap.innerHTML = `<table class="hist-table">
    <thead><tr>
      <th>#</th><th>Action</th><th>Reward</th><th>Observation Preview</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function renderGrade(g) {
  $('gradeIdle').style.display = 'none';
  $('gradeResultInner').style.display = '';

  const score = g.score || 0;
  const pct = score * 100;

  // Ring
  const circ = 314;
  const offset = circ - (circ * score);
  const fg = $('grrFg');
  fg.style.strokeDashoffset = offset;
  fg.style.stroke = score >= (g.passing_score || 0.7) ? 'var(--accent-green)' : 'var(--accent-red)';

  // Score text
  $('gradeScoreText').textContent = pct.toFixed(1) + '%';

  // Pass tag
  const tag = $('gradePassTag');
  tag.textContent = g.passed ? '✓ PASSED' : '✗ FAILED';
  tag.className = 'grade-pass-tag ' + (g.passed ? 'passed' : 'failed');

  // Meta
  $('gradeMeta').innerHTML = `
    <div class="grade-meta-row"><span class="gm-label">Task</span><span class="gm-val">${esc(g.task_id)}</span></div>
    <div class="grade-meta-row"><span class="gm-label">Difficulty</span><span class="gm-val">${esc(g.difficulty)}</span></div>
    <div class="grade-meta-row"><span class="gm-label">Pass threshold</span><span class="gm-val">${((g.passing_score||0)*100).toFixed(0)}%</span></div>
    <div class="grade-meta-row"><span class="gm-label">Steps</span><span class="gm-val">${g.steps_taken} / ${g.max_steps}</span></div>
    <div class="grade-meta-row"><span class="gm-label">Required done</span><span class="gm-val">${g.required_actions_completed} / ${g.required_actions_total}</span></div>
    <div class="grade-meta-row"><span class="gm-label">Cumulative reward</span><span class="gm-val">${(g.cumulative_reward||0).toFixed(4)}</span></div>
  `;

  // Feedback
  $('gradeFbPre').textContent = g.feedback || '—';

  // Components (parse from feedback)
  renderComponents(g);
  $('gradeComponents').style.display = '';
}

function renderComponents(g) {
  const feedback = g.feedback || '';
  const lines = feedback.split('\n');
  const comps = [];

  lines.forEach(line => {
    const m1 = line.match(/Coverage score:\s*([\d.]+)\/([\d.]+)/);
    if (m1) comps.push({ name: 'Coverage (required actions)', val: parseFloat(m1[1]), max: parseFloat(m1[2]) });
    const m2 = line.match(/Reward score:\s*([\d.]+)\/([\d.]+)/);
    if (m2) comps.push({ name: 'Reward signal', val: parseFloat(m2[1]), max: parseFloat(m2[2]) });
    const m3 = line.match(/Efficiency score:\s*([\d.]+)\/([\d.]+)/);
    if (m3) comps.push({ name: 'Efficiency bonus', val: parseFloat(m3[1]), max: parseFloat(m3[2]) });
    const m4 = line.match(/Completion bonus:\s*([\d.]+)\/([\d.]+)/);
    if (m4) comps.push({ name: 'Completion bonus', val: parseFloat(m4[1]), max: parseFloat(m4[2]) });
  });

  if (!comps.length) { $('gradeComponents').style.display = 'none'; return; }

  $('compList').innerHTML = comps.map(c => {
    const pct = c.max > 0 ? Math.min((c.val / c.max) * 100, 100) : 0;
    return `<div class="comp-row">
      <div class="comp-top">
        <span class="comp-name">${esc(c.name)}</span>
        <span class="comp-val">${c.val.toFixed(3)} / ${c.max.toFixed(3)}</span>
      </div>
      <div class="comp-bar-track">
        <div class="comp-bar-fill" style="width:${pct}%"></div>
      </div>
    </div>`;
  }).join('');
}

/* ── Helpers ── */
function setRing(el, fraction, circumference) {
  const offset = circumference - (circumference * Math.min(Math.max(fraction, 0), 1));
  el.style.strokeDashoffset = offset;
}

function setBadge(type) {
  const b = $('statusBadge');
  b.className = 'status-badge';
  if (type === 'active')  { b.classList.add('active-badge'); b.textContent = 'ACTIVE'; }
  if (type === 'success') { b.classList.add('done-badge');   b.textContent = 'RESOLVED'; }
  if (type === 'fail')    { b.classList.add('fail-badge');   b.textContent = 'FAILED'; }
  if (type === 'idle')    { b.textContent = 'IDLE'; }
}

/* ══════════════════════════════════════
   INIT
══════════════════════════════════════ */
(function init() {
  // Select default task
  selectTask('easy_vpn_lock');

  // Grade button default state
  $('gradeBtn').disabled = false;

  // Keyboard shortcut: Enter on focused action btn
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') hideLoading();
  });

  // Check server health on load
  fetch('/').then(r => r.json()).then(data => {
    if (data.status === 'ok') {
      toast(`IncidentEnv ready · ${data.tasks_available} tasks available`, 'success', 3000);
    }
  }).catch(() => {
    toast('Could not connect to environment server', 'error');
  });
})();
