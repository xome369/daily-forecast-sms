# Daily Forecast

A Python script that fetches a 24-hour weather forecast for a configured city and delivers a concise SMS summary via Twilio. Runs automatically every day via GitHub Actions.

## Features

- Fetches 24-hour forecast in 3-hour steps from OpenWeatherMap
- Collapses repeated conditions — only logs a new step when conditions or temperature change meaningfully
- Displays human-readable condition descriptions (e.g. "Broken clouds" instead of "Clouds")
- Shows daily high and low temperatures
- Appends a severity-prioritised alert for adverse weather conditions
- Splits long messages into segments to stay within SMS character limits
- Runs on a daily schedule via GitHub Actions

## Requirements

- Python 3.11+
- OpenWeatherMap API key (free tier sufficient)
- Twilio account with a toll-free number and Messaging Service SID

## Local Setup

1. Clone the repository
2. Create a virtual environment and install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root with the following variables:
   ```
   OPEN_WEATHER_MAP_API_KEY=your_key
   TWILIO_ACCOUNT_SID=your_sid
   TWILIO_AUTH_TOKEN=your_token
   TWILIO_MESSAGING_SERVICE_SID=your_messaging_service_sid
   RECIPIENT_NUMBER=+1234567890
   CITY=Fort Lauderdale
   ```
4. Run the script:
   ```
   python main.py
   ```

## GitHub Actions Deployment

All `.env` variables must be added as repository secrets before the workflow will run successfully.

1. Go to your repository on GitHub
2. Navigate to Settings → Secrets and variables → Actions
3. Add each variable from the `.env` file as a new repository secret
4. The workflow runs automatically at 12:00 UTC daily (7:00 AM EST)
5. To trigger manually, go to Actions → Daily Forecast → Run workflow

## Project Structure

```
├── main.py                              # Main script
├── requirements.txt                     # Python dependencies
├── .env                                 # Local secrets (never commit this)
├── .gitignore
└── .github/
    └── workflows/
        └── daily_forecast.yml           # GitHub Actions workflow
```

## Configuration

| Constant | Location | Description |
|---|---|---|
| `TEMP_CHANGE_THRESHOLD` | `main.py` | Minimum °C shift to log a new forecast step (default: 3) |
| `ALERT_CONDITIONS` | `main.py` | Dict of condition names and their alert messages |
| `ALERT_PRIORITY` | `main.py` | Ordered list defining alert severity precedence |
| `cron` | `daily_forecast.yml` | Schedule for the workflow (default: 12:00 UTC) |
