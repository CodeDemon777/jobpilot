// JobPilot Dashboard — vanilla JS frontend

const API = '';

// --- Authentication State ---
let authToken = localStorage.getItem('authToken');
let refreshToken = localStorage.getItem('refreshToken');
let currentUser = null;

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
    if (authToken) {
        opts.headers['Authorization'] = `Bearer ${authToken}`;
    }
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API}${path}`, opts);
    if (res.status === 401 && refreshToken) {
        // Try to refresh token
        const refreshed = await refreshAccessToken();
        if (refreshed) {
            opts.headers['Authorization'] = `Bearer ${authToken}`;
            const retryRes = await fetch(`${API}${path}`, opts);
            return retryRes.json();
        }
    }
    return res.json();
}

// --- Authentication Functions ---
async function refreshAccessToken() {
    try {
        const res = await fetch(`${API}/api/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        if (res.ok) {
            const data = await res.json();
            authToken = data.access_token;
            localStorage.setItem('authToken', authToken);
            return true;
        }
    } catch (err) {
        console.error('Token refresh failed:', err);
    }
    logout();
    return false;
}

function updateAuthUI() {
    const navAuth = document.getElementById('nav-auth');
    const navUser = document.getElementById('nav-user');
    const userName = document.getElementById('user-name');

    if (authToken && currentUser) {
        navAuth.classList.add('hidden');
        navUser.classList.remove('hidden');
        userName.textContent = currentUser.name || currentUser.email;
    } else {
        navAuth.classList.remove('hidden');
        navUser.classList.add('hidden');
    }
}

async function checkAuth() {
    if (authToken) {
        try {
            const res = await api('GET', '/api/auth/me');
            if (res.id) {
                currentUser = res;
                updateAuthUI();
                return true;
            }
        } catch (err) {
            console.error('Auth check failed:', err);
        }
        logout();
    }
    return false;
}

function showLoginModal() {
    document.getElementById('login-modal').classList.remove('hidden');
}

function closeLoginModal() {
    document.getElementById('login-modal').classList.add('hidden');
}

function showRegisterModal() {
    document.getElementById('register-modal').classList.remove('hidden');
}

function closeRegisterModal() {
    document.getElementById('register-modal').classList.add('hidden');
}

async function logout() {
    authToken = null;
    refreshToken = null;
    currentUser = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('refreshToken');
    updateAuthUI();
    showToast('Logged out successfully');
}

