// JobPilot Dashboard — vanilla JS frontend

const API = '';

// --- Navigation ---
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const page = link.dataset.page;
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        document.getElementById(`page-${page}`).classList.add('active');
        link.classList.add('active');
        loadPage(page);
    });
});

// --- Toast ---
function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 3000);
}

// --- API Helpers ---
async function api(method, path, body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API}${path}`, opts);
    return res.json();
}

// --- Dashboard ---
async function loadDashboard() {
    const stats = await api('GET', '/api/stats');
    document.getElementById('stats-grid').innerHTML = `
        <div class="stat-card"><div class="label">Total Jobs</div><div class="value blue">${stats.total_jobs}</div></div>
        <div class="stat-card"><div class="label">Companies</div><div class="value">${stats.total_companies}</div></div>
        <div class="stat-card"><div class="label">Applications</div><div class="value yellow">${stats.total_applications}</div></div>
        <div class="stat-card"><div class="label">Avg Match</div><div class="value green">${(stats.average_match_score * 100).toFixed(0)}%</div></div>
    `;

    const { jobs } = await api('GET', '/api/jobs?min_score=0.5');
    const top = jobs.slice(0, 5);
    if (top.length === 0) {
        document.getElementById('top-matches').innerHTML = '<div class="empty-state">No matches yet. Run a scan first.</div>';
        return;
    }
    document.getElementById('top-matches').innerHTML = top.map(renderJobCard).join('');
}

// --- Jobs ---
async function loadJobs() {
    const q = document.getElementById('job-search').value;
    const source = document.getElementById('job-source').value;
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (source) params.set('source', source);
    const { jobs } = await api('GET', `/api/jobs?${params}`);
    if (jobs.length === 0) {
        document.getElementById('jobs-list').innerHTML = '<div class="empty-state">No jobs found. Try a different search.</div>';
        return;
    }
    document.getElementById('jobs-list').innerHTML = jobs.map(renderJobCard).join('');
}

// --- Applications ---
async function loadApplications() {
    const { applications } = await api('GET', '/api/applications');
    if (applications.length === 0) {
        document.getElementById('applications-list').innerHTML = '<div class="empty-state">No applications tracked yet.</div>';
        return;
    }
    document.getElementById('applications-list').innerHTML = applications.map(app => `
        <div class="app-card">
            <div class="app-info">
                <strong>${app.company}</strong> — ${app.role}
                <div style="font-size:0.85rem;color:var(--text-dim)">Score: ${(app.match_score * 100).toFixed(0)}% · Updated: ${app.updated_date?.slice(0,10) || '-'}</div>
            </div>
            <span class="app-status status-${app.status}">${app.status}</span>
        </div>
    `).join('');
}

// --- Profile ---
async function loadProfile() {
    const profile = await api('GET', '/api/profile');
    const form = document.getElementById('profile-form');
    for (const [key, value] of Object.entries(profile)) {
        const el = form.elements[key];
        if (!el) continue;
        if (Array.isArray(value)) {
            el.value = value.join(', ');
        } else {
            el.value = value ?? '';
        }
    }
}

document.getElementById('profile-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const data = {};
    for (const [key, val] of fd.entries()) {
        if (['skills', 'programming_languages', 'frameworks', 'cloud_platforms', 'preferred_roles', 'preferred_locations'].includes(key)) {
            data[key] = val.split(',').map(s => s.trim()).filter(Boolean);
        } else if (key === 'experience_years') {
            data[key] = parseInt(val) || 0;
        } else {
            data[key] = val;
        }
    }
    await api('PUT', '/api/profile', data);
    showToast('Profile saved!');
});

// --- Actions ---
async function triggerScan() {
    showToast('Scanning jobs...');
    try {
        const result = await api('POST', '/api/scan', { source: 'all', role: '', location: '' });
        showToast(`Found ${result.jobs_found} jobs from ${result.sources.join(', ')}!`);
        loadDashboard();
    } catch (err) {
        showToast('Scan failed — check server logs.');
    }
}

async function runMatch() {
    showToast('Matching...');
    try {
        const result = await api('POST', '/api/match/run', { min_score: 0.5, limit: 20 });
        showToast(`Matched ${result.total} jobs!`);
        loadDashboard();
    } catch (err) {
        showToast('Matching failed — run a scan first.');
    }
}

// --- Resume Analyzer ---
document.getElementById('resume-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = document.getElementById('resume-text').value.trim();
    if (!text) { showToast('Please paste your resume text.'); return; }

    const targetRole = document.getElementById('resume-target-role').value.trim();
    showToast('Analyzing resume...');

    try {
        const result = await api('POST', '/api/resume/analyze', { text, target_role: targetRole });
        displayResumeResults(result);
        loadResumeHistory();
        showToast('Analysis complete!');
    } catch (err) {
        showToast('Error analyzing resume.');
    }
});

function displayResumeResults(result) {
    const container = document.getElementById('resume-results');
    container.style.display = 'block';

    // Scores
    const scores = result.scores;
    document.getElementById('resume-scores').innerHTML = `
        <div class="stats-grid">
            <div class="stat-card"><div class="label">ATS Score</div><div class="value ${scoreColor(scores.ats_score)}">${(scores.ats_score * 100).toFixed(0)}%</div></div>
            <div class="stat-card"><div class="label">Quality</div><div class="value ${scoreColor(scores.resume_quality_score)}">${(scores.resume_quality_score * 100).toFixed(0)}%</div></div>
            <div class="stat-card"><div class="label">Technical</div><div class="value ${scoreColor(scores.technical_strength_score)}">${(scores.technical_strength_score * 100).toFixed(0)}%</div></div>
            <div class="stat-card"><div class="label">Hiring Ready</div><div class="value ${scoreColor(scores.hiring_readiness_score)}">${(scores.hiring_readiness_score * 100).toFixed(0)}%</div></div>
        </div>
    `;

    // Skills
    document.getElementById('resume-skills').innerHTML = result.skills.length > 0
        ? `<h3>Skills Detected (${result.skills.length})</h3><div class="job-skills">${result.skills.map(s => `<span class="skill-tag">${s}</span>`).join('')}</div>`
        : '';

    // Strengths
    document.getElementById('resume-strengths').innerHTML = result.strengths.length > 0
        ? `<h3 style="color:var(--green)">Strengths</h3><ul>${result.strengths.map(s => `<li>✓ ${s}</li>`).join('')}</ul>`
        : '';

    // Weaknesses
    document.getElementById('resume-weaknesses').innerHTML = result.weaknesses.length > 0
        ? `<h3 style="color:var(--red)">Weaknesses</h3><ul>${result.weaknesses.map(w => `<li>✗ ${w}</li>`).join('')}</ul>`
        : '';

    // Suggestions
    document.getElementById('resume-suggestions').innerHTML = result.suggestions.length > 0
        ? `<h3 style="color:var(--blue)">Improvement Suggestions</h3><ol>${result.suggestions.map(s => `<li>${s}</li>`).join('')}</ol>`
        : '';

    // Missing skills
    document.getElementById('resume-missing').innerHTML = result.missing_skills.length > 0
        ? `<h3 style="color:var(--yellow)">Missing Skills for ${result.target_role || 'Target Role'}</h3><div class="job-skills">${result.missing_skills.map(s => `<span class="missing-tag">${s}</span>`).join('')}</div>`
        : '';
}

function scoreColor(score) {
    if (score >= 0.8) return 'green';
    if (score >= 0.6) return 'yellow';
    return 'red';
}

async function loadResumeHistory() {
    const { resumes } = await api('GET', '/api/resume/history');
    if (resumes.length === 0) {
        document.getElementById('resume-history').innerHTML = '<div class="empty-state">No resumes analyzed yet.</div>';
        return;
    }
    document.getElementById('resume-history').innerHTML = resumes.map(r => `
        <div class="app-card">
            <div class="app-info">
                <strong>${r.name || 'Untitled'}</strong> — ${r.filename}
                <div style="font-size:0.85rem;color:var(--text-dim)">
                    ${r.target_role ? 'Target: ' + r.target_role + ' · ' : ''}${r.created_at?.slice(0,10) || '-'}
                </div>
            </div>
        </div>
    `).join('');
}

// --- Rendering ---
function renderJobCard(job) {
    const score = job.match_score ?? 0;
    const scorePct = (score * 100).toFixed(0);
    const scoreClass = score >= 0.8 ? 'high' : score >= 0.5 ? 'mid' : 'low';
    const skills = (job.required_skills || job.tech_stack || []).slice(0, 6);
    const missing = (job.missing_skills || []).slice(0, 4);

    return `
        <div class="job-card" onclick="window.open('${job.url || '#'}', '_blank')">
            <div class="job-header">
                <div>
                    <div class="job-title">${job.title}</div>
                    <div class="job-company">${job.company}</div>
                    <div class="job-meta">${job.location || 'Unknown'} · ${job.source} · ${job.remote_status || ''}</div>
                </div>
                <div class="job-score ${scoreClass}">${scorePct}%</div>
            </div>
            <div class="job-skills">
                ${skills.map(s => `<span class="skill-tag">${s}</span>`).join('')}
                ${missing.map(s => `<span class="missing-tag">-${s}</span>`).join('')}
            </div>
        </div>
    `;
}

// --- Init ---
function loadPage(page) {
    if (page === 'dashboard') loadDashboard();
    else if (page === 'jobs') loadJobs();
    else if (page === 'applications') loadApplications();
    else if (page === 'profile') loadProfile();
    else if (page === 'resume') loadResumeHistory();
}

loadDashboard();
