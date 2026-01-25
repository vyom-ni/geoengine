# Fix Summary: SALT Scores Now Display Correctly in Frontend

## Issue Identified
The SALT scores were not displaying properly in the frontend because the API was returning very low scores (Overall: 6/100 instead of expected 44-55/100).

## Root Cause
The enhanced web scraping system added support for marketplace URLs (Zillow, Homes.com, Realtor.com, Google Business), but these URLs were not being passed from the `AgentProfile` to the `AgentSeed` during the web scraping process.

**Result**: Only 3 sources were being scraped instead of 8, causing artificially low scores.

## Changes Made

### 1. Updated `AgentProfile` dataclass
**File**: `agent_intelligence_v2.py` (line ~1233)

Added marketplace URL fields:
```python
# Marketplace URLs (for web scraping)
zillow_url: str = ""; homes_url: str = ""; realtor_url: str = ""; google_business_url: str = ""
```

### 2. Updated `record_to_profile` method
**File**: `agent_intelligence_v2.py` (line ~2075)

Added extraction of marketplace URLs from database with fallback column names:
```python
# Marketplace URLs for enhanced scraping
zillow_url=g_str('Zillow ', '') or g_str('Zillow', ''),
homes_url=g_str('Homes', ''),
realtor_url=g_str('Realtor', ''),
google_business_url=g_str('Google business profile', ''),
```

Also added fallbacks for social URLs to handle Test RE.xlsx column names:
```python
instagram_url=g_str('Instagram_URL', '') or g_str('Instagram', ''),
facebook_url=g_str('Facebook_URL', '') or g_str('Facebook', ''),
linkedin_url=g_str('LinkedIn_URL', '') or g_str('Linkedin', ''),
```

### 3. Updated `_profile_to_seed` method
**File**: `agent_intelligence_v2.py` (line ~1376)

Modified to extract and pass marketplace URLs to AgentSeed:
```python
# Extract marketplace URLs from profile if available
zillow_url = getattr(profile, 'zillow_url', '')
homes_url = getattr(profile, 'homes_url', '')
realtor_url = getattr(profile, 'realtor_url', '')
google_business_url = getattr(profile, 'google_business_url', '')

return AgentSeed(
    # ... other fields ...
    zillow_url=zillow_url,
    homes_url=homes_url,
    realtor_url=realtor_url,
    google_business_url=google_business_url,
    # ... other fields ...
)
```

## Results

### Before Fix:
```
Sources checked: 3
SALT Scores: S:10 A:0 L:16 T:0 Overall:6
```

### After Fix:
```
Sources checked: 8
SALT Scores: S:71 A:45 L:41 T:20 Overall:44
```

**Score Improvements**:
- Semantic: 10 → 71 (+610%)
- Authority: 0 → 45 (from nothing to measurable)
- Location: 16 → 41 (+156%)
- Trust: 0 → 20 (from nothing to measurable)
- Overall: 6 → 44 (+633%)

## API Response Structure

The vieweo.py API now correctly returns:

```json
{
  "salt_scores": {
    "semantic": 71,
    "authority": 45,
    "location": 41,
    "trust": 20
  },
  "visibility_score": 44,
  "visibility_grade": "F",
  "visibility_tier": "Developing"
}
```

**Note**: `salt_scores` is only included when user is logged in. For non-logged-in users, it returns `null`.

## Frontend Display

The frontend will now display:
- ✅ Overall visibility score (shown to everyone)
- ✅ SALT score breakdown (shown only when logged in)
- ✅ Score bars with proper percentages
- ✅ LLM visibility scores
- ✅ Ranking information

## How to Test

### 1. Restart vieweo.py:
```bash
python vieweo.py
```

### 2. Access the frontend:
- Open: http://localhost:8080
- Search for an agent (e.g., "Bailey Jenkins")
- Login with admin credentials:
  - Email: admin@vieweo.com
  - Name: Admin (any name)

### 3. Verify scores display:
- Check overall score circle shows ~44/100
- Check SALT breakdown shows all 4 scores
- Check score bars animate to correct percentages

## Test Results Confirmation

Ran test script `test_vieweo_scores.py`:
```
SUCCESS: Scores are being calculated properly!
Semantic:  71/100
Authority: 45/100
Location:  41/100
Trust:     20/100
Overall:   44/100
```

## Notes

1. **Scores are still developing** because:
   - No verified reviews found (Authority: 45/100)
   - Limited trust signals (Trust: 20/100)
   - State column missing from database (affects Location scoring)

2. **To improve scores further**:
   - Add State column to Test RE.xlsx
   - Ensure agents have reviews on Google/Zillow/Realtor.com
   - Verify all URLs are accessible (check collection_errors in output)

3. **Caching**: The system caches results for 5 minutes. If you make changes to the database, wait 5 minutes or restart vieweo.py.

## Files Modified

1. `agent_intelligence_v2.py` - 3 functions updated
2. `test_vieweo_scores.py` - Created for testing

## Status: ✅ FIXED

The SALT scores now display correctly in the frontend with proper values based on comprehensive web scraping of all available URLs.