// Login form handler
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    try {
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        const res = await fetch(`${API}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData.toString()
        });

        const data = await res.json();

        if (res.ok && data.access_token) {
            authToken = data.access_token;
            refreshToken = data.refresh_token;
            localStorage.setItem('authToken', authToken);
            localStorage.setItem('refreshToken', refreshToken);
            closeLoginModal();
            await checkAuth();
            showToast('Logged in successfully!');
        } else {
            showToast(data.detail || 'Login failed');
        }
    } catch (err) {
        showToast('Login failed');
    }
});

// Register form handler
document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('register-name').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;

    try {
        const res = await api('POST', '/api/auth/register', { email, password, name });
        if (res.id) {
            closeRegisterModal();
            showLoginModal();
            showToast('Account created! Please login.');
        } else {
            showToast(res.detail || 'Registration failed');
        }
    } catch (err) {
        showToast('Registration failed');
    }
});

// --- Dashboard ---
async function loadDashboard() {
    // Load basic stats
    const stats = await api('GET', '/api/stats');
    document.getElementById('stats-grid').innerHTML = `
        <div class="stat-card"><div class="label">Total Jobs</div><div class="value blue">${stats.total_jobs}</div></div>
        <div class="stat-card"><div class="label">Companies</div><div class="value">${stats.total_companies}</div></div>
        <div class="stat-card"><div class="label">Applications</div><div class="value yellow">${stats.total_applications}</div></div>
        <div class="stat-card"><div class="label">Avg Match</div><div class="value green">${(stats.average_match_score * 100).toFixed(0)}%</div></div>
    `;

    // Load enhanced dashboard data
    loadEnhancedDashboard();
    loadNotifications();
    loadTrendingSkills();
    loadTopCompanies();
    loadJobsBySource();
    loadRecommendations();

    // Load top matches
    const { jobs } = await api('GET', '/api/jobs?min_score=0.5');
    const top = jobs.slice(0, 5);
    if (top.length === 0) {
        document.getElementById('top-matches').innerHTML = '<div class="empty-state">No matches yet. Run a scan first.</div>';
    } else {
        document.getElementById('top-matches').innerHTML = top.map(renderJobCard).join('');
    }
}

async function loadEnhancedDashboard() {
    try {
        const data = await api('GET', '/api/dashboard/enhanced');

        // Update stats grid with new metrics
        const grid = document.getElementById('stats-grid');
        grid.innerHTML += `
            <div class="stat-card"><div class="label">New Today</div><div class="value green">${data.jobs_discovered_today}</div></div>
            <div class="stat-card"><div class="label">New This Week</div><div class="value blue">${data.jobs_discovered_this_week}</div></div>
            <div class="stat-card"><div class="label">Unread Alerts</div><div class="value yellow">${data.unread_notifications}</div></div>
        `;

        // Load new jobs today
        if (data.jobs_today && data.jobs_today.length > 0) {
            document.getElementById('new-jobs-today').innerHTML = data.jobs_today.slice(0, 5).map(job => `
                <div class="job-card">
                    <div class="job-header">
                        <div>
                            <div class="job-title">${job.title}</div>
                            <div class="job-company">${job.company}</div>
                            <div class="job-meta">${job.location || 'Unknown'} · ${job.source}</div>
                        </div>
                        <span class="badge badge-new">NEW</span>
                    </div>
                </div>
            `).join('');
        } else {
            document.getElementById('new-jobs-today').innerHTML = '<div class="empty-state">No new jobs discovered today.</div>';
        }

        // Load recent high match jobs
        if (data.recent_high_match && data.recent_high_match.length > 0) {
            document.getElementById('top-matches').innerHTML = data.recent_high_match.slice(0, 5).map(job => `
                <div class="job-card">
                    <div class="job-header">
                        <div>
                            <div class="job-title">${job.title}</div>
                            <div class="job-company">${job.company}</div>
                            <div class="job-meta">${job.location || 'Unknown'} · ${job.source}</div>
                        </div>
                        <div class="job-score high">${(job.match_score * 100).toFixed(0)}%</div>
                    </div>
                    <div class="job-skills">
                        ${(job.strengths || []).slice(0, 3).map(s => `<span class="skill-tag">${s}</span>`).join('')}
                    </div>
                </div>
            `).join('');
        }
    } catch (err) {
        console.log('Enhanced dashboard not available:', err);
    }
}

async function loadNotifications() {
    try {
        const { notifications, total } = await api('GET', '/api/notifications?limit=10');
        const badge = document.getElementById('unread-badge');
        const { unread_count } = await api('GET', '/api/notifications/unread-count');

        if (unread_count > 0) {
            badge.textContent = unread_count;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }

        if (notifications.length === 0) {
            document.getElementById('notifications-list').innerHTML = '<div class="empty-state">No notifications yet.</div>';
            return;
        }

        document.getElementById('notifications-list').innerHTML = notifications.map(n => `
            <div class="notification-card ${n.is_read ? '' : 'unread'}">
                <div class="notification-content">
                    <div class="notification-title">${n.company || 'Unknown'} — ${n.title || 'New Match'}</div>
                    <div class="notification-message">${n.message || ''}</div>
                    <div class="notification-meta">
                        <span class="badge badge-score">${(n.match_score * 100).toFixed(0)}% match</span>
                        <span class="notification-time">${n.created_at?.slice(0, 16) || ''}</span>
                    </div>
                </div>
                ${!n.is_read ? `<button class="btn btn-sm" onclick="markNotificationRead(${n.id})">Mark Read</button>` : ''}
            </div>
        `).join('');
    } catch (err) {
        console.log('Notifications not available:', err);
    }
}

async function markNotificationRead(id) {
    await api('POST', `/api/notifications/${id}/read`);
    loadNotifications();
}

async function loadTrendingSkills() {
    try {
        const { skills } = await api('GET', '/api/trending/skills?limit=10');
        if (skills.length === 0) {
            document.getElementById('trending-skills').innerHTML = '<div class="empty-state">No skill data yet. Run a scan first.</div>';
            return;
        }
        document.getElementById('trending-skills').innerHTML = `
            <div class="skills-grid">
                ${skills.map(s => `
                    <div class="skill-item">
                        <span class="skill-name">${s.skill}</span>
                        <span class="skill-count">${s.count} jobs</span>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (err) {
        console.log('Trending skills not available:', err);
    }
}

async function loadTopCompanies() {
    try {
        const { companies } = await api('GET', '/api/trending/companies?limit=5');
        if (companies.length === 0) {
            document.getElementById('top-companies').innerHTML = '<div class="empty-state">No company data yet.</div>';
            return;
        }
        document.getElementById('top-companies').innerHTML = `
            <div class="companies-grid">
                ${companies.map(c => `
                    <div class="company-item">
                        <span class="company-name">${c.company}</span>
                        <span class="company-count">${c.job_count} jobs</span>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (err) {
        console.log('Top companies not available:', err);
    }
}

async function loadJobsBySource() {
    try {
        const { sources } = await api('GET', '/api/trending/sources');
        if (sources.length === 0) {
            document.getElementById('jobs-by-source').innerHTML = '<div class="empty-state">No source data yet.</div>';
            return;
        }
        document.getElementById('jobs-by-source').innerHTML = `
            <div class="sources-grid">
                ${sources.map(s => `
                    <div class="source-item">
                        <span class="source-name">${s.source || 'Unknown'}</span>
                        <span class="source-count">${s.job_count} jobs</span>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (err) {
        console.log('Jobs by source not available:', err);
    }
}

async function loadRecommendations() {
    try {
        const data = await api('GET', '/api/recommendations');
        let html = '';

        // Recommended Jobs
        if (data.recommended_jobs && data.recommended_jobs.length > 0) {
            html += `<h3>Recommended Jobs</h3>`;
            html += data.recommended_jobs.slice(0, 3).map(r => `
                <div class="job-card">
                    <div class="job-header">
                        <div>
                            <div class="job-title">${r.job.title}</div>
                            <div class="job-company">${r.job.company}</div>
                        </div>
                        <div class="job-score high">${(r.match_score * 100).toFixed(0)}%</div>
                    </div>
                </div>
            `).join('');
        }

        // Recommended Skills
        if (data.recommended_skills && data.recommended_skills.length > 0) {
            html += `<h3>Skills to Learn</h3>`;
            html += `<div class="job-skills">${data.recommended_skills.slice(0, 5).map(s => `
                <span class="skill-tag skill-recommend">${s.skill} <small>(${s.demand_count} jobs)</small></span>
            `).join('')}</div>`;
        }

        // Recommended Certifications
        if (data.recommended_certifications && data.recommended_certifications.length > 0) {
            html += `<h3>Recommended Certifications</h3>`;
            html += data.recommended_certifications.slice(0, 3).map(c => `
                <div class="cert-item">
                    <span class="cert-name">${c.certification}</span>
                    <span class="cert-provider">${c.provider}</span>
                    <span class="cert-skill">for ${c.related_skill}</span>
                </div>
            `).join('');
        }

        if (html) {
            document.getElementById('recommendations').innerHTML = html;
        } else {
            document.getElementById('recommendations').innerHTML = '<div class="empty-state">Complete your profile to get personalized recommendations.</div>';
        }
    } catch (err) {
        console.log('Recommendations not available:', err);
    }
}

// --- Jobs ---
async function loadJobs() {
    const q = document.getElementById('job-search').value;
    const source = document.getElementById('job-source').value;
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (source) params.set('source', source);
    console.log('Loading jobs with params:', params.toString());
    const { jobs } = await api('GET', `/api/jobs?${params}`);
    console.log('Jobs loaded:', jobs.length);
    if (jobs.length === 0) {
        document.getElementById('jobs-list').innerHTML = '<div class="empty-state">No jobs found. Try a different search.</div>';
        return;
    }
    document.getElementById('jobs-list').innerHTML = jobs.map(renderJobCard).join('');
}

async function refreshJobs() {
    showToast('Refreshing jobs...');
    await loadJobs();
    showToast('Jobs refreshed!');
}

// --- Career Page ---
function switchCareerTab(tab) {
    document.querySelectorAll('#page-career .sub-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('#page-career .tab-content').forEach(t => { t.style.display = 'none'; t.classList.remove('active'); });
    document.querySelector(`#page-career .sub-tab[data-tab="${tab}"]`).classList.add('active');
    const content = document.getElementById(`tab-${tab}`);
    content.style.display = 'block';
    content.classList.add('active');

    // Load data for the tab
    if (tab === 'coach') loadCoachHistory();
    if (tab === 'versions') loadResumeVersions();
}

function loadCareerPage() {
    // Load initial tab data
    loadCoachHistory();
    loadResumeVersions();
}

// Career Roadmap
document.getElementById('roadmap-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const role = document.getElementById('roadmap-role').value.trim();
    const company = document.getElementById('roadmap-company').value.trim();

    showToast('Generating career roadmap...');
    try {
        const result = await api('POST', '/api/roadmap/generate', { goal_role: role, goal_company: company });
        displayRoadmap(result);
        showToast('Roadmap generated!');
    } catch (err) {
        showToast('Error generating roadmap.');
    }
});

function displayRoadmap(result) {
    const container = document.getElementById('roadmap-results');
    container.style.display = 'block';

    let html = `<div class="stats-grid">
        <div class="stat-card"><div class="label">Goal</div><div class="value blue">${result.goal_role}</div></div>
        <div class="stat-card"><div class="label">Duration</div><div class="value yellow">${result.estimated_duration_weeks} weeks</div></div>
        <div class="stat-card"><div class="label">Missing Skills</div><div class="value red">${result.missing_skills.length}</div></div>
        <div class="stat-card"><div class="label">Match Score</div><div class="value green">${(result.match_analysis.overall_score * 100).toFixed(0)}%</div></div>
    </div>`;

    if (result.missing_skills.length > 0) {
        html += `<h3>Skills to Learn</h3><div class="job-skills">${result.missing_skills.map(s => `<span class="missing-tag">${s}</span>`).join('')}</div>`;
    }

    if (result.roadmap_data && result.roadmap_data.length > 0) {
        html += `<h3>Roadmap</h3>`;
        result.roadmap_data.forEach(phase => {
            html += `<div class="improvement-card">
                <div class="header">
                    <span class="title">${phase.phase}</span>
                    <span class="priority priority-medium">Week ${phase.week_start}-${phase.week_end}</span>
                </div>
                <div class="description">
                    <strong>Skills:</strong> ${phase.skills.join(', ') || 'N/A'}<br>
                    <strong>Tasks:</strong> ${phase.tasks.join(', ')}<br>
                    <strong>Milestone:</strong> ${phase.milestone}
                </div>
            </div>`;
        });
    }

    if (result.recommended_resources && result.recommended_resources.length > 0) {
        html += `<h3>Recommended Resources</h3>`;
        result.recommended_resources.forEach(r => {
            html += `<div class="cert-item">
                <span class="cert-name">${r.skill}</span>
                <span class="cert-provider">${r.platform}</span>
                <span class="cert-skill">${r.course}</span>
            </div>`;
        });
    }

    document.getElementById('roadmap-output').innerHTML = html;
}

// AI Career Coach
document.getElementById('coach-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const question = document.getElementById('coach-question').value.trim();
    if (!question) { showToast('Please enter a question.'); return; }

    showToast('Asking career coach...');
    try {
        const result = await api('POST', '/api/coach/ask', { question });
        displayCoachResponse(result);
        loadCoachHistory();
        showToast('Coach responded!');
    } catch (err) {
        showToast('Error getting response.');
    }
});

function displayCoachResponse(result) {
    const container = document.getElementById('coach-results');
    container.style.display = 'block';
    document.getElementById('coach-output').innerHTML = `
        <div class="cover-letter-output">${result.answer}</div>
        ${result.suggestions && result.suggestions.length > 0 ? `
            <h3 style="margin-top: 1rem;">Suggested Actions</h3>
            <div class="job-skills">${result.suggestions.map(s => `<span class="skill-tag">${s}</span>`).join('')}</div>
        ` : ''}
    `;
}

async function loadCoachHistory() {
    const { conversations } = await api('GET', '/api/coach/history?limit=5');
    const container = document.getElementById('coach-history');
    if (!conversations || conversations.length === 0) {
        container.innerHTML = '<div class="empty-state">No conversations yet.</div>';
        return;
    }
    container.innerHTML = conversations.map(c => `
        <div class="app-card">
            <div class="app-info">
                <strong>Q:</strong> ${c.question}
                <div style="font-size:0.85rem;color:var(--text-dim)">${c.created_at?.slice(0,10) || '-'}</div>
            </div>
        </div>
    `).join('');
}

// Resume Versions
document.getElementById('version-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('version-name').value.trim();
    const text = document.getElementById('version-text').value.trim();
    const notes = document.getElementById('version-notes').value.trim();

    showToast('Creating resume version...');
    try {
        const result = await api('POST', '/api/resume/versions/create', { name, raw_text: text, notes });
        showToast(`Version created! ATS Score: ${(result.ats_score * 100).toFixed(0)}%`);
        loadResumeVersions();
        e.target.reset();
    } catch (err) {
        showToast('Error creating version.');
    }
});

async function loadResumeVersions() {
    const { versions } = await api('GET', '/api/resume/versions');
    const container = document.getElementById('versions-list');
    if (!versions || versions.length === 0) {
        container.innerHTML = '<div class="empty-state">No resume versions yet.</div>';
        return;
    }
    container.innerHTML = versions.map(v => `
        <div class="app-card">
            <div class="app-info">
                <strong>${v.name}</strong> (v${v.version_number})
                <div style="font-size:0.85rem;color:var(--text-dim)">
                    ATS: ${(v.ats_score * 100).toFixed(0)}% · Skills: ${JSON.parse(v.skills || '[]').length} · ${v.created_at?.slice(0,10) || '-'}
                </div>
            </div>
        </div>
    `).join('');
}

// Interview Prep
document.getElementById('interview-search-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const company = document.getElementById('interview-company').value.trim();
    showToast('Searching interview info...');
    try {
        const result = await api('GET', `/api/interviews/company/${encodeURIComponent(company)}`);
        displayInterviewInfo(result);
        showToast('Found interview info!');
    } catch (err) {
        showToast('Error fetching interview info.');
    }
});

function displayInterviewInfo(result) {
    const container = document.getElementById('interview-results');
    container.style.display = 'block';

    let html = `<h3>${result.company}</h3>`;

    if (result.difficulty) {
        html += `<p><strong>Difficulty:</strong> ${'⭐'.repeat(result.difficulty)} (${result.difficulty}/5)</p>`;
    }

    if (result.typical_rounds && result.typical_rounds.length > 0) {
        html += `<h4>Typical Interview Process</h4>`;
        result.typical_rounds.forEach(round => {
            html += `<div class="improvement-card">
                <div class="header">
                    <span class="title">Round ${round.round}: ${round.type}</span>
                    <span class="priority priority-medium">${round.duration}</span>
                </div>
                <div class="description">${round.topics.join(' · ')}</div>
            </div>`;
        });
    }

    if (result.common_questions && result.common_questions.length > 0) {
        html += `<h4>Common Questions</h4><ul>${result.common_questions.map(q => `<li>${q}</li>`).join('')}</ul>`;
    }

    if (result.tips && result.tips.length > 0) {
        html += `<h4>Tips</h4><ul>${result.tips.map(t => `<li>${t}</li>`).join('')}</ul>`;
    }

    if (result.salary_range) {
        html += `<p><strong>Salary Range:</strong> ${result.salary_range}</p>`;
    }

    document.getElementById('interview-output').innerHTML = html;
}

document.getElementById('interview-submit-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
        company: document.getElementById('submit-company').value.trim(),
        role: document.getElementById('submit-role').value.trim(),
        difficulty: parseInt(document.getElementById('submit-difficulty').value),
        experience_text: document.getElementById('submit-experience').value.trim(),
        tips: document.getElementById('submit-tips').value.trim(),
        rounds: [],
        questions: [],
        salary_range: '',
    };
    showToast('Submitting experience...');
    try {
        await api('POST', '/api/interviews/submit', data);
        showToast('Experience submitted!');
        e.target.reset();
    } catch (err) {
        showToast('Error submitting experience.');
    }
});

// Salary Estimator
document.getElementById('salary-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
        role: document.getElementById('salary-role').value.trim(),
        company: document.getElementById('salary-company').value.trim(),
        location: document.getElementById('salary-location').value.trim(),
        experience_level: document.getElementById('salary-experience').value,
        skills: document.getElementById('salary-skills').value.split(',').map(s => s.trim()).filter(Boolean),
    };
    showToast('Estimating salary...');
    try {
        const result = await api('POST', '/api/salary/estimate', data);
        displaySalaryEstimate(result);
        showToast('Estimate ready!');
    } catch (err) {
        showToast('Error estimating salary.');
    }
});

