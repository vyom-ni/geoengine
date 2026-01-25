# Enhanced SALT and GEO Scoring System

## Overview

This enhanced version of the Agent Intelligence system provides **consistent and comprehensive SALT (Semantic, Authority, Location, Trust) and GEO scoring** by scraping ALL available URLs from your data source.

## What's New

### 1. **Multi-Platform URL Support**
The system now extracts and scrapes data from ALL platforms in your Excel file:
- ✅ Brokerage websites
- ✅ Zillow profiles  
- ✅ Homes.com profiles
- ✅ Realtor.com profiles
- ✅ Google Business profiles
- ✅ LinkedIn
- ✅ Instagram
- ✅ Facebook
- ✅ Twitter/X

### 2. **Improved Data Extraction**
Enhanced scraping with multiple patterns for each platform:
- **Reviews**: Multiple regex patterns to catch different formats
- **Ratings**: Extracts ratings from various HTML structures
- **Listings**: Tracks both active and sold listings
- **Social presence**: Verifies accessibility of all social profiles

### 3. **Consistent Scoring Logic**
All scores are calculated using **verified web signals only**:

#### SALT Framework:
- **S (Semantic)**: Identity clarity - name, license, website, social consistency
- **A (Authority)**: Cite-worthiness - reviews, ratings, press mentions
- **L (Location)**: Market grounding - geographic signals, local content, listings
- **T (Trust)**: Safety to recommend - license verification, reputation, security

#### Score Consistency:
- ✅ Same agent + same web data = **same score every time** (deterministic)
- ✅ No randomness in calculations
- ✅ Missing signals = lower scores (no assumptions)
- ✅ All formulas documented in `SCORING_METHODOLOGY.md`

### 4. **Comprehensive Reporting**
The new processing script provides:
- Detailed SALT scores for each agent
- Score breakdowns with contributing factors
- LLM visibility scores (ChatGPT, Perplexity, Claude, Gemini)
- Summary statistics and tier distributions
- Top performers ranking

## Usage

### Processing Test RE.xlsx

```bash
# Basic processing
python process_test_re.py

# Specify custom input/output files
python process_test_re.py --input "Test RE.xlsx" --output "results.json"

# Include detailed breakdowns
python process_test_re.py --detailed
```

### Output Format

The script generates a JSON file with:
```json
{
  "metadata": {
    "source_file": "Test RE.xlsx",
    "total_agents": 10,
    "processed_at": "2026-01-25T...",
    "version": "Enhanced SALT Scoring v2.0"
  },
  "summary": {
    "total_agents": 10,
    "statistics": {
      "semantic": {"average": 65.2, "min": 40, "max": 85},
      "authority": {"average": 58.5, "min": 30, "max": 90},
      "location": {"average": 62.3, "min": 45, "max": 80},
      "trust": {"average": 55.8, "min": 35, "max": 85},
      "overall": {"average": 60.5, "min": 42, "max": 82}
    },
    "tier_distribution": {
      "Elite": 0,
      "Exceptional": 2,
      "Strong": 5,
      "Solid": 2,
      "Developing": 1
    }
  },
  "agents": [
    {
      "agent": {
        "name": "Bailey Jenkins",
        "id": "VA225254825",
        "city": "Roanoke",
        "state": "VA"
      },
      "scores": {
        "semantic": {"score": 75, "grade": "C"},
        "authority": {"score": 62, "grade": "D"},
        "location": {"score": 68, "grade": "D"},
        "trust": {"score": 58, "grade": "F"},
        "overall": {"score": 66, "grade": "D", "tier": "Solid"}
      },
      "web_signals": {
        "total_reviews": 15,
        "average_rating": 4.5,
        "website_accessible": true,
        "review_sources": {
          "google": {"count": 5, "rating": 4.6},
          "zillow": {"count": 8, "rating": 4.5},
          "realtor": {"count": 2, "rating": 4.3}
        }
      }
    }
  ]
}
```

## Data Source Requirements

Your Excel file should have these columns (the system will auto-detect):

### Required:
- **Name**: `Realtor Name`, `Agent Name`, or `Full_Name`
- **ID**: `Realtor ID`, `Agent_ID`, or `ID`
- **Location**: `Office (Source Google Business Profile)` or `City` + `State`

### Optional URLs (more = better scoring):
- `Brokerage` or `Personal website`
- `Zillow ` or `Zillow`
- `Homes`
- `Realtor`
- `Google business profile`
- `Linkedin` or `LinkedIn`
- `Instagram`
- `Facebook`
- `Twitter`

## Scoring Methodology

### Semantic Score (0-100)
- **Identity Verification** (20 pts): Full name, license, jurisdiction
- **Website Presence** (30 pts): Accessibility, bio, contact info
- **Social Consistency** (30 pts): Number and accessibility of platforms
- **Contact Availability** (20 pts): City/state, website contact

### Authority Score (0-100)
- **Website Quality** (25 pts): Exists, accessible, SSL, listings
- **Review Authority** (40 pts): Review count + rating quality
- **Professional Presence** (20 pts): LinkedIn, press mentions
- **Verification** (15 pts): Brokerage verified, multi-platform reviews

