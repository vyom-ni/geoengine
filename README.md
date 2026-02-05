# Vieweo - AI Visibility Platform for Real Estate Agents

## Quick Start

1. Create a `.env` file and add your Gemini API key:

   ```
   GEMINI_API_KEY=YOUR_API_KEY
   ```

2. Create and activate virtual environment

3. Install all required packages:

   ```bash
   pip install -r requirements.txt
   ```

4. Run the app:

   ```bash
   py vieweo.py
   ```

5. Login credentials:
   - Email: `admin@gmail.com`
   - Name: `Admin`

---

## Agent Scoring Logic Overview

### Architecture: 3-Layer Pipeline

The scoring system uses a **web-verified pipeline** with three distinct layers:

```
Excel Data → (1) INPUT SEED → (2) WEB SIGNALS → (3) SCORING
              Identity only    Fetch live data   Compute scores
```

---

### Layer 1: Input Seed Layer

- Extracts **identity only** from Excel (name, license, URLs)
- **NO scoring derived** from Excel fields
- Used purely to seed URL discovery for web scraping

---

### Layer 2: Web Signal Layer

- **Source of truth** - actively scrapes live web data
- Collects verified signals from:
  - Agent websites (accessibility, SSL, bio, contact, listings)
  - Marketplaces (Zillow, Realtor.com, Homes.com → reviews, ratings)
  - Google Business (reviews, ratings)
  - Social platforms (LinkedIn, Instagram, Facebook, Twitter)
- Missing signals → **reduces scores** (no inflation from assumptions)

---

### Layer 3: Scoring Layer - S.A.L.T. Framework

Each dimension scores 0-100 based on **web signals only**:

| Score         | Measures            | Key Factors                                                                      |
| ------------- | ------------------- | -------------------------------------------------------------------------------- |
| **S**emantic  | Identity Clarity    | Name/license (20pts), Website (30pts), Social (30pts), Contact (20pts)           |
| **A**uthority | Cite-worthiness     | Website quality (25pts), Reviews (40pts), LinkedIn (20pts), Verification (15pts) |
| **L**ocation  | Market Grounding    | Geography (30pts), Local content (40pts), Listings (30pts)                       |
| **T**rust     | Safety to Recommend | License (25pts), Reputation (40pts), Security (20pts), Contact (15pts)           |

**Overall Score** = Average of S + A + L + T

---

### Consistency Mechanisms

1. **Deterministic**: `LLM_TEMPERATURE = 0` ensures same prompts → same outputs
2. **Web-only scoring**: Excel data cannot inflate scores
3. **Liberal base credits**: Agents get base points for being in the database (avoids zero scores)
4. **Tiered review thresholds**: Reviews scored in buckets (50+, 20+, 10+, 5+, etc.)
5. **Weighted rating average**: Multiple platforms' ratings weighted by review count
6. **Capped at 100**: All sub-scores capped to prevent overflow

The design ensures that **same web presence = same score every time**, making rankings reproducible and fair.