function displaySalaryEstimate(result) {
    const container = document.getElementById('salary-results');
    container.style.display = 'block';

    document.getElementById('salary-output').innerHTML = `
        <div class="stats-grid">
            <div class="stat-card"><div class="label">Minimum</div><div class="value green">$${result.estimated_min.toLocaleString()}</div></div>
            <div class="stat-card"><div class="label">Maximum</div><div class="value blue">$${result.estimated_max.toLocaleString()}</div></div>
            <div class="stat-card"><div class="label">Average</div><div class="value yellow">$${((result.estimated_min + result.estimated_max) / 2).toLocaleString()}</div></div>
            <div class="stat-card"><div class="label">Confidence</div><div class="value">${(result.confidence_score * 100).toFixed(0)}%</div></div>
        </div>
        ${result.factors && result.factors.length > 0 ? `
            <h3>Factors Affecting Salary</h3>
            <ul>${result.factors.map(f => `<li>${f}</li>`).join('')}</ul>
        ` : ''}
        ${result.tips && result.tips.length > 0 ? `
            <h3>Tips to Increase Salary</h3>
            <ul>${result.tips.map(t => `<li>${t}</li>`).join('')}</ul>
        ` : ''}
    `;
}

async function importJobFromUrl() {
    const url = document.getElementById('job-import-url').value.trim();
    if (!url) {
        showToast('Please enter a job URL');
        return;
    }

    showToast('Importing job...');
    try {
        const result = await api('POST', '/api/jobs/import', { url });
        if (result.job) {
            document.getElementById('import-result').innerHTML = `
                <div class="job-card">
                    <div class="job-header">
                        <div>
                            <div class="job-title">${result.job.title}</div>
                            <div class="job-company">${result.job.company}</div>
                            <div class="job-meta">${result.job.location || 'Unknown'} · ${result.job.source}</div>
                        </div>
                        <div class="job-score high">${(result.match_score * 100).toFixed(0)}%</div>
                    </div>
                    <div class="job-skills">
                        ${(result.job.required_skills || []).slice(0, 6).map(s => `<span class="skill-tag">${s}</span>`).join('')}
                    </div>
                    <p style="margin-top: 0.5rem; color: var(--text-dim); font-size: 0.85rem;">
                        ${result.match_result.missing_skills.length > 0 ? 'Missing: ' + result.match_result.missing_skills.slice(0, 3).join(', ') : 'Great match!'}
                    </p>
                </div>
            `;
            showToast('Job imported successfully!');
            document.getElementById('job-import-url').value = '';
            loadJobs(); // Refresh job list
        } else {
            showToast(result.detail || 'Failed to import job');
        }
    } catch (err) {
        showToast('Error importing job');
    }
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
    const data = buildProfileDataFromForm();
    // Log verification requested
    await api('POST', '/api/verify/request', { entity_type: 'profile', entity_id: 'profile' });
    // Open verification modal instead of saving directly
    openVerificationModal('profile', data);
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

async function triggerSmartScan() {
    showToast('Running smart scan with duplicate detection...');
    try {
        const result = await api('POST', '/api/scan/smart', { source: 'all', role: '', location: '' });
        showToast(`Found ${result.total_jobs_found} jobs, ${result.total_new_jobs} new!`);
        loadDashboard();
    } catch (err) {
        showToast('Smart scan failed — check server logs.');
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

        // Auto-fill profile form from resume analysis
        autoFillProfileFromResume(result);

        // Build the profile data from auto-filled form values
        const profileData = buildProfileDataFromForm();

        // Log verification requested
        await api('POST', '/api/verify/request', { entity_type: 'resume', entity_id: result.resume_id });

        // Open verification modal with auto-filled data
        openVerificationModal('resume', profileData, result);
    } catch (err) {
        showToast('Error analyzing resume.');
    }
});

