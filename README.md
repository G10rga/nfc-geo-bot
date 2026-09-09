# NFC Geo Bot

Python CLI that looks up businesses via the **Google Places API** and writes them into your Google Sheet (`Name`, `Location`, `Sold`, `Name on Maps`, `Verified Location`, `Phone`).

## Setup

### 1. Install

```powershell
cd C:\Users\user\nfc-geo-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

### 2. Google Places API key

1. Open [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select a project
3. Enable **Places API (New)**
4. Create an API key → put it in `.env` as `GOOGLE_PLACES_API_KEY`

### 3. Google Sheets access (OAuth — your Google account)

No service-account key needed (works when org policy blocks key creation).

1. In the same Cloud project: enable **Google Sheets API** and **Google Drive API**
2. **APIs & Services → OAuth consent screen**
   - User type: **External** (or Internal if on Workspace)
   - App name: e.g. `NFC Geo Bot`
   - Add your email as a test user
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Download the JSON
4. Save it in this folder as `credentials.json`
5. Put the Sheet ID (from the URL) in `.env` as `GOOGLE_SHEET_ID`
6. Set `GOOGLE_SHEET_TAB` to your tab name (often `Sheet1`)

First time you run a command, a browser opens — sign in with the Google account that **owns or can edit** the spreadsheet. A `token.json` file is saved so you won’t need to log in every time.

## Usage

Add one business (appends a new row):

```powershell
python main.py add "urban fitness" -l "Tbilisi"
python main.py add "Power Max" -l "saburtalo" --dry-run
```

Enrich existing rows that already have **Name** / **Location** but are missing Maps fields or phone:

```powershell
python main.py enrich
python main.py enrich --limit 10 --dry-run
```

## Notes

- Uses the official Places API (not browser scraping).
- First successful `enrich`/`add` ensures a **Phone** column in column F.
- `Sold` is left blank for you to fill manually.
- Keep `credentials.json` and `token.json` private (they are gitignored).
