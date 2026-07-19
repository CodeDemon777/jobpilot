// JobPilot Browser Extension - Popup Script

const API_URL = 'http://localhost:8000';

// DOM Elements
const loginSection = document.getElementById('login-section');
const registerSection = document.getElementById('register-section');
const saveSection = document.getElementById('save-section');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const saveBtn = document.getElementById('save-btn');
const analyzeBtn = document.getElementById('analyze-btn');
const logoutBtn = document.getElementById('logout-btn');
const saveResult = document.getElementById('save-result');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  // Check if user is logged in
  const token = await getAuthToken();
  if (token) {
    showSaveSection();
    await extractJobInfo();
  }

  // Event listeners
  loginForm.addEventListener('submit', handleLogin);
  registerForm.addEventListener('submit', handleRegister);
  saveBtn.addEventListener('click', handleSaveJob);
  analyzeBtn.addEventListener('click', handleAnalyzeJob);
  logoutBtn.addEventListener('click', handleLogout);
  document.getElementById('show-register').addEventListener('click', () => {
    loginSection.classList.add('hidden');
    registerSection.classList.remove('hidden');
  });
  document.getElementById('show-login').addEventListener('click', () => {
    registerSection.classList.add('hidden');
    loginSection.classList.remove('hidden');
  });
});

// Auth functions
async function getAuthToken() {
  const result = await chrome.storage.local.get(['authToken']);
  return result.authToken;
}

async function setAuthToken(token) {
  await chrome.storage.local.set({ authToken: token });
}

async function clearAuthToken() {
  await chrome.storage.local.remove(['authToken']);
}

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;

  try {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await fetch(`${API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString()
    });

    const data = await response.json();

    if (response.ok && data.access_token) {
      await setAuthToken(data.access_token);
      showSaveSection();
      await extractJobInfo();
    } else {
      showError(data.detail || 'Login failed');
    }
  } catch (err) {
    showError('Connection failed. Is JobPilot running?');
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const name = document.getElementById('reg-name').value;
  const email = document.getElementById('reg-email').value;
  const password = document.getElementById('reg-password').value;

  try {
    const response = await fetch(`${API_URL}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, name })
    });

    const data = await response.json();

    if (response.ok && data.id) {
      showSuccess('Account created! Please login.');
      registerSection.classList.add('hidden');
      loginSection.classList.remove('hidden');
    } else {
      showError(data.detail || 'Registration failed');
    }
  } catch (err) {
    showError('Connection failed. Is JobPilot running?');
  }
}

async function handleLogout() {
  await clearAuthToken();
  loginSection.classList.remove('hidden');
  saveSection.classList.add('hidden');
}

function showSaveSection() {
  loginSection.classList.add('hidden');
  registerSection.classList.add('hidden');
  saveSection.classList.remove('hidden');
}

// Extract job info from current page
async function extractJobInfo() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    // Execute content script to extract job info
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      function: extractJobFromPage
    });

    if (results && results[0] && results[0].result) {
      const jobInfo = results[0].result;
      document.getElementById('job-title').value = jobInfo.title || '';
      document.getElementById('job-company').value = jobInfo.company || '';
      document.getElementById('job-location').value = jobInfo.location || '';
      document.getElementById('job-url').value = tab.url || '';
      document.getElementById('job-description').value = jobInfo.description || '';
    }
  } catch (err) {
    console.error('Failed to extract job info:', err);
  }
}

