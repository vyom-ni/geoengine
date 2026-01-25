# Quick Start Guide: Processing Test RE.xlsx

## Installation

1. Make sure you have Python 3.8+ installed
2. Install required dependencies:

```bash
pip install pandas requests beautifulsoup4 openpyxl
```

## Running the Script

### Basic Usage (Process all agents in Test RE.xlsx)

```bash
python process_test_re.py
```

This will:
- Load Test RE.xlsx
- Scrape all URLs for each agent
- Calculate SALT scores (Semantic, Authority, Location, Trust)
- Generate a JSON report: `test_re_results.json`
- Print a summary to console

### Advanced Options

```bash
# Specify custom input/output files
python process_test_re.py --input "My File.xlsx" --output "my_results.json"

# Include detailed breakdowns (factors and score components)
python process_test_re.py --detailed

# Combine options
python process_test_re.py --input "Test RE.xlsx" --output "results.json" --detailed
```

## What Gets Scraped

For each agent, the system will scrape:

1. **Brokerage Website** - Bio, contact info, listings
2. **Zillow Profile** - Reviews, ratings, active listings
3. **Homes.com Profile** - Reviews, ratings
4. **Realtor.com Profile** - Reviews, ratings, sold listings
5. **Google Business** - Reviews, ratings (if URL provided)
6. **LinkedIn** - Profile accessibility
7. **Instagram** - Profile accessibility
8. **Facebook** - Profile accessibility

## Understanding the Results

### Score Ranges

- **90-100**: Exceptional - Elite tier agents with strong web presence
- **75-89**: Strong - Well-established agents with good visibility
- **65-74**: Solid - Developing agents with moderate presence
- **50-64**: Developing - Limited web presence, needs improvement
- **0-49**: Poor - Minimal or no verifiable web presence

### SALT Score Components

#### Semantic (Identity Clarity)
- Do search engines know who this agent is?
- Can AI identify them from their web presence?
- **Key factors**: Name, license, website, social profiles

#### Authority (Cite-worthiness)
- Is there credible content to cite about this agent?
- Do they have reviews and ratings?
- **Key factors**: Review count, rating quality, website quality

#### Location (Market Grounding)
- What markets does this agent serve?
- Are they established locally?
- **Key factors**: Geographic signals, listings, local content

#### Trust (Safety to Recommend)
- Is this agent reputable and verified?
- Safe for AI to recommend?
- **Key factors**: License verification, reviews, brokerage affiliation

## Example Output

```json
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
    "review_sources": {
      "google": {"count": 5, "rating": 4.6},
      "zillow": {"count": 8, "rating": 4.5},
      "realtor": {"count": 2, "rating": 4.3}
    },
    "listings": {
      "active": 3,
      "sold": 12
    }
  }
}
```

## Tips for Better Scores

### To Improve Semantic Scores:
- Ensure all URLs in Excel are complete (include https://)
- Verify website is accessible and has bio/contact info
- Link to at least 3 social platforms

### To Improve Authority Scores:
- Focus on collecting reviews on Google, Zillow, Realtor.com
- Maintain high ratings (4.5+ stars)
- Have an SSL-secured website with active listings

### To Improve Location Scores:
- Include complete address information
- Maintain active listings on public platforms
- Verify brokerage affiliation on website

### To Improve Trust Scores:
- Ensure license number is in the data
- Build consistent reviews across multiple platforms
- Have SSL on website
- Display brokerage affiliation prominently

## Troubleshooting

### "File not found" error
- Make sure Test RE.xlsx is in the same folder as process_test_re.py
- Or use full path: `python process_test_re.py --input "C:\path\to\Test RE.xlsx"`

### Low scores across all agents
- Check that URLs in Excel are complete and valid
- Some websites may block scrapers - this is normal
- Review the `collection_errors` in the JSON output

### Script is slow
- Web scraping takes time (each URL is fetched individually)
- Typical: 5-10 seconds per agent
- For 10 agents: ~1-2 minutes total

### Some URLs not scraped
- Check the `sources_checked` field in results
- Some platforms block automated access - this is expected
- The system continues even if some URLs fail

## Next Steps

After processing:

1. **Review the JSON file** - Contains all detailed data
2. **Check the summary** - Shows average scores and distributions
3. **Identify top performers** - Listed at the end of the summary
4. **Address low scores** - Use the detailed breakdowns to see what's missing

## Support

- See [ENHANCED_SCORING_README.md](ENHANCED_SCORING_README.md) for detailed documentation
- See [SCORING_METHODOLOGY.md](SCORING_METHODOLOGY.md) for scoring formulas
- Check code comments in [agent_intelligence_v2.py](agent_intelligence_v2.py) for implementation details
