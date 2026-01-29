# Google Places API Setup Guide

## Overview

The system now uses **Google Places API** as the primary method for extracting Google Business reviews. This is much more reliable than web scraping and avoids CAPTCHA issues.

## Why Google Places API?

- ✅ **Reliable**: Official API with guaranteed data access
- ✅ **No CAPTCHA**: No bot detection or blocking
- ✅ **Accurate**: Direct access to review counts and ratings
- ✅ **Fast**: Much faster than web scraping
- ✅ **Review Content**: Access to actual review text for sentiment analysis

## Setup Instructions

### Step 1: Get Google Places API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services > Credentials**
4. Click **+ CREATE CREDENTIALS > API Key**
5. Copy the generated API key

### Step 2: Enable Required APIs

In the Google Cloud Console, enable these APIs:

1. **Places API** (required)
2. **Maps JavaScript API** (if not already enabled)

To enable:
- Go to **APIs & Services > Library**
- Search for "Places API"
- Click on it and press **ENABLE**

### Step 3: Configure API Key in .env File

Add your API key to the `.env` file in the project root:

```
GOOGLE_PLACES_API_KEY=your_api_key_here
```

### Step 4: Test the Integration

Run the test script to verify everything works:

```bash
python test_google_places_api.py
```

You should see output like:

```
✓ API key found: AIzaSyB...xyz
✓ Google Places API initialized

Testing agent: Jay Kilby
Location: Durham, NC

Collecting Web Signals...
      Google Places API search: Jay Kilby real estate agent Durham NC
      ✓ Google Places API rating: 5.0
      ✓ Google Places API reviews: 116
      ✓ Google data retrieved via Places API

RESULTS
========
Google Reviews:
   Rating: 5.0/5.0
   Review Count: 116
```

## How It Works

### 1. Primary Method: Google Places API

The system first tries to get Google reviews using the Places API:

```python
def _check_google_with_places_api(self, seed: AgentSeed, signals: WebSignals) -> bool:
    # 1. Search for the agent using their name + location
    # 2. Get the place_id from search results
    # 3. Fetch detailed place information including reviews
    # 4. Extract rating, review count, and sentiment
```

### 2. Fallback: Web Scraping

If the API is not available or fails, the system falls back to web scraping:
- BeautifulSoup parsing
- JSON-LD structured data extraction
- Regex patterns for review extraction

### 3. Integration Points

The API integration is in `agent_intelligence_v2.py`:

- **Line 59-66**: Import googlemaps and load .env
- **Line 361-372**: Initialize Google Places API client in WebSignalLayer.__init__()
- **Line 981-1046**: New method `_check_google_with_places_api()`
- **Line 1055-1060**: Updated `_check_google_business()` to use API first

## API Usage and Costs

### Free Tier

Google provides **$200 free credit per month**, which includes:

- **Places API - Text Search**: $32 per 1000 requests
- **Places API - Place Details**: $17 per 1000 requests

### Cost Calculation

For each agent, we make:
- 1 Text Search request (~$0.032)
- 1 Place Details request (~$0.017)
- **Total: ~$0.049 per agent**

With $200 free credit:
- **~4,000 agents per month for FREE**

## Testing with Multiple Agents

The system has been tested with these 6 agents (from `google_review_urls.json`):

1. **Jay Kilby** - Durham, NC
2. **Bailey Jenkins** - Durham, NC
3. **Sean Gold** - Durham, NC
4. **Martin Rodriguez** - Durham, NC (116 Google reviews)
5. **Scott Avis** - Durham, NC
6. **Jenny Maraghey** - Durham, NC

To test with these agents, you can modify the test script to loop through all 6.

## Troubleshooting

### Error: "GOOGLE_PLACES_API_KEY not found in .env file"

**Solution**: Add the API key to `.env` file as shown in Step 3.

### Error: "This API project is not authorized to use this API"

**Solution**: Enable the Places API in Google Cloud Console (see Step 2).

### Error: "Google Places API error: REQUEST_DENIED"

**Solution**:
1. Check that billing is enabled for your Google Cloud project
2. Verify the API key is correct
3. Ensure Places API is enabled

### Reviews showing 0 despite API being configured

**Possible causes**:
1. The agent doesn't have a Google Business Profile
2. The search query doesn't match any business
3. The business is not classified as a real estate agency

**Solution**: Check the logs for the actual API response, and adjust the search query if needed.

## API Response Example

Successful API response structure:

```json
{
  "status": "OK",
  "results": [{
    "place_id": "ChIJxxxxx",
    "name": "Jay Kilby - Real Estate Agent",
    "rating": 5.0,
    "user_ratings_total": 116,
    "reviews": [
      {
        "text": "Jay was very helpful and responsive...",
        "rating": 5,
        "author_name": "John Doe"
      }
    ]
  }]
}
```

## Next Steps

Once the API key is configured:

1. ✅ Run `test_google_places_api.py` to verify it works
2. ✅ Run the full analysis on your database:
   ```bash
   python agent_intelligence_v2.py analyze --name "Agent Name" --db database.xlsx
   ```
3. ✅ Check the final reports to see accurate Google review data

## Support

If you encounter any issues:

1. Check the `.env` file has the correct API key
2. Verify APIs are enabled in Google Cloud Console
3. Check the console output for detailed error messages
4. Review the `google_review_urls.json` file for agent mappings
