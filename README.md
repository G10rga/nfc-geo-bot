# NFC Geo Bot

Looks up businesses on **Google Maps in a browser** (no Places API / no API key for Maps) and writes results into your Google Sheet:
`Name | Location | Sold | Name on Maps | Verified Location | Phone`

## Setup

### 1. Install

```powershell
cd C:\Users\user\nfc-geo-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
```

### 2. Google Sheets access (OAuth — only Google Cloud piece left)

Needed only so the bot can write your spreadsheet. No Places API.

1. Cloud Console → enable **Google Sheets API** + **Google Drive API**
2. **OAuth consent screen** → add yourself as a test user
3. **Credentials → Create → OAuth client ID → Desktop app**
4. Download JSON → save as `credentials.json` in this folder
5. Set `GOOGLE_SHEET_ID` and `GOOGLE_SHEET_TAB` in `.env`

First run opens a browser to sign in; then `token.json` is saved.

## Usage

```powershell
python main.py add "urban fitness" -l "Tbilisi" --dry-run
python main.py add "urban fitness" -l "Tbilisi"
python main.py enrich --limit 5 --dry-run
python main.py enrich --fix-locations --show-browser
```

- **Location (column B)** → general area like `Tbilisi, Saburtalo`
- **Verified Location (column E)** → exact street address
- `-l Tbilisi` is only a search hint; district is detected from Maps when possible
- `--fix-locations` rewrites rows that still only say `Tbilisi` in column B

Use `--show-browser` if headless mode gets blocked or stuck on a consent page.

## Notes

- Maps lookup uses Playwright (unofficial; Google may show captchas or change the page layout).
- Keep lookups slow (`enrich` defaults to 2.5s between rows).
- Keep `credentials.json` / `token.json` private (gitignored).