### Location Score (GEO) (0-100)
- **Geographic Identification** (30 pts): City, state, ZIP, coordinates
- **Local Content** (40 pts): Website, brokerage, office address
- **Listing Activity** (30 pts): Active and sold listings

### Trust Score (0-100)
- **License Verification** (25 pts): License available and verified
- **Reputation Signals** (40 pts): Rating + review volume combined
- **Security** (20 pts): SSL, brokerage verification
- **Contact Verification** (15 pts): Phone and address verified

## Key Improvements for Consistency

1. **Deterministic Scraping**: Same URL scraped multiple times = same result
2. **Fallback Patterns**: Multiple regex patterns ensure data capture
3. **Aggregated Reviews**: Combines reviews from all sources (Google, Zillow, Realtor.com, Homes.com)
4. **Normalized Ratings**: Weighted average across all review sources
5. **Missing Data Handling**: Missing signals reduce scores predictably
6. **No Excel Scoring**: ALL scores derived from live web data, not Excel fields

## Troubleshooting

### Low Scores?
- **Check URLs**: Make sure all URLs in Excel are complete and accessible
- **Review Data**: Agents need reviews on Google, Zillow, or Realtor.com for high Authority scores
- **Website Required**: Agents without accessible websites will have lower Semantic scores
- **License Info**: Missing license reduces Trust score significantly

### Scraping Errors?
- **Timeout**: Some sites may be slow - increase timeout in `WebSignalLayer(timeout=15)`
- **Blocked**: Some platforms block scrapers - errors are logged but don't stop processing
- **Rate Limiting**: Process large batches slowly to avoid IP blocks

### Inconsistent Scores?
- The system is deterministic - same input ALWAYS produces same output
- If scores vary, the underlying web data changed between runs
- Check timestamps in results to compare when data was collected

## Example Run

```bash
$ python process_test_re.py

📂 Loaded 10 agents from Test RE.xlsx

================================================================================
PROCESSING 10 AGENTS
================================================================================

────────────────────────────────────────────────────────────────────────────────
[1/10] Processing Agent...
────────────────────────────────────────────────────────────────────────────────
   Agent: Bailey Jenkins
   ID: VA225254825
   Location: Roanoke, VA
   URLs to scrape: 8
     • Website: https://roanoke.nestrealty.com/agent/bailey-jenkins...
     • Zillow: https://www.zillow.com/profile/bailey%20jenkins0...
     • Homes.com: https://www.homes.com/real-estate-agents/bailey-jenkins...
     • Realtor.com: https://www.realtor.com/realestateagents/61ce...
     • Google Business: https://share.google/XWchlDieofStvFIyz...
     • LinkedIn: linkedin.com/in/baileyjenkins/?skipRedirect=true...
     • Instagram: https://www.instagram.com/bailey.jenkinsre/...
     • Facebook: https://www.facebook.com/baileyjenkinsrealtor/...

   🌐 Scraping web sources...
   ✓ Checked 8 sources
   📊 Calculating SALT scores...

✅ Bailey Jenkins
   Location: Roanoke, VA
   SALT Scores:
     • Semantic:  75/100 (C)
     • Authority: 62/100 (D)
     • Location:  68/100 (D)
     • Trust:     58/100 (F)
   Overall: 66/100 (D) - Solid

... (9 more agents)

================================================================================
SUMMARY REPORT
================================================================================

Total Agents Processed: 10

Average Scores:
  • Semantic:  65.2/100
  • Authority: 58.5/100
  • Location:  62.3/100
  • Trust:     55.8/100
  • Overall:   60.5/100

Tier Distribution:
  • Elite: 0 agents
  • Exceptional: 2 agents
  • Strong: 5 agents
  • Solid: 2 agents
  • Developing: 1 agents

Top 5 Performers:
  1. Agent A: 82/100 (Exceptional)
  2. Agent B: 78/100 (Strong)
  3. Agent C: 75/100 (Strong)
  4. Agent D: 72/100 (Strong)
  5. Agent E: 68/100 (Solid)

================================================================================
✅ Processing complete! Results saved to: test_re_results.json
================================================================================
```

## Technical Details

### Architecture
```
Excel Data → AgentSeed (identity only)
              ↓
    WebSignalLayer (scrape all URLs)
              ↓
    WebSignals (verified web data)
              ↓
    SignalExtractor (normalize signals)
              ↓
    ScoringLayer (calculate SALT scores)
              ↓
    Results (deterministic scores)
```

### Dependencies
- `pandas`: Excel file reading
- `requests`: HTTP requests for web scraping
- `beautifulsoup4`: HTML parsing (optional, uses regex fallback)
- `openpyxl`: Excel file support

Install all:
```bash
pip install pandas requests beautifulsoup4 openpyxl
```

## Support

For questions about:
- **Scoring methodology**: See `SCORING_METHODOLOGY.md`
- **Implementation**: See code comments in `agent_intelligence_v2.py`
- **Results interpretation**: See output JSON structure above

## Version History

- **v2.0** (2026-01-25): Enhanced multi-platform scraping, consistent SALT/GEO scoring
- **v1.0**: Original implementation with basic scoring