// Content script function to extract job info from page
function extractJobFromPage() {
  const jobInfo = {
    title: '',
    company: '',
    location: '',
    description: ''
  };

  // Try to extract title
  const titleSelectors = [
    'h1', 'h2', '[class*="title"]', '[class*="job-title"]',
    '[data-testid="job-title"]', '.job-title', '.posting-headline'
  ];
  for (const selector of titleSelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.trim().length > 5) {
      jobInfo.title = el.textContent.trim();
      break;
    }
  }

  // Try to extract company
  const companySelectors = [
    '[class*="company"]', '[class*="employer"]', '[data-testid="company-name"]',
    '.company-name', '.posting-company'
  ];
  for (const selector of companySelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.trim().length > 2) {
      jobInfo.company = el.textContent.trim();
      break;
    }
  }

  // Try to extract location
  const locationSelectors = [
    '[class*="location"]', '[data-testid="location"]',
    '.location', '.posting-location'
  ];
  for (const selector of locationSelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.trim().length > 2) {
      jobInfo.location = el.textContent.trim();
      break;
    }
  }

  // Try to extract description
  const descSelectors = [
    '[class*="description"]', '[class*="job-description"]',
    '.description', '.posting-body', 'article'
  ];
  for (const selector of descSelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.trim().length > 50) {
      jobInfo.description = el.textContent.trim().substring(0, 500);
      break;
    }
  }

  return jobInfo;
}

// Save job to JobPilot
async function handleSaveJob() {
  const token = await getAuthToken();
  if (!token) {
    showError('Please login first');
    return;
  }

  const jobData = {
    url: document.getElementById('job-url').value,
    title: document.getElementById('job-title').value,
    company: document.getElementById('job-company').value,
    location: document.getElementById('job-location').value,
    description: document.getElementById('job-description').value
  };

  if (!jobData.url) {
    showError('Please enter a job URL');
    return;
  }

  saveBtn.disabled = true;
  saveBtn.innerHTML = '<span class="spinner"></span> Saving...';

  try {
    const response = await fetch(`${API_URL}/api/jobs/import`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ url: jobData.url })
    });

    const data = await response.json();

    if (response.ok && data.job) {
      showSuccess(`Job saved! Match score: ${(data.match_score * 100).toFixed(0)}%`);
    } else {
      showError(data.detail || 'Failed to save job');
    }
  } catch (err) {
    showError('Connection failed. Is JobPilot running?');
  } finally {
    saveBtn.disabled = false;
    saveBtn.innerHTML = 'Save to JobPilot';
  }
}

// Analyze job match
async function handleAnalyzeJob() {
  const token = await getAuthToken();
  if (!token) {
    showError('Please login first');
    return;
  }

  const jobData = {
    url: document.getElementById('job-url').value,
    title: document.getElementById('job-title').value,
    company: document.getElementById('job-company').value,
    location: document.getElementById('job-location').value,
    description: document.getElementById('job-description').value
  };

  if (!jobData.url) {
    showError('Please enter a job URL');
    return;
  }

  analyzeBtn.disabled = true;
  analyzeBtn.innerHTML = '<span class="spinner"></span> Analyzing...';

  try {
    const response = await fetch(`${API_URL}/api/jobs/import`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ url: jobData.url })
    });

    const data = await response.json();

    if (response.ok && data.match_result) {
      const match = data.match_result;
      let resultHtml = `<div class="success">
        <strong>Match Analysis:</strong><br>
        Score: ${(match.overall_score * 100).toFixed(0)}%<br>
        Skills: ${(match.skills_score * 100).toFixed(0)}%<br>`;
      if (match.strengths && match.strengths.length > 0) {
        resultHtml += `Strengths: ${match.strengths.slice(0, 3).join(', ')}<br>`;
      }
      if (match.missing_skills && match.missing_skills.length > 0) {
        resultHtml += `Missing: ${match.missing_skills.slice(0, 3).join(', ')}`;
      }
      resultHtml += '</div>';
      saveResult.innerHTML = resultHtml;
      saveResult.classList.remove('hidden');
    } else {
      showError(data.detail || 'Analysis failed');
    }
  } catch (err) {
    showError('Connection failed. Is JobPilot running?');
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.innerHTML = 'Analyze Match';
  }
}

// UI helpers
function showSuccess(message) {
  saveResult.innerHTML = `<div class="success">${message}</div>`;
  saveResult.classList.remove('hidden');
}

function showError(message) {
  saveResult.innerHTML = `<div class="error">${message}</div>`;
  saveResult.classList.remove('hidden');
}
