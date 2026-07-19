// JobPilot Browser Extension - Background Service Worker

const API_URL = 'http://localhost:8000';

// Listen for messages from content script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'saveJob') {
    handleSaveJob(request.jobInfo).then(sendResponse);
    return true; // Keep message channel open for async response
  }
});

// Save job to JobPilot backend
async function handleSaveJob(jobInfo) {
  try {
    // Get auth token
    const result = await chrome.storage.local.get(['authToken']);
    const token = result.authToken;

    if (!token) {
      return { success: false, error: 'Not logged in' };
    }

    // Import job via API
    const response = await fetch(`${API_URL}/api/jobs/import`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ url: jobInfo.url || window.location.href })
    });

    const data = await response.json();

    if (response.ok && data.job) {
      // Show notification
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: 'Job Saved to JobPilot',
        message: `${data.job.title} at ${data.job.company} - Match: ${(data.match_score * 100).toFixed(0)}%`
      });
      return { success: true, job: data.job };
    } else {
      return { success: false, error: data.detail || 'Failed to save job' };
    }
  } catch (err) {
    return { success: false, error: 'Connection failed' };
  }
}

// Handle extension installation
chrome.runtime.onInstalled.addListener(() => {
  console.log('JobPilot extension installed');
});