function displayResumeResults(result) {
    const container = document.getElementById('resume-results');
    container.style.display = 'block';

    // Scores
    const scores = result.scores;
    document.getElementById('upload-scores').innerHTML = `
        <div class="stats-grid">
            <div class="stat-card"><div class="label">ATS Score</div><div class="value ${scoreColor(scores.ats_score)}">${(scores.ats_score * 100).toFixed(0)}%</div></div>
            <div class="stat-card"><div class="label">Quality</div><div class="value ${scoreColor(scores.resume_quality_score)}">${(scores.resume_quality_score * 100).toFixed(0)}%</div></div>
            <div class="stat-card"><div class="label">Technical</div><div class="value ${scoreColor(scores.technical_strength_score)}">${(scores.technical_strength_score * 100).toFixed(0)}%</div></div>
            <div class="stat-card"><div class="label">Hiring Ready</div><div class="value ${scoreColor(scores.hiring_readiness_score)}">${(scores.hiring_readiness_score * 100).toFixed(0)}%</div></div>
        </div>
    `;

    // Skills
    document.getElementById('upload-skills').innerHTML = result.skills.length > 0
        ? `<h3>Skills Detected (${result.skills.length})</h3><div class="job-skills">${result.skills.map(s => `<span class="skill-tag">${s}</span>`).join('')}</div>`
        : '';

    // Strengths
    document.getElementById('upload-strengths').innerHTML = result.strengths.length > 0
        ? `<h3 style="color:var(--green)">Strengths</h3><ul>${result.strengths.map(s => `<li>✓ ${s}</li>`).join('')}</ul>`
        : '';

    // Weaknesses
    document.getElementById('upload-weaknesses').innerHTML = result.weaknesses.length > 0
        ? `<h3 style="color:var(--red)">Weaknesses</h3><ul>${result.weaknesses.map(w => `<li>✗ ${w}</li>`).join('')}</ul>`
        : '';

    // Suggestions
    document.getElementById('upload-suggestions').innerHTML = result.suggestions.length > 0
        ? `<h3 style="color:var(--blue)">Improvement Suggestions</h3><ol>${result.suggestions.map(s => `<li>${s}</li>`).join('')}</ol>`
        : '';

    // Missing skills
    document.getElementById('upload-missing').innerHTML = result.missing_skills.length > 0
        ? `<h3 style="color:var(--yellow)">Missing Skills for ${result.target_role || 'Target Role'}</h3><div class="job-skills">${result.missing_skills.map(s => `<span class="missing-tag">${s}</span>`).join('')}</div>`
        : '';

    // Switch to analyze tab to show results
    switchResumeTab('analyze');
}

function scoreColor(score) {
    if (score >= 0.8) return 'green';
    if (score >= 0.6) return 'yellow';
    return 'red';
}

