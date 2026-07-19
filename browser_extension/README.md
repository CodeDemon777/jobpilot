# JobPilot Browser Extension

Save jobs from any website to JobPilot with one click!

## Features

- **One-Click Save**: Click the floating button on any job page to save it to JobPilot
- **Auto-Extract**: Automatically extracts job title, company, location, and description
- **Match Analysis**: See how well the job matches your profile
- **Login Integration**: Securely connects to your JobPilot account

## Installation

### Chrome/Edge (Developer Mode)

1. Open Chrome/Edge and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `browser_extension` folder from this project
5. The extension icon will appear in your toolbar

### First Time Setup

1. Click the extension icon
2. Login with your JobPilot credentials
3. The extension is ready to use!

## Usage

### Method 1: Floating Button

1. Navigate to any job posting (LinkedIn, Indeed, Naukri, etc.)
2. Click the "Save to JobPilot" button in the bottom-right corner
3. Review the extracted job information
4. Click "Save to JobPilot" to save

### Method 2: Extension Popup

1. Click the JobPilot icon in your toolbar
2. The popup will automatically extract job info from the current page
3. Review and edit the extracted information
4. Click "Save to JobPilot" or "Analyze Match"

## Supported Websites

The extension works on any website, but is optimized for:

- LinkedIn Jobs
- Indeed
- Naukri
- Glassdoor
- Wellfound (AngelList)
- Company career pages
- Any job board with structured content

## How It Works

1. **Content Script**: Runs on every page, extracts job information using CSS selectors
2. **Popup**: Provides a UI for reviewing and saving jobs
3. **Background Script**: Handles API communication with JobPilot backend
4. **Storage**: Securely stores authentication tokens

## Permissions

- `activeTab`: Access the current tab to extract job information
- `storage`: Store authentication tokens securely
- `scripting`: Execute content scripts on demand
- `host_permissions`: Communicate with JobPilot backend

## Privacy

- The extension only sends job URLs to your JobPilot backend
- No personal data is collected or shared
- Authentication tokens are stored locally in your browser
- No tracking or analytics

## Troubleshooting

### "Connection failed" error

Make sure the JobPilot web server is running:
```bash
cd jobpilot
python -m uvicorn jobpilot.web.app:app --host 127.0.0.1 --port 8000
```

### Job info not extracted

Some websites use dynamic loading. Try:
1. Wait for the page to fully load
2. Click the extension popup again
3. Manually fill in any missing fields

### Extension not working

1. Go to `chrome://extensions/`
2. Click the refresh button on the JobPilot extension
3. Try again
