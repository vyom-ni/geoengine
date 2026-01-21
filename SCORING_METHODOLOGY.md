# Agent Intelligence Scoring Methodology

## Overview

The Agent Intelligence System uses a **web-verified scoring pipeline** to evaluate real estate agents' AI visibility and discoverability. Unlike traditional scoring systems that rely on self-reported data, our system derives all scores from **verified web signals** collected in real-time.

This document explains how each score is calculated and what factors contribute to an agent's overall rating.

---

## Core Principle: Web-Verified Scoring

```
Excel Data → Identity Only (name, license, URLs)
                    ↓
        Web Scraping & Verification
                    ↓
         Verified Signal Extraction
                    ↓
            Score Computation
```

**Key Rules:**

- Scores are derived **exclusively** from verified web data
- Missing signals **reduce** scores (no assumptions or inflation)
- Same agent + same web presence = same score every time (deterministic)
- Excel/CRM data is used only for identification, never for scoring

---

## The S.A.L.T. Framework

We use the **S.A.L.T.** framework to measure AI visibility across four dimensions:

| Dimension     | What It Measures    | Why It Matters               |
| ------------- | ------------------- | ---------------------------- |
| **S**emantic  | Identity Clarity    | Can AI identify who you are? |
| **A**uthority | Cite-worthiness     | Does AI trust your content?  |
| **L**ocation  | Market Grounding    | Where do you operate?        |
| **T**rust     | Safety to Recommend | Is the agent reputable?      |

Each dimension is scored 0-100, and the **Overall Score** is the average of all four.

---

## Semantic Score (Identity Clarity)

**Question answered:** _Can AI systems clearly identify who this agent is?_

### Scoring Breakdown (100 points max)

| Category              | Max Points | What We Check                               |
| --------------------- | ---------- | ------------------------------------------- |
| Identity Verification | 20         | Full name, license number, jurisdiction     |
| Website Presence      | 30         | Website exists, accessible, has bio/contact |
| Social Consistency    | 30         | Number of social platforms, accessibility   |
| Contact Availability  | 20         | City/state identified, contact on website   |

### Detailed Scoring

**Identity Verification (20 pts)**

- Full name identified: +10 pts
- License number available: +5 pts
- Jurisdiction identified: +5 pts

**Website Presence (30 pts)**

- Website URL exists: +10 pts
- Website is accessible: +10 pts
- Bio content verified on website: +5 pts
- Contact info verified on website: +5 pts

**Social Consistency (30 pts)**

- Each linked social platform: +5 pts (max 20 pts)
- Each verified accessible platform: +3 pts (max 10 pts)

**Contact Availability (20 pts)**

- City and state identified: +10 pts
- Contact information on website: +10 pts

---

## Authority Score (Cite-worthiness)

**Question answered:** _Does AI have credible content to cite about this agent?_

### Scoring Breakdown (100 points max)

| Category              | Max Points | What We Check                                |
| --------------------- | ---------- | -------------------------------------------- |
| Website Quality       | 25         | Exists, accessible, SSL, listings            |
| Review Authority      | 40         | Review count, rating (verified sources)      |
| Professional Presence | 20         | LinkedIn, press mentions                     |
| Verification Signals  | 15         | Brokerage verification, multi-source reviews |

### Detailed Scoring

**Website Quality (25 pts)**

- Website exists: +5 pts
- Website accessible: +5 pts
- SSL certificate (HTTPS): +5 pts
- Active listings on website: +10 pts

**Review Authority (40 pts)** — _Most Important Signal_

| Verified Reviews | Points  |
| ---------------- | ------- |
| 100+ reviews     | +25 pts |
| 50-99 reviews    | +18 pts |
| 20-49 reviews    | +12 pts |
| 5-19 reviews     | +6 pts  |
| 1-4 reviews      | +2 pts  |
| 0 reviews        | 0 pts   |

_Rating Bonus:_
| Average Rating | Points |
|----------------|--------|
| 4.8+ / 5 | +15 pts |
| 4.5-4.7 / 5 | +12 pts |
| 4.0-4.4 / 5 | +8 pts |
| 3.5-3.9 / 5 | +4 pts |

**Professional Presence (20 pts)**

- LinkedIn profile exists: +10 pts
- LinkedIn accessible: +5 pts
- Press mentions: +5 pts

**Verification Signals (15 pts)**

- Brokerage verified on website: +10 pts
- Reviews across 2+ platforms: +5 pts

---

## Location Score (Market Grounding)

**Question answered:** _What markets does this agent serve, and how well established are they locally?_

### Scoring Breakdown (100 points max)

| Category                  | Max Points | What We Check                            |
| ------------------------- | ---------- | ---------------------------------------- |
| Geographic Identification | 30         | City, state, ZIP, coordinates            |
| Local Content Signals     | 40         | Website, brokerage, address verification |
| Listing Activity          | 30         | Active and sold listings verified        |

### Detailed Scoring

**Geographic Identification (30 pts)**

- City identified: +10 pts
- State identified: +8 pts
- ZIP code available: +6 pts
- Coordinates mapped: +6 pts

**Local Content Signals (40 pts)**

- Website accessible (can serve local content): +15 pts
- Brokerage association verified: +10 pts
- Office address verified: +15 pts

**Listing Activity (30 pts)**

| Active Listings | Points  |
| --------------- | ------- |
| 10+ listings    | +15 pts |
| 5-9 listings    | +10 pts |
| 1-4 listings    | +5 pts  |