async function loadResumeHistory() {
    const { uploads } = await api('GET', '/api/resume/uploads');
    if (!uploads || uploads.length === 0) {
        document.getElementById('upload-history').innerHTML = '<div class="empty-state">No resumes uploaded yet.</div>';
        return;
    }
    document.getElementById('upload-history').innerHTML = uploads.map(r => `
        <div class="app-card">
            <div class="app-info">
                <strong>${r.filename || 'Untitled'}</strong>
                <div style="font-size:0.85rem;color:var(--text-dim)">
                    ${r.file_type?.toUpperCase() || 'TXT'} · ${r.upload_date?.slice(0,10) || '-'}
                </div>
            </div>
            <button class="btn btn-secondary" onclick="deleteUpload('${r.id}')">Delete</button>
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
        <div class="job-card">
            <div class="job-header">
                <div>
                    <div class="job-title" onclick="window.open('${job.url || '#'}', '_blank')">${job.title}</div>
                    <div class="job-company">${job.company}</div>
                    <div class="job-meta">${job.location || 'Unknown'} · ${job.source} · ${job.remote_status || ''}</div>
                </div>
                <div style="display:flex;gap:0.5rem;align-items:center">
                    <div class="job-score ${scoreClass}">${scorePct}%</div>
                    <button class="btn btn-primary btn-sm" onclick="event.stopPropagation();addToAutoApply('${job.id}')">Add to Queue</button>
                </div>
            </div>
            <div class="job-skills">
                ${skills.map(s => `<span class="skill-tag">${s}</span>`).join('')}
                ${missing.map(s => `<span class="missing-tag">-${s}</span>`).join('')}
            </div>
        </div>
    `;
}

// --- Verification Modal ---
let _pendingVerificationData = null;
let _pendingVerificationSource = null;
let _pendingResumeAnalysis = null;

function openVerificationModal(source, data, resumeAnalysis = null) {
    _pendingVerificationData = data;
    _pendingVerificationSource = source;
    _pendingResumeAnalysis = resumeAnalysis;

    // Fill modal fields from data
    document.getElementById('verify-name').textContent = data.name || '';
    document.getElementById('verify-email').textContent = data.email || '';
    document.getElementById('verify-phone').textContent = data.phone || '';
    document.getElementById('verify-skills').textContent = Array.isArray(data.skills) ? data.skills.join(', ') : (data.skills || '');
    document.getElementById('verify-experience').textContent = data.experience_years ? data.experience_years + ' years' : '';
    document.getElementById('verify-education').textContent = Array.isArray(data.education) ? data.education.map(e => typeof e === 'object' ? e.degree + ' - ' + e.school : e).join(', ') : (data.education || '');
    document.getElementById('verify-roles').textContent = Array.isArray(data.preferred_roles) ? data.preferred_roles.join(', ') : (data.preferred_roles || '');
    document.getElementById('verify-location').textContent = Array.isArray(data.preferred_locations) ? data.preferred_locations.join(', ') : (data.preferred_locations || '');
    document.getElementById('verify-remote').textContent = data.remote_preference || '';

    // Show resume summary if available
    const resumeSection = document.getElementById('verify-resume-summary');
    if (resumeAnalysis && resumeAnalysis.scores) {
        resumeSection.style.display = 'block';
        document.getElementById('verify-ats').textContent = (resumeAnalysis.scores.ats_score * 100).toFixed(0) + '%';
        document.getElementById('verify-tech').textContent = (resumeAnalysis.scores.technical_strength_score * 100).toFixed(0) + '%';
        document.getElementById('verify-hiring').textContent = (resumeAnalysis.scores.hiring_readiness_score * 100).toFixed(0) + '%';
    } else {
        resumeSection.style.display = 'none';
    }

    // Reset checkboxes and disable confirm button
    document.getElementById('verify-check-1').checked = false;
    document.getElementById('verify-check-2').checked = false;
    document.getElementById('verify-confirm-btn').disabled = true;

    // Show modal
    document.getElementById('verification-modal').style.display = 'flex';
}

function updateVerifyButton() {
    const checked1 = document.getElementById('verify-check-1').checked;
    const checked2 = document.getElementById('verify-check-2').checked;
    document.getElementById('verify-confirm-btn').disabled = !(checked1 && checked2);
}

document.getElementById('verify-check-1').addEventListener('change', updateVerifyButton);
document.getElementById('verify-check-2').addEventListener('change', updateVerifyButton);

async function handleVerifyConfirm() {
    if (!_pendingVerificationData) return;

    const data = { ..._pendingVerificationData };
    const now = new Date().toISOString();
    data.is_verified = true;
    data.verified_at = now;

    try {
        // Save profile data
        await api('PUT', '/api/profile', data);
        // Log verification accepted
        await api('POST', '/api/verify/confirm', {
            entity_type: _pendingVerificationSource,
            entity_id: 'profile',
            verified_data: _pendingVerificationData,
        });
        closeVerificationModal();
        showToast('Profile verified and saved successfully!');
        loadProfile(); // Refresh the profile form
    } catch (err) {
        showToast('Error saving profile. Please try again.');
    }
}

async function handleVerifyEdit() {
    if (_pendingVerificationSource) {
        // Log decline event
        await api('POST', '/api/verify/decline', {
            entity_type: _pendingVerificationSource,
            entity_id: 'profile',
        });
    }
    closeVerificationModal();
    showToast('You can edit your information and re-submit.');
}

function closeVerificationModal() {
    document.getElementById('verification-modal').style.display = 'none';
    _pendingVerificationData = null;
    _pendingVerificationSource = null;
    _pendingResumeAnalysis = null;
}

// --- Auto-fill Helpers ---
function autoFillProfileFromResume(result) {
    const form = document.getElementById('profile-form');
    if (result.name) form.elements['name'].value = result.name;
    if (result.email) form.elements['email'].value = result.email;
    if (result.phone) form.elements['phone'].value = result.phone;
    if (result.experience_years) form.elements['experience_years'].value = result.experience_years;
    if (result.skills && result.skills.length > 0) {
        form.elements['skills'].value = result.skills.join(', ');
    }
}

function buildProfileDataFromForm() {
    const form = document.getElementById('profile-form');
    const fd = new FormData(form);
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
    return data;
}

// --- Init ---
function loadPage(page) {
    if (page === 'dashboard') loadDashboard();
    else if (page === 'jobs') loadJobs();
    else if (page === 'auto-apply') loadAutoApplyQueue();
    else if (page === 'applications') loadApplications();
    else if (page === 'profile') loadProfile();
    else if (page === 'resume') loadResumeHistory();
    else if (page === 'tools') loadCoverLetterHistory();
    else if (page === 'career') loadCareerPage();
    else if (page === 'alerts') loadAlerts();
}

// Auto-refresh on page load
function refreshPage() {
    const activePage = document.querySelector('.nav-link.active')?.dataset?.page || 'dashboard';
    loadPage(activePage);
    showToast('Data refreshed!');
}

// --- Auto Apply Queue ---
async function addToAutoApply(jobId) {
    try {
        await api('POST', '/api/auto-apply/add', { job_id: jobId });
        showToast('Job added to auto-apply queue!');
    } catch (err) {
        showToast('Error adding job to queue');
    }
}

async function processAllQueued() {
    showToast('Processing queued applications...');
    try {
        const queue = await api('GET', '/api/auto-apply/queue?status=queued');
        for (const item of queue.items) {
            await api('POST', `/api/auto-apply/process/${item.id}`);
        }
        showToast('All queued applications processed!');
        loadAutoApplyQueue();
    } catch (err) {
        showToast('Error processing applications');
    }
}
async function loadAutoApplyQueue() {
    try {
        const queue = await api('GET', '/api/auto-apply/queue') || { items: [], total: 0 };
        const stats = await api('GET', '/api/auto-apply/stats') || { total: 0, ready: 0, pending_submission: 0, submitted: 0 };

        // Display stats
        document.getElementById('auto-apply-stats').innerHTML = `
            <div class="stat-card"><div class="label">Total</div><div class="value blue">${stats.total}</div></div>
            <div class="stat-card"><div class="label">Ready</div><div class="value green">${stats.ready}</div></div>
            <div class="stat-card"><div class="label">Pending</div><div class="value yellow">${stats.pending_submission}</div></div>
            <div class="stat-card"><div class="label">Submitted</div><div class="value green">${stats.submitted}</div></div>
        `;

        // Display queue items
        if (queue.items.length === 0) {
            document.getElementById('auto-apply-list').innerHTML = '<div class="empty-state">No jobs in queue. Add jobs from the Jobs page.</div>';
            return;
        }

        document.getElementById('auto-apply-list').innerHTML = queue.items.map(item => `
            <div class="job-card">
                <div class="job-header">
                    <div>
                        <div class="job-title">Job ID: ${item.job_id}</div>
                        <div class="job-meta">Status: <span class="skill-tag">${item.status}</span></div>
                    </div>
                    <div class="job-actions">
                        ${item.status === 'ready' ? `<button class="btn btn-primary" onclick="approveAutoApply(${item.id})">Approve</button>` : ''}
                        ${item.status === 'pending_submission' ? `<button class="btn btn-primary" onclick="submitAutoApply(${item.id})">Mark Submitted</button>` : ''}
                        ${item.status !== 'submitted' && item.status !== 'cancelled' ? `<button class="btn btn-secondary" onclick="cancelAutoApply(${item.id})">Cancel</button>` : ''}
                    </div>
                </div>
                <div class="job-meta">
                    ${item.resume_tailored ? '<span class="skill-tag">Resume Tailored</span>' : ''}
                    ${item.cover_letter_generated ? '<span class="skill-tag">Cover Letter Ready</span>' : ''}
                    ${item.application_ready ? '<span class="skill-tag">Application Ready</span>' : ''}
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Error loading auto-apply queue:', err);
    }
}

async function processAllQueued() {
    showToast('Processing queued applications...');
    try {
        const queue = await api('GET', '/api/auto-apply/queue?status=queued');
        for (const item of queue.items) {
            await api('POST', `/api/auto-apply/process/${item.id}`);
        }
        showToast('All queued applications processed!');
        loadAutoApplyQueue();
    } catch (err) {
        showToast('Error processing applications');
    }
}

async function approveAutoApply(id) {
    try {
        await api('POST', `/api/auto-apply/${id}/approve`);
        showToast('Application approved!');
        loadAutoApplyQueue();
    } catch (err) {
        showToast('Error approving application');
    }
}

async function submitAutoApply(id) {
    try {
        await api('POST', `/api/auto-apply/${id}/submit`);
        showToast('Application submitted!');
        loadAutoApplyQueue();
    } catch (err) {
        showToast('Error submitting application');
    }
}

async function cancelAutoApply(id) {
    if (!confirm('Cancel this application?')) return;
    try {
        await api('DELETE', `/api/auto-apply/${id}`);
        showToast('Application cancelled');
        loadAutoApplyQueue();
    } catch (err) {
        showToast('Error cancelling application');
    }
}

// Check authentication on load
(async function init() {
    await checkAuth();
    loadDashboard();
    // Auto-refresh every 60 seconds
    setInterval(refreshPage, 60000);
})();

// ============================================================================
// Tab Switching
// ============================================================================

function switchResumeTab(tab) {
    document.querySelectorAll('#page-resume .sub-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('#page-resume .tab-content').forEach(t => { t.style.display = 'none'; t.classList.remove('active'); });
    document.querySelector(`#page-resume .sub-tab[data-tab="${tab}"]`).classList.add('active');
    const content = document.getElementById(`tab-${tab}`);
    content.style.display = 'block';
    content.classList.add('active');
    if (tab === 'history') loadResumeHistory();
    if (tab === 'upload') loadUploadHistory();
    if (tab === 'tailor') loadTailorHistory();
}

function switchToolsTab(tab) {
    document.querySelectorAll('#page-tools .sub-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('#page-tools .tab-content').forEach(t => { t.style.display = 'none'; t.classList.remove('active'); });
    document.querySelector(`#page-tools .sub-tab[data-tab="${tab}"]`).classList.add('active');
    const content = document.getElementById(`tab-${tab}`);
    content.style.display = 'block';
    content.classList.add('active');
    if (tab === 'cover-letter') loadCoverLetterHistory();
    if (tab === 'linkedin') loadLinkedInHistory();
}

// ============================================================================
// FEATURE 1: Resume Upload
// ============================================================================

// Upload form handler
document.getElementById('upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('resume-file');
    const file = fileInput.files[0];
    if (!file) { showToast('Please select a file.'); return; }

    const targetRole = document.getElementById('upload-target-role').value.trim();
    showToast('Uploading and analyzing...');

    const formData = new FormData();
    formData.append('file', file);
    if (targetRole) formData.append('target_role', targetRole);

    try {
        const res = await fetch('/api/resume/upload', { method: 'POST', body: formData });
        const result = await res.json();
        if (res.ok) {
            displayUploadResults(result);
            loadUploadHistory();
            showToast('Upload and analysis complete!');
        } else {
            showToast(result.detail || 'Upload failed.');
        }
    } catch (err) {
        showToast('Error uploading file.');
    }
});

// Drag and drop support
const uploadArea = document.getElementById('upload-area');
const fileInput = document.getElementById('resume-file');

if (uploadArea) {
    uploadArea.addEventListener('click', () => fileInput.click());

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            uploadArea.querySelector('p').textContent = files[0].name;
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            uploadArea.querySelector('p').textContent = fileInput.files[0].name;
        }
    });
}

