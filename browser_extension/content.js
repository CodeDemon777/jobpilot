// JobPilot Browser Extension - Content Script
// This script runs on every page and provides job extraction capabilities

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extractJob') {
    const jobInfo = extractJobFromPage();
    sendResponse(jobInfo);
  }
  return true;
});

// Extract job information from the current page
function extractJobFromPage() {
  const jobInfo = {
    title: '',
    company: '',
    location: '',
    description: '',
    url: window.location.href
  };

  // Try to extract title
  const titleSelectors = [
    'h1', 'h2', '[class*="title"]', '[class*="job-title"]',
    '[data-testid="job-title"]', '.job-title', '.posting-headline',
    'h1[class*="job"]', 'h1[class*="posting"]'
  ];
  for (const selector of titleSelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.trim().length > 5 && el.textContent.trim().length < 200) {
      jobInfo.title = el.textContent.trim();
      break;
    }
  }

  // Try to extract company
  const companySelectors = [
    '[class*="company"]', '[class*="employer"]', '[data-testid="company-name"]',
    '.company-name', '.posting-company', '[class*="org"]'
  ];
  for (const selector of companySelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.trim().length > 2 && el.textContent.trim().length < 100) {
      jobInfo.company = el.textContent.trim();
      break;
    }
  }

  // Try to extract location
  const locationSelectors = [
    '[class*="location"]', '[data-testid="location"]',
    '.location', '.posting-location', '[class*="place"]'
  ];
  for (const selector of locationSelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.trim().length > 2 && el.textContent.trim().length < 100) {
      jobInfo.location = el.textContent.trim();
      break;
    }
  }

  // Try to extract description
  const descSelectors = [
    '[class*="description"]', '[class*="job-description"]',
    '.description', '.posting-body', 'article', '[class*="content"]'
  ];
  for (const selector of descSelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent.trim().length > 50) {
      jobInfo.description = el.textContent.trim().substring(0, 1000);
      break;
    }
  }

  return jobInfo;
}

// Add floating button to save jobs
function addSaveButton() {
  // Only add if not already present
  if (document.getElementById('jobpilot-save-btn')) return;

  const btn = document.createElement('button');
  btn.id = 'jobpilot-save-btn';
  btn.innerHTML = '💾 Save to JobPilot';
  btn.onclick = async () => {
    const jobInfo = extractJobFromPage();
    // Send to background script
    chrome.runtime.sendMessage({ action: 'saveJob', jobInfo });
  };
  document.body.appendChild(btn);
}

// Add save button when page loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', addSaveButton);
} else {
  addSaveButton();
}