| Sold Listings | Points  |
| ------------- | ------- |
| 20+ sold      | +15 pts |
| 10-19 sold    | +10 pts |
| 1-9 sold      | +5 pts  |

---

## Trust Score (Safety to Recommend)

**Question answered:** _Is this agent reputable and safe for AI to recommend?_

### Scoring Breakdown (100 points max)

| Category              | Max Points | What We Check                        |
| --------------------- | ---------- | ------------------------------------ |
| License Verification  | 25         | License available, actively verified |
| Reputation Signals    | 40         | Rating + review volume combined      |
| Security/Verification | 20         | SSL, brokerage verification          |
| Contact Verification  | 15         | Phone, address verified              |

### Detailed Scoring

**License Verification (25 pts)**

- License number available: +15 pts
- License actively verified: +10 pts

**Reputation Signals (40 pts)**

_Combined Rating + Volume:_
| Condition | Points |
|-----------|--------|
| 4.8+ rating AND 20+ reviews | +25 pts |
| 4.5+ rating AND 10+ reviews | +20 pts |
| 4.0+ rating AND 5+ reviews | +15 pts |
| 3.5+ rating | +8 pts |
| Has reviews but low rating | +3 pts |

_Review Volume Bonus:_
| Review Count | Points |
|--------------|--------|
| 50+ reviews | +15 pts |
| 20-49 reviews | +10 pts |
| 5-19 reviews | +5 pts |

**Security/Verification (20 pts)**

- SSL-secured website: +10 pts
- Brokerage affiliation verified: +10 pts

**Contact Verification (15 pts)**

- Phone number verified: +8 pts
- Office address verified: +7 pts

---

## Overall Score & Grades

### Overall Score Calculation

```
Overall Score = (Semantic + Authority + Location + Trust) / 4
```

### Letter Grades

| Score Range | Grade |
| ----------- | ----- |
| 97-100      | A+    |
| 93-96       | A     |
| 90-92       | A-    |
| 87-89       | B+    |
| 83-86       | B     |
| 80-82       | B-    |
| 77-79       | C+    |
| 73-76       | C     |
| 70-72       | C-    |
| 60-69       | D     |
| 0-59        | F     |

### Tier Classification

| Score Range | Tier        |
| ----------- | ----------- |
| 95-100      | Elite       |
| 85-94       | Exceptional |
| 75-84       | Strong      |
| 65-74       | Solid       |
| 0-64        | Developing  |

---

## LLM Visibility Scores

We also calculate how visible an agent is to specific AI systems, as each has different preferences:

### ChatGPT (OpenAI)

- **Weights:** Semantic 30%, Authority 25%, Trust 30%, Location 15%
- **Bonus factors:** Review volume, rating quality
- **Preference:** Structured data, clear identity, strong reviews

### Perplexity

- **Weights:** Authority 35%, Location 25%, Semantic 25%, Trust 15%
- **Bonus factors:** Website presence, social platforms
- **Preference:** Web citations, diverse content sources

### Claude (Anthropic)

- **Weights:** Trust 35%, Semantic 30%, Authority 20%, Location 15%
- **Bonus factors:** License verification, rating quality
- **Preference:** Trust signals, verified information

### Gemini (Google)

- **Weights:** Location 35%, Authority 30%, Semantic 20%, Trust 15%
- **Bonus factors:** Review volume, website presence
- **Preference:** Local SEO, Google ecosystem signals

---

## Data Sources

All scores are derived from verified web signals. We check:

| Source          | Signals Extracted                                    |
| --------------- | ---------------------------------------------------- |
| Agent Website   | Accessibility, SSL, content (listings, bio, contact) |
| Google Business | Reviews, ratings, business verification              |
| Zillow          | Reviews, ratings, listing activity                   |
| Realtor.com     | Reviews, ratings, listing activity                   |
| LinkedIn        | Profile existence, accessibility                     |
| Instagram       | Profile existence, accessibility                     |
| Facebook        | Profile existence, accessibility                     |
| Twitter/X       | Profile existence, accessibility                     |

---

## Determinism & Consistency

Our scoring system is **deterministic**:

- ✅ Same agent + same web data = same score every run
- ✅ No randomness in calculations
- ✅ Fixed formulas, no AI-generated scores
- ✅ LLM temperature set to 0 for consistent insights

**What AI is used for (and not used for):**

- ✅ AI interprets scraped content
- ✅ AI generates recommendations
- ❌ AI does NOT generate or modify scores
- ❌ AI does NOT invent or infer data

---

## Improving Scores

### Quick Wins (Immediate Impact)

1. Claim and verify Google Business profile
2. Ensure website is accessible with SSL
3. Add contact information to website
4. Link all social profiles consistently

### High Priority (1-3 Months)

1. Implement systematic review collection
2. Ensure reviews appear on Google, Zillow, and Realtor.com
3. Add active listings to personal website
4. Get LinkedIn recommendations from clients

### Medium Priority (3-6 Months)

1. Publish local market content
2. Build press/media mentions
3. Create video content (property tours)
4. Expand to all major social platforms

---

## Contact

For questions about this scoring methodology or to request a detailed agent analysis, please contact the GeoEngine team.

---

_Document Version: 2.0_  
_Last Updated: January 2026_  
_Scoring Engine: Web-Verified Pipeline v2_