function displayUploadResults(result) {
    const container = document.getElementById('upload-results');
    container.style.display = 'block';
    document.getElementById('upload-output').innerHTML = `
        <div class="stats-grid">
            <div class="stat-card"><div class="label">ATS Score</div><div class="value ${scoreColor(result.scores?.ats_score || 0)}">${((result.scores?.ats_score || 0) * 100).toFixed(0)}%</div></div>
            <div class="stat-card"><div class="label">Quality</div><div class="value ${scoreColor(result.scores?.resume_quality_score || 0)}">${((result.scores?.resume_quality_score || 0) * 100).toFixed(0)}%</div></div>
            <div class="stat-card"><div class="label">File</div><div class="value blue" style="font-size:1rem">${result.filename || 'Unknown'}</div></div>
            <div class="stat-card"><div class="label">Size</div><div class="value" style="font-size:1rem">${result.file_size ? (result.file_size / 1024).toFixed(1) + ' KB' : '-'}</div></div>
        </div>
        <div class="section">
            <h3>Skills Detected (${result.skills?.length || 0})</h3>
            <div class="job-skills">${(result.skills || []).map(s => `<span class="skill-tag">${s}</span>`).join('')}</div>
        </div>
    `;
}

async function loadUploadHistory() {
    const { uploads } = await api('GET', '/api/resume/uploads');
    const container = document.getElementById('upload-history');
    if (!uploads || uploads.length === 0) {
        container.innerHTML = '<div class="empty-state">No uploaded resumes yet.</div>';
        return;
    }
    container.innerHTML = uploads.map(u => `
        <div class="app-card">
            <div class="app-info">
                <strong>${u.filename}</strong> — ${u.file_type.toUpperCase()}
                <div style="font-size:0.85rem;color:var(--text-dim)">${u.upload_date?.slice(0,10) || '-'} · ${(u.file_size / 1024).toFixed(1)} KB</div>
            </div>
            <button class="btn btn-secondary" onclick="deleteUpload('${u.id}')">Delete</button>
        </div>
    `).join('');
}

async function deleteUpload(id) {
    if (!confirm('Delete this uploaded resume?')) return;
    await api('DELETE', `/api/resume/uploads/${id}`);
    loadUploadHistory();
    showToast('Upload deleted.');
}

// ============================================================================
// FEATURE 2: Resume Improvement
// ============================================================================

document.getElementById('improve-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const resumeId = document.getElementById('improve-resume-select').value;
    const targetRole = document.getElementById('improve-target-role').value.trim();

    if (!resumeId) {
        showToast('Please select a resume first.');
        return;
    }

    showToast('Generating improvement suggestions...');
    try {
        const result = await api('POST', '/api/resume/suggestions', { resume_id: resumeId, target_role: targetRole });
        displayImprovementResults(result);
        showToast('Suggestions generated!');
    } catch (err) {
        showToast('Error generating suggestions.');
    }
});

// Load resumes for improve dropdown
async function loadResumesForImprove() {
    const { uploads } = await api('GET', '/api/resume/uploads');
    const select = document.getElementById('improve-resume-select');
    if (uploads && uploads.length > 0) {
        select.innerHTML = '<option value="">-- Select a resume --</option>' +
            uploads.map(r => `<option value="${r.id}">${r.filename} (${r.file_type?.toUpperCase() || 'TXT'})</option>`).join('');
    } else {
        select.innerHTML = '<option value="">-- No resumes uploaded yet --</option>';
    }
}

function displayImprovementResults(result) {
    const container = document.getElementById('improve-results');
    container.style.display = 'block';
    let html = '';

    // Grade
    const grade = result.overall_grade || 'N/A';
    const gradeClass = grade.startsWith('A') ? 'grade-A' : grade.startsWith('B') ? 'grade-B' : grade.startsWith('C') ? 'grade-C' : 'grade-D';
    html += `<div class="grade-display ${gradeClass}">Grade: ${grade}</div>`;

    // Scores comparison
    html += `<div class="stats-grid">
        <div class="stat-card"><div class="label">Current ATS</div><div class="value ${scoreColor(result.score_before?.ats || 0)}">${((result.score_before?.ats || 0) * 100).toFixed(0)}%</div></div>
        <div class="stat-card"><div class="label">After Improvement</div><div class="value ${scoreColor(result.score_after?.ats || 0)}">${((result.score_after?.ats || 0) * 100).toFixed(0)}%</div></div>
        <div class="stat-card"><div class="label">Improvement</div><div class="value green">+${(((result.score_after?.ats || 0) - (result.score_before?.ats || 0)) * 100).toFixed(0)}%</div></div>
    </div>`;

    // Strengths
    if (result.strengths?.length) {
        html += `<h3 style="color:var(--green)">Strengths</h3><ul>${result.strengths.map(s => `<li>✓ ${s}</li>`).join('')}</ul>`;
    }

    // Weaknesses
    if (result.weaknesses?.length) {
        html += `<h3 style="color:var(--red)">Weaknesses</h3><ul>${result.weaknesses.map(w => `<li>✗ ${w}</li>`).join('')}</ul>`;
    }

    // Improvements
    if (result.improvements?.length) {
        html += `<h3 style="color:var(--blue)">Recommended Improvements</h3>`;
        result.improvements.forEach(imp => {
            html += `<div class="improvement-card">
                <div class="header">
                    <span class="title">${imp.title}</span>
                    <span class="priority priority-${imp.priority}">${imp.priority}</span>
                </div>
                <div class="description">${imp.description}</div>
            </div>`;
        });
    }

    // Keywords
    if (result.recommended_keywords?.length) {
        html += `<h3 style="color:var(--yellow)">Recommended Keywords</h3><div class="job-skills">${result.recommended_keywords.map(k => `<span class="skill-tag">${k}</span>`).join('')}</div>`;
    }

    document.getElementById('improve-output').innerHTML = html;
}

// ============================================================================
// FEATURE 3: Cover Letter
// ============================================================================

document.getElementById('cover-letter-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
        resume_text: document.getElementById('cl-resume-text').value.trim(),
        job_description: document.getElementById('cl-job-desc').value.trim(),
        company_name: document.getElementById('cl-company').value.trim(),
        role_title: document.getElementById('cl-role').value.trim(),
        tone: document.getElementById('cl-tone').value,
        candidate_name: document.getElementById('cl-name').value.trim(),
    };

    if (!data.resume_text || !data.job_description) {
        showToast('Please provide resume text and job description.');
        return;
    }

    showToast('Generating cover letter...');
    try {
        const result = await api('POST', '/api/cover-letter/generate', data);
        displayCoverLetter(result);
        loadCoverLetterHistory();
        showToast('Cover letter generated!');
    } catch (err) {
        showToast('Error generating cover letter.');
    }
});

function displayCoverLetter(result) {
    const container = document.getElementById('cl-results');
    container.style.display = 'block';
    document.getElementById('cl-output').innerHTML = `
        <div class="cover-letter-output">${result.letter_text}</div>
        <div style="display:flex;gap:0.5rem;margin-top:1rem">
            <button class="btn btn-secondary" onclick="copyCoverLetter()">Copy</button>
            <button class="btn btn-secondary" onclick="downloadCoverLetter()">Download</button>
        </div>
        <div style="margin-top:0.5rem;color:var(--text-dim);font-size:0.85rem">Word count: ${result.word_count} · Tone: ${result.tone}</div>
    `;
    window._lastCoverLetter = result.letter_text;
}

function copyCoverLetter() {
    navigator.clipboard.writeText(window._lastCoverLetter || '');
    showToast('Cover letter copied to clipboard!');
}

function downloadCoverLetter() {
    const blob = new Blob([window._lastCoverLetter || ''], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'cover-letter.txt';
    a.click();
    URL.revokeObjectURL(url);
}

async function loadCoverLetterHistory() {
    const { cover_letters } = await api('GET', '/api/cover-letter/history');
    const container = document.getElementById('cl-history');
    if (!cover_letters || cover_letters.length === 0) {
        container.innerHTML = '<div class="empty-state">No cover letters generated yet.</div>';
        return;
    }
    container.innerHTML = cover_letters.map(cl => `
        <div class="app-card">
            <div class="app-info">
                <strong>${cl.company_name || 'Unknown'}</strong> — ${cl.role_title || 'Unknown Role'}
                <div style="font-size:0.85rem;color:var(--text-dim)">${cl.tone} · ${cl.word_count} words · ${cl.created_at?.slice(0,10) || '-'}</div>
            </div>
            <div style="display:flex;gap:0.5rem">
                <button class="btn btn-secondary" onclick="viewCoverLetter(${cl.id})">View</button>
                <button class="btn btn-secondary" onclick="deleteCoverLetter(${cl.id})">Delete</button>
            </div>
        </div>
    `).join('');
}

async function viewCoverLetter(id) {
    const letter = await api('GET', `/api/cover-letter/${id}`);
    if (letter && letter.letter_text) {
        displayCoverLetter({ letter_text: letter.letter_text, word_count: letter.word_count, tone: letter.tone });
    }
}

async function deleteCoverLetter(id) {
    if (!confirm('Delete this cover letter?')) return;
    await api('DELETE', `/api/cover-letter/${id}`);
    loadCoverLetterHistory();
    showToast('Cover letter deleted.');
}

// ============================================================================
// FEATURE 5: Interview Prep
// ============================================================================

document.getElementById('interview-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const categories = Array.from(document.getElementById('int-category').selectedOptions).map(o => o.value);
    const data = {
        resume_text: document.getElementById('int-resume-text').value.trim(),
        role_title: document.getElementById('int-role').value.trim(),
        categories: categories,
        difficulty: document.getElementById('int-difficulty').value,
        count: parseInt(document.getElementById('int-count').value) || 10,
    };

    showToast('Generating interview questions...');
    try {
        const result = await api('POST', '/api/interview/questions', data);
        displayInterviewQuestions(result.questions);
        showToast(`Generated ${result.total} questions!`);
    } catch (err) {
        showToast('Error generating questions.');
    }
});

function displayInterviewQuestions(questions) {
    const container = document.getElementById('int-results');
    container.style.display = 'block';
    let html = '';
    questions.forEach((q, i) => {
        html += `<div class="interview-card">
            <div class="meta">
                <span class="badge">${q.category}</span>
                <span class="badge">${q.difficulty}</span>
            </div>
            <div class="question">${i + 1}. ${q.question}</div>
            <div class="answer">${q.sample_answer}</div>
            <div class="tips">💡 ${q.tips}</div>
        </div>`;
    });
    document.getElementById('int-output').innerHTML = html;
}

// ============================================================================
// FEATURE 6: Skill Gap Analysis
// ============================================================================

document.getElementById('skill-gap-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
        resume_text: document.getElementById('sg-resume-text').value.trim(),
        job_description: document.getElementById('sg-job-desc').value.trim(),
    };

    if (!data.resume_text || !data.job_description) {
        showToast('Please provide both resume and job description.');
        return;
    }

    showToast('Analyzing skill gap...');
    try {
        const result = await api('POST', '/api/skill-gap/analyze', data);
        displaySkillGap(result);
        showToast('Analysis complete!');
    } catch (err) {
        showToast('Error analyzing skill gap.');
    }
});

function displaySkillGap(result) {
    const container = document.getElementById('sg-results');
    container.style.display = 'block';
    let html = `<div class="stats-grid">
        <div class="stat-card"><div class="label">Match Score</div><div class="value ${scoreColor(result.match_percentage / 100)}">${result.match_percentage}%</div></div>
        <div class="stat-card"><div class="label">Matched Skills</div><div class="value green">${result.total_matched}</div></div>
        <div class="stat-card"><div class="label">Missing Skills</div><div class="value red">${result.total_missing}</div></div>
    </div>`;

    html += `<div class="skill-comparison">
        <div class="skill-list">
            <h3 style="color:var(--green)">Matched Skills</h3>
            ${(result.matched_skills || []).map(s => `<div class="skill-item matched">✓ ${s}</div>`).join('')}
        </div>
        <div class="skill-list">
            <h3 style="color:var(--red)">Missing Skills</h3>
            ${(result.missing_skills || []).map(s => `<div class="skill-item missing">✗ ${s}</div>`).join('')}
        </div>
    </div>`;

    if (result.learning_areas?.length) {
        html += `<h3>Recommended Learning Areas</h3>`;
        result.learning_areas.forEach(area => {
            html += `<div class="improvement-card">
                <div class="title">${area.category}</div>
                <div class="description">${area.skills.join(', ')}</div>
            </div>`;
        });
    }

    document.getElementById('sg-output').innerHTML = html;
}

// ============================================================================
// FEATURE 7: LinkedIn Analyzer
// ============================================================================

document.getElementById('linkedin-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
        headline: document.getElementById('li-headline').value.trim(),
        about: document.getElementById('li-about').value.trim(),
        skills: document.getElementById('li-skills').value.trim(),
        experience: document.getElementById('li-experience').value.trim(),
    };

    showToast('Analyzing LinkedIn profile...');
    try {
        const result = await api('POST', '/api/linkedin/analyze', data);
        displayLinkedInResults(result);
        loadLinkedInHistory();
        showToast('Analysis complete!');
    } catch (err) {
        showToast('Error analyzing profile.');
    }
});

function displayLinkedInResults(result) {
    const container = document.getElementById('li-results');
    container.style.display = 'block';
    let html = `<div class="linkedin-scores">
        <div class="linkedin-score-card">
            <div class="score ${scoreColor(result.visibility_score / 100)}">${result.visibility_score}</div>
            <div class="label">Visibility Score</div>
        </div>
        <div class="linkedin-score-card">
            <div class="score ${scoreColor(result.strength_score / 100)}">${result.strength_score}</div>
            <div class="label">Profile Strength</div>
        </div>
    </div>`;

    if (result.suggestions?.length) {
        html += `<h3 style="color:var(--blue)">Optimization Suggestions</h3>`;
        result.suggestions.forEach(s => {
            html += `<div class="improvement-card"><div class="description">${s}</div></div>`;
        });
    }

    if (result.missing_keywords?.length) {
        html += `<h3 style="color:var(--yellow)">Missing Keywords</h3><div class="job-skills">${result.missing_keywords.map(k => `<span class="missing-tag">${k}</span>`).join('')}</div>`;
    }

    if (result.detected_skills?.length) {
        html += `<h3>Detected Skills</h3><div class="job-skills">${result.detected_skills.map(s => `<span class="skill-tag">${s}</span>`).join('')}</div>`;
    }

    document.getElementById('li-output').innerHTML = html;
}

async function loadLinkedInHistory() {
    const { reports } = await api('GET', '/api/linkedin/history');
    const container = document.getElementById('li-history');
    if (!reports || reports.length === 0) {
        container.innerHTML = '<div class="empty-state">No LinkedIn analyses yet.</div>';
        return;
    }
    container.innerHTML = reports.map(r => `
        <div class="app-card">
            <div class="app-info">
                <strong>Visibility: ${r.visibility_score}</strong> · Strength: ${r.strength_score}
                <div style="font-size:0.85rem;color:var(--text-dim)">${r.analyzed_at?.slice(0,10) || '-'}</div>
            </div>
        </div>
    `).join('');
}

// ============================================================================
// FEATURE 8: Resume Tailoring
// ============================================================================

document.getElementById('tailor-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
        resume_text: document.getElementById('tailor-resume-text').value.trim(),
        job_description: document.getElementById('tailor-job-desc').value.trim(),
    };

    if (!data.resume_text || !data.job_description) {
        showToast('Please provide both resume and job description.');
        return;
    }

    showToast('Tailoring resume...');
    try {
        const result = await api('POST', '/api/resume/tailor', data);
        displayTailoredResume(result);
        loadTailorHistory();
        showToast('Resume tailored!');
    } catch (err) {
        showToast('Error tailoring resume.');
    }
});

function displayTailoredResume(result) {
    const container = document.getElementById('tailor-results');
    container.style.display = 'block';
    let html = `<div class="stats-grid">
        <div class="stat-card"><div class="label">Original Score</div><div class="value ${scoreColor(result.original_score)}">${(result.original_score * 100).toFixed(0)}%</div></div>
        <div class="stat-card"><div class="label">Tailored Score</div><div class="value ${scoreColor(result.tailored_score)}">${(result.tailored_score * 100).toFixed(0)}%</div></div>
        <div class="stat-card"><div class="label">Improvement</div><div class="value green">+${result.improvement_pct}%</div></div>
    </div>`;

    html += `<div class="tailored-comparison">
        <div class="tailored-panel">
            <h3>Original</h3>
            <div class="text-content">${result.original_text}</div>
        </div>
        <div class="tailored-panel">
            <h3>Tailored</h3>
            <div class="text-content">${result.tailored_text}</div>
        </div>
    </div>`;

    if (result.keywords_added?.length) {
        html += `<h3 style="margin-top:1rem">Keywords Added</h3><div class="job-skills">${result.keywords_added.map(k => `<span class="skill-tag">${k}</span>`).join('')}</div>`;
    }

    if (result.changes_made?.length) {
        html += `<h3>Changes Made</h3><ul>${result.changes_made.map(c => `<li>${c}</li>`).join('')}</ul>`;
    }

    document.getElementById('tailor-output').innerHTML = html;
}

async function loadTailorHistory() {
    const { tailored_resumes } = await api('GET', '/api/resume/tailored');
    const container = document.getElementById('tailor-history');
    if (!tailored_resumes || tailored_resumes.length === 0) {
        container.innerHTML = '<div class="empty-state">No tailored resumes yet.</div>';
        return;
    }
    container.innerHTML = tailored_resumes.map(r => `
        <div class="app-card">
            <div class="app-info">
                <strong>Original: ${(r.original_score * 100).toFixed(0)}%</strong> → <strong style="color:var(--green)">${(r.tailored_score * 100).toFixed(0)}%</strong>
                <div style="font-size:0.85rem;color:var(--text-dim)">+${r.improvement_pct}% improvement · ${r.created_at?.slice(0,10) || '-'}</div>
            </div>
        </div>
    `).join('');
}

// ============================================================================
// FEATURE 9: Alerts
// ============================================================================

document.getElementById('alert-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
        role: document.getElementById('alert-role').value.trim(),
        location: document.getElementById('alert-location').value.trim(),
        experience_level: document.getElementById('alert-experience').value,
        frequency: document.getElementById('alert-frequency').value,
        remote_only: document.getElementById('alert-remote').checked,
    };

    showToast('Creating alert...');
    try {
        await api('POST', '/api/alerts/subscribe', data);
        loadAlerts();
        showToast('Alert created!');
        e.target.reset();
    } catch (err) {
        showToast('Error creating alert.');
    }
});

async function loadAlerts() {
    const { alerts } = await api('GET', '/api/alerts/preferences');
    const container = document.getElementById('alerts-list');
    if (!alerts || alerts.length === 0) {
        container.innerHTML = '<div class="empty-state">No active alerts. Create one above!</div>';
        return;
    }
    container.innerHTML = alerts.map(a => `
        <div class="alert-card">
            <div class="alert-info">
                <div class="alert-role">${a.role || 'All Roles'}</div>
                <div class="alert-meta">${a.location || 'Any Location'} · ${a.frequency} · ${a.remote_only ? 'Remote Only' : 'Any'}</div>
            </div>
            <div class="alert-actions">
                <button class="btn btn-secondary" onclick="toggleAlert(${a.id}, ${a.is_active})">${a.is_active ? 'Pause' : 'Resume'}</button>
                <button class="btn btn-secondary" onclick="deleteAlert(${a.id})">Delete</button>
            </div>
        </div>
    `).join('');
}

async function toggleAlert(id, currentlyActive) {
    await api('PUT', `/api/alerts/${id}`, { is_active: !currentlyActive });
    loadAlerts();
    showToast(currentlyActive ? 'Alert paused.' : 'Alert resumed.');
}

async function deleteAlert(id) {
    if (!confirm('Delete this alert?')) return;
    await api('DELETE', `/api/alerts/${id}`);
    loadAlerts();
    showToast('Alert deleted.');
}

// ============================================================================
// FEATURE 10: Dashboard Analytics
// ============================================================================

async function loadDashboardAnalytics() {
    try {
        const stats = await api('GET', '/api/dashboard/stats');
        // Update stats grid with additional metrics
        const grid = document.getElementById('stats-grid');
        if (stats.application_metrics) {
            grid.innerHTML += `
                <div class="stat-card"><div class="label">Interviews</div><div class="value green">${stats.application_metrics.interview_rate || 0}%</div></div>
                <div class="stat-card"><div class="label">Offers</div><div class="value yellow">${stats.application_metrics.offer_rate || 0}%</div></div>
            `;
        }
    } catch (err) {
        console.log('Analytics not available yet');
    }
}

// ============================================================================
// Enhanced Applications (Feature 4)
// ============================================================================

async function loadApplications() {
    const { applications } = await api('GET', '/api/applications');
    const stats = await api('GET', '/api/applications/stats');

    let html = '';
    if (stats && stats.total > 0) {
        html += `<div class="stats-grid" style="margin-bottom:1.5rem">
            <div class="stat-card"><div class="label">Total</div><div class="value">${stats.total}</div></div>
            <div class="stat-card"><div class="label">Interviews</div><div class="value green">${(stats.interview || 0) + (stats.assessment || 0)}</div></div>
            <div class="stat-card"><div class="label">Offers</div><div class="value yellow">${(stats.offer || 0) + (stats.accepted || 0)}</div></div>
            <div class="stat-card"><div class="label">Rejected</div><div class="value red">${stats.rejected || 0}</div></div>
        </div>`;
    }

    if (applications.length === 0) {
        html += '<div class="empty-state">No applications tracked yet.</div>';
    } else {
        applications.forEach(app => {
            html += `<div class="app-card">
                <div class="app-info">
                    <strong>${app.company}</strong> — ${app.role}
                    <div style="font-size:0.85rem;color:var(--text-dim)">Score: ${(app.match_score * 100).toFixed(0)}% · Updated: ${app.updated_date?.slice(0,10) || '-'}</div>
                </div>
                <div style="display:flex;gap:0.5rem;align-items:center">
                    <select class="input" style="width:auto;padding:0.3rem 0.5rem;font-size:0.8rem" onchange="updateAppStatus('${app.job_id}', this.value)">
                        <option value="saved" ${app.status==='saved'?'selected':''}>Saved</option>
                        <option value="applied" ${app.status==='applied'?'selected':''}>Applied</option>
                        <option value="interview" ${app.status==='interview'?'selected':''}>Interview</option>
                        <option value="assessment" ${app.status==='assessment'?'selected':''}>Assessment</option>
                        <option value="offer" ${app.status==='offer'?'selected':''}>Offer</option>
                        <option value="rejected" ${app.status==='rejected'?'selected':''}>Rejected</option>
                        <option value="accepted" ${app.status==='accepted'?'selected':''}>Accepted</option>
                    </select>
                    <button class="btn btn-secondary" style="padding:0.3rem 0.5rem;font-size:0.8rem" onclick="deleteApp('${app.job_id}')">×</button>
                </div>
            </div>`;
        });
    }
    document.getElementById('applications-list').innerHTML = html;
}

async function updateAppStatus(appId, status) {
    await api('PUT', `/api/applications/${appId}`, { status });
    showToast('Status updated.');
}

async function deleteApp(appId) {
    if (!confirm('Delete this application?')) return;
    await api('DELETE', `/api/applications/${appId}`);
    loadApplications();
    showToast('Application deleted.');
}
