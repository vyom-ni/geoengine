"""
Real Estate Agent Intelligence System v2 - ENHANCED
Powered by Google Gemini / OpenAI + RAG with detailed executive summaries and leaderboard rankings
"""

import pandas as pd
import json
import os
import argparse
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import random

# Try to import AI libraries
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Extended ZIP coordinates for better map coverage
ZIP_COORDS = {
    "331": (25.76, -80.19), "332": (26.12, -80.14), "333": (26.72, -80.05), "334": (27.95, -82.46),
    "335": (28.54, -81.38), "336": (30.33, -81.66), "900": (34.05, -118.24), "901": (34.05, -118.24),
    "902": (34.07, -118.40), "910": (34.18, -118.31), "920": (32.72, -117.16), "921": (32.72, -117.16),
    "940": (37.77, -122.42), "941": (37.77, -122.42), "950": (37.34, -121.89), "750": (32.78, -96.80),
    "751": (32.78, -96.80), "752": (32.78, -96.80), "760": (32.76, -97.33), "770": (29.76, -95.37),
    "771": (29.76, -95.37), "772": (29.76, -95.37), "780": (29.42, -98.49), "782": (30.27, -97.74),
    "100": (40.71, -74.01), "101": (40.71, -74.01), "102": (40.71, -74.01), "110": (40.73, -73.79),
    "111": (40.73, -73.84), "112": (40.69, -73.94), "600": (41.88, -87.63), "601": (41.88, -87.63),
    "606": (41.88, -87.63), "850": (33.45, -112.07), "852": (33.45, -112.07), "300": (33.75, -84.39),
    "303": (33.75, -84.39), "021": (42.36, -71.06), "022": (42.36, -71.06), "980": (47.61, -122.33),
    "981": (47.61, -122.33), "800": (39.74, -104.99), "802": (39.74, -104.99), "890": (36.17, -115.14),
    "891": (36.17, -115.14), "970": (45.52, -122.68), "370": (36.16, -86.78), "372": (36.16, -86.78),
    "190": (39.95, -75.17), "191": (39.95, -75.17), "480": (42.33, -83.05), "270": (35.78, -78.64),
    "280": (35.23, -80.84), "630": (38.63, -90.20), "640": (39.10, -94.58), "070": (40.74, -74.17),
    "071": (40.74, -74.17), "220": (38.91, -77.04), "430": (39.96, -83.00), "440": (41.50, -81.69),
    "550": (44.98, -93.27), "460": (39.77, -86.16),
}

def get_coordinates_from_zip(zip_code: str) -> Tuple[float, float]:
    if not zip_code or str(zip_code).strip() in ('', 'nan'):
        return (39.83, -98.58)
    zip_str = str(zip_code).strip()[:3]
    if zip_str in ZIP_COORDS:
        return ZIP_COORDS[zip_str]
    region = {'0': (42.36, -71.06), '1': (40.71, -74.01), '2': (38.91, -77.04), '3': (33.75, -84.39),
              '4': (41.88, -87.63), '5': (44.98, -93.27), '6': (39.10, -94.58), '7': (32.78, -96.80),
              '8': (39.74, -104.99), '9': (34.05, -118.24)}
    return region.get(zip_str[0] if zip_str else '5', (39.83, -98.58))


@dataclass
class AgentProfile:
    agent_id: str; full_name: str; license_number: str; license_status: str; jurisdiction: str
    city: str; state: str; zip_code: str; office_address: str
    latitude: float = 0.0; longitude: float = 0.0
    brokerage_name: str = ""; profile_url: str = ""; website: str = ""
    instagram_url: str = ""; facebook_url: str = ""; twitter_url: str = ""; linkedin_url: str = ""
    average_rating: float = 0.0; total_reviews: int = 0; review_text: str = ""; review_platform: str = ""
    bio_text: str = ""; phone_number: str = ""; profile_image_url: str = ""
    years_experience: int = 0; specialization: str = ""; career_sales: str = ""
    industry_ranking: str = ""; credibility_score: int = 0; credibility_tier: str = ""
    verified_realtrends: str = ""; follower_count: int = 0; verification_badge: str = ""
    media_mentions_count: int = 0; sample_listing_url: str = ""; team_name: str = ""
    observation_timestamp: str = ""; web_enrichment: Dict = field(default_factory=dict)


class AIAnalyzer:
    """Unified AI Analyzer supporting OpenAI and Gemini"""
    
    def __init__(self, openai_api_key: Optional[str] = None, gemini_api_key: Optional[str] = None):
        self.openai_client = None
        self.gemini_model = None
        self.active_llm = None
        
        # Prefer OpenAI if available
        if openai_api_key and OPENAI_AVAILABLE:
            try:
                self.openai_client = openai.OpenAI(api_key=openai_api_key)
                self.active_llm = 'openai'
                print("✅ OpenAI client initialized")
            except Exception as e:
                print(f"⚠️ OpenAI init failed: {e}")
        
        # Fallback to Gemini
        if not self.openai_client and gemini_api_key and GEMINI_AVAILABLE:
            try:
                genai.configure(api_key=gemini_api_key)  # type: ignore
                self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')  # type: ignore
                self.active_llm = 'gemini'
                print("✅ Gemini client initialized")
            except Exception as e:
                print(f"⚠️ Gemini init failed: {e}")
        
        if not self.active_llm:
            print("⚠️ No LLM available - using algorithmic scoring only")
    
    def analyze_agent(self, profile: AgentProfile, leaderboard: Optional[Dict] = None) -> Dict:
        """
        Main analysis method - ALWAYS uses algorithmic SALT scores for consistency,
        then enhances with LLM insights if available.
        """
        # ALWAYS calculate SALT scores algorithmically (reliable & consistent)
        salt_analysis = self._calculate_salt_scores(profile, leaderboard)
        
        # Calculate LLM-specific visibility scores
        llm_scores = self._calculate_llm_visibility_scores(profile, salt_analysis)
        salt_analysis['llm_visibility_scores'] = llm_scores
        
        # Optionally enhance with LLM insights (recommendations, summaries)
        if self.active_llm:
            try:
                llm_insights = self._get_llm_insights(profile, salt_analysis, leaderboard)
                # Merge LLM insights but DON'T override SALT scores
                if llm_insights:
                    # Only take non-score insights from LLM
                    for key in ['recommendations', 'profile_analysis', 'competitive_insights']:
                        if key in llm_insights and llm_insights[key]:
                            salt_analysis[key] = llm_insights[key]
            except Exception as e:
                print(f"⚠️ LLM enhancement failed (using base analysis): {e}")
        
        return salt_analysis
    
    def _calculate_llm_visibility_scores(self, p: AgentProfile, analysis: Dict) -> Dict:
        """
        Calculate visibility scores for different LLMs based on their known preferences.
        Each LLM has different weights for various factors.
        """
        scores = analysis.get('scores', {})
        semantic = scores.get('semantic', {}).get('score', 0)
        authority = scores.get('authority', {}).get('score', 0)
        location = scores.get('location', {}).get('score', 0)
        trust = scores.get('trust', {}).get('score', 0)
        
        # Count digital presence factors
        platforms = sum([1 for x in [p.instagram_url, p.facebook_url, p.twitter_url, p.linkedin_url] if x])
        has_website = 1 if p.website else 0
        review_factor = min(p.total_reviews / 100, 1.0)  # Normalize to 0-1
        rating_factor = (p.average_rating - 3) / 2 if p.average_rating >= 3 else 0  # 3-5 -> 0-1
        
        # ChatGPT (OpenAI) - Values structured data, reviews, clear identity
        # Weights: Semantic 30%, Authority 25%, Trust 30%, Location 15%
        chatgpt_score = int(
            semantic * 0.30 + 
            authority * 0.25 + 
            trust * 0.30 + 
            location * 0.15 +
            (review_factor * 5) +  # Bonus for reviews
            (rating_factor * 5)     # Bonus for high ratings
        )
        
        # Perplexity - Values web presence, citations, recent content
        # Weights: Authority 35%, Location 25%, Semantic 25%, Trust 15%
        perplexity_score = int(
            authority * 0.35 + 
            location * 0.25 + 
            semantic * 0.25 + 
            trust * 0.15 +
            (has_website * 8) +     # Strong bonus for website
            (platforms * 2)          # Bonus for each platform
        )
        
        # Claude (Anthropic) - Values trust signals, verified info, ethical presentation
        # Weights: Trust 35%, Semantic 30%, Authority 20%, Location 15%
        claude_score = int(
            trust * 0.35 + 
            semantic * 0.30 + 
            authority * 0.20 + 
            location * 0.15 +
            (10 if p.license_status == 'Active' else 0) +  # Verified license bonus
            (rating_factor * 5)
        )
        
        # Gemini (Google) - Values Google ecosystem, local SEO, structured data
        # Weights: Location 35%, Authority 30%, Semantic 20%, Trust 15%
        gemini_score = int(
            location * 0.35 + 
            authority * 0.30 + 
            semantic * 0.20 + 
            trust * 0.15 +
            (review_factor * 8) +   # Google loves reviews
            (has_website * 5)
        )
        
        # Ensure scores are within bounds
        return {
            'chatgpt': min(max(chatgpt_score, 0), 100),
            'perplexity': min(max(perplexity_score, 0), 100),
            'claude': min(max(claude_score, 0), 100),
            'gemini': min(max(gemini_score, 0), 100)
        }
    
    def _get_llm_insights(self, profile: AgentProfile, base_analysis: Dict, leaderboard: Optional[Dict]) -> Optional[Dict]:
        """Get enhanced insights from LLM (recommendations, not scores)"""
        profile_dict = {k: v for k, v in asdict(profile).items() if v not in (None, "", 0, {})}
        scores = base_analysis.get('scores', {})
        
        prompt = f"""You are a real estate AI visibility consultant. Based on this agent's data and SALT scores, provide actionable insights.

AGENT: {profile.full_name}
LOCATION: {profile.city}, {profile.state}
BROKERAGE: {profile.brokerage_name}
EXPERIENCE: {profile.years_experience} years
REVIEWS: {profile.total_reviews} reviews, {profile.average_rating}/5 rating
SPECIALIZATION: {profile.specialization}

SALT SCORES (already calculated):
- Semantic (Identity Clarity): {scores.get('semantic', {}).get('score', 0)}/100
- Authority (Cite-worthiness): {scores.get('authority', {}).get('score', 0)}/100  
- Location (Market Grounding): {scores.get('location', {}).get('score', 0)}/100
- Trust (Safety to Recommend): {scores.get('trust', {}).get('score', 0)}/100
- Overall: {scores.get('overall', {}).get('score', 0)}/100

Return JSON with ONLY these fields (do not include scores):
{{
    "recommendations": {{
        "for_agent": ["5 specific, actionable recommendations to improve AI visibility"]
    }},
    "profile_analysis": {{
        "strengths": ["3-4 key strengths"],
        "areas_for_improvement": ["3-4 areas to improve"],
        "unique_selling_points": ["2-3 USPs"]
    }},
    "competitive_insights": {{
        "market_position": "Brief market position summary",
        "differentiation_strategy": "How to stand out"
    }}
}}

Return ONLY valid JSON, no markdown."""

        try:
            if self.active_llm == 'openai' and self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1000
                )
                text = response.choices[0].message.content.strip()
            elif self.active_llm == 'gemini' and self.gemini_model:
                response = self.gemini_model.generate_content(prompt)
                text = response.text.strip()
            else:
                return None
            
            # Clean response
            if text.startswith('```json'): text = text[7:]
            if text.startswith('```'): text = text[3:]
            if text.endswith('```'): text = text[:-3]
            
            return json.loads(text.strip())
        except Exception as e:
            print(f"⚠️ LLM insights error: {e}")
            return None
    
    def _calculate_salt_scores(self, p: AgentProfile, lb: Optional[Dict] = None) -> Dict:
        """
        Calculate S.A.L.T. scores based on the framework:
        S - Semantic: Identity clarity - Can AI identify who you are?
        A - Authority: Cite-worthiness - Does AI have access to credible content?
        L - Location: Market grounding - What markets do you work in?
        T - Trust: Safety to recommend - Is the agent reputable and low-risk?
        """
        
        # ============== SEMANTIC SCORE (Identity Clarity) ==============
        # Measures: Name consistency, role clarity, brokerage attribution, bio quality
        semantic = 0
        semantic_f = []
        semantic_breakdown = {
            'identity_consistency': {'score': 0, 'max': 30, 'factors': []},
            'role_clarity': {'score': 0, 'max': 25, 'factors': []},
            'cross_platform': {'score': 0, 'max': 25, 'factors': []},
            'value_proposition': {'score': 0, 'max': 20, 'factors': []}
        }
        
        # 2.1 Identity Consistency (30 pts max)
        if p.full_name and len(p.full_name.split()) >= 2:
            semantic_breakdown['identity_consistency']['score'] += 10
            semantic_breakdown['identity_consistency']['factors'].append("Full name present")
        if p.phone_number:
            semantic_breakdown['identity_consistency']['score'] += 5
            semantic_breakdown['identity_consistency']['factors'].append("Phone number available")
        if p.office_address:
            semantic_breakdown['identity_consistency']['score'] += 5
            semantic_breakdown['identity_consistency']['factors'].append("Office address listed")
        if p.bio_text and len(p.bio_text) > 100:
            semantic_breakdown['identity_consistency']['score'] += 10
            semantic_breakdown['identity_consistency']['factors'].append("Detailed bio present")
        elif p.bio_text:
            semantic_breakdown['identity_consistency']['score'] += 5
            semantic_breakdown['identity_consistency']['factors'].append("Basic bio present")
        
        # 2.2 Role & Positioning Clarity (25 pts max)
        if p.brokerage_name:
            semantic_breakdown['role_clarity']['score'] += 10
            semantic_breakdown['role_clarity']['factors'].append(f"Brokerage: {p.brokerage_name}")
        if p.license_status == 'Active':
            semantic_breakdown['role_clarity']['score'] += 8
            semantic_breakdown['role_clarity']['factors'].append("Active license verified")
        if p.specialization:
            semantic_breakdown['role_clarity']['score'] += 7
            semantic_breakdown['role_clarity']['factors'].append(f"Specialization: {p.specialization}")
        
        # 2.3 Cross-Platform Consistency (25 pts max)
        platforms = sum([1 for x in [p.instagram_url, p.facebook_url, p.twitter_url, p.linkedin_url] if x])
        platform_score = min(platforms * 6, 20)
        semantic_breakdown['cross_platform']['score'] += platform_score
        if platforms >= 3:
            semantic_breakdown['cross_platform']['factors'].append(f"Strong presence on {platforms} platforms")
        elif platforms >= 1:
            semantic_breakdown['cross_platform']['factors'].append(f"Present on {platforms} platform(s) - expand recommended")
        else:
            semantic_breakdown['cross_platform']['factors'].append("No social presence detected - critical gap")
        if p.profile_url:
            semantic_breakdown['cross_platform']['score'] += 5
            semantic_breakdown['cross_platform']['factors'].append("Profile URL available")
        
        # 2.4 Value Proposition (20 pts max)
        if p.years_experience >= 20:
            semantic_breakdown['value_proposition']['score'] += 10
            semantic_breakdown['value_proposition']['factors'].append(f"Veteran: {p.years_experience}+ years")
        elif p.years_experience >= 10:
            semantic_breakdown['value_proposition']['score'] += 7
            semantic_breakdown['value_proposition']['factors'].append(f"Experienced: {p.years_experience} years")
        elif p.years_experience >= 5:
            semantic_breakdown['value_proposition']['score'] += 4
            semantic_breakdown['value_proposition']['factors'].append(f"Established: {p.years_experience} years")
        if p.career_sales:
            semantic_breakdown['value_proposition']['score'] += 5
            semantic_breakdown['value_proposition']['factors'].append(f"Career sales: {p.career_sales}")
        if p.industry_ranking:
            semantic_breakdown['value_proposition']['score'] += 5
            semantic_breakdown['value_proposition']['factors'].append(f"Industry ranking: {p.industry_ranking}")
        
        semantic = sum(s['score'] for s in semantic_breakdown.values())
        for section in semantic_breakdown.values():
            semantic_f.extend(section['factors'])
        
        # ============== AUTHORITY SCORE (Cite-worthiness) ==============
        # Measures: Owned domain, content quality, review volume, media presence
        authority = 0
        authority_f = []
        authority_breakdown = {
            'owned_properties': {'score': 0, 'max': 35, 'factors': []},
            'social_authority': {'score': 0, 'max': 25, 'factors': []},
            'review_authority': {'score': 0, 'max': 25, 'factors': []},
            'media_presence': {'score': 0, 'max': 15, 'factors': []}
        }
        
        # 3.1 Owned Domain Authority (35 pts max)
        if p.website:
            authority_breakdown['owned_properties']['score'] += 25
            authority_breakdown['owned_properties']['factors'].append(f"Owned website: {p.website}")
        else:
            authority_breakdown['owned_properties']['factors'].append("No owned website - AI cites platforms instead")
        if p.profile_url:
            authority_breakdown['owned_properties']['score'] += 10
            authority_breakdown['owned_properties']['factors'].append("Profile page available")
        
        # 3.2 Social Media Authority (25 pts max)
        if p.linkedin_url:
            authority_breakdown['social_authority']['score'] += 8
            authority_breakdown['social_authority']['factors'].append("LinkedIn presence")
        if p.instagram_url:
            authority_breakdown['social_authority']['score'] += 6
            authority_breakdown['social_authority']['factors'].append("Instagram presence")
        if p.facebook_url:
            authority_breakdown['social_authority']['score'] += 6
            authority_breakdown['social_authority']['factors'].append("Facebook presence")
        if p.twitter_url:
            authority_breakdown['social_authority']['score'] += 5
            authority_breakdown['social_authority']['factors'].append("Twitter/X presence")
        
        # 3.3 Review Authority (25 pts max)
        if p.total_reviews >= 100:
            authority_breakdown['review_authority']['score'] += 25
            authority_breakdown['review_authority']['factors'].append(f"Strong review base: {p.total_reviews} reviews")
        elif p.total_reviews >= 50:
            authority_breakdown['review_authority']['score'] += 18
            authority_breakdown['review_authority']['factors'].append(f"Good review base: {p.total_reviews} reviews")
        elif p.total_reviews >= 20:
            authority_breakdown['review_authority']['score'] += 12
            authority_breakdown['review_authority']['factors'].append(f"Developing reviews: {p.total_reviews}")
        elif p.total_reviews > 0:
            authority_breakdown['review_authority']['score'] += 5
            authority_breakdown['review_authority']['factors'].append(f"Limited reviews: {p.total_reviews}")
        else:
            authority_breakdown['review_authority']['factors'].append("No reviews - critical authority gap")
        
        # 3.4 Media/Industry Presence (15 pts max)
        if p.industry_ranking:
            authority_breakdown['media_presence']['score'] += 8
            authority_breakdown['media_presence']['factors'].append(f"Industry recognized: {p.industry_ranking}")
        if p.verified_realtrends == 'Yes':
            authority_breakdown['media_presence']['score'] += 4
            authority_breakdown['media_presence']['factors'].append("RealTrends verified")
        if p.media_mentions_count > 0:
            authority_breakdown['media_presence']['score'] += 3
            authority_breakdown['media_presence']['factors'].append(f"Media mentions: {p.media_mentions_count}")
        
        authority = sum(s['score'] for s in authority_breakdown.values())
        for section in authority_breakdown.values():
            authority_f.extend(section['factors'])
        
        # ============== LOCATION SCORE (Market Grounding) ==============
        # Measures: Geographic signals, neighborhood content, local keywords
        location = 0
        location_f = []
        location_breakdown = {
            'geographic_signals': {'score': 0, 'max': 40, 'factors': []},
            'neighborhood_authority': {'score': 0, 'max': 30, 'factors': []},
            'local_content': {'score': 0, 'max': 30, 'factors': []}
        }
        
        # 4.1 Geographic Signals (40 pts max)
        if p.city:
            location_breakdown['geographic_signals']['score'] += 15
            location_breakdown['geographic_signals']['factors'].append(f"City identified: {p.city}")
        if p.state:
            location_breakdown['geographic_signals']['score'] += 10
            location_breakdown['geographic_signals']['factors'].append(f"State: {p.state}")
        if p.zip_code:
            location_breakdown['geographic_signals']['score'] += 8
            location_breakdown['geographic_signals']['factors'].append(f"ZIP code: {p.zip_code}")
        if p.office_address:
            location_breakdown['geographic_signals']['score'] += 7
            location_breakdown['geographic_signals']['factors'].append("Office address verified")
        
        # 4.2 Neighborhood Authority (30 pts max) - Based on available data
        # Without neighborhood pages, this will be low
        if p.city and p.specialization:
            location_breakdown['neighborhood_authority']['score'] += 10
            location_breakdown['neighborhood_authority']['factors'].append(f"Market specialization in {p.city}")
        if p.total_reviews >= 20 and p.city:
            location_breakdown['neighborhood_authority']['score'] += 8
            location_breakdown['neighborhood_authority']['factors'].append("Review-based local credibility")
        else:
            location_breakdown['neighborhood_authority']['factors'].append("Missing neighborhood-specific content")
        
        # 4.3 Local Content Signals (30 pts max)
        # Website with local content would score higher
        if p.website and p.city:
            location_breakdown['local_content']['score'] += 12
            location_breakdown['local_content']['factors'].append("Website can host local content")
        if p.bio_text and p.city and p.city.lower() in str(p.bio_text).lower():
            location_breakdown['local_content']['score'] += 8
            location_breakdown['local_content']['factors'].append("Bio mentions local market")
        if p.sample_listing_url:
            location_breakdown['local_content']['score'] += 5
            location_breakdown['local_content']['factors'].append("Active listings available")
        if not location_breakdown['local_content']['factors']:
            location_breakdown['local_content']['factors'].append("No local content detected - AI defaults to portals")
        
        location = sum(s['score'] for s in location_breakdown.values())
        for section in location_breakdown.values():
            location_f.extend(section['factors'])
        
        # ============== TRUST SCORE (Safety to Recommend) ==============
        # Measures: Sentiment, reputation signals, license status, outcome proof
        trust = 0
        trust_f = []
        trust_breakdown = {
            'sentiment_profile': {'score': 0, 'max': 35, 'factors': []},
            'license_verification': {'score': 0, 'max': 25, 'factors': []},
            'reputation_signals': {'score': 0, 'max': 25, 'factors': []},
            'outcome_proof': {'score': 0, 'max': 15, 'factors': []}
        }
        
        # 5.1 Sentiment Profile (35 pts max)
        if p.average_rating >= 4.8:
            trust_breakdown['sentiment_profile']['score'] += 35
            trust_breakdown['sentiment_profile']['factors'].append(f"Exceptional rating: {p.average_rating}/5")
        elif p.average_rating >= 4.5:
            trust_breakdown['sentiment_profile']['score'] += 28
            trust_breakdown['sentiment_profile']['factors'].append(f"Excellent rating: {p.average_rating}/5")
        elif p.average_rating >= 4.0:
            trust_breakdown['sentiment_profile']['score'] += 20
            trust_breakdown['sentiment_profile']['factors'].append(f"Good rating: {p.average_rating}/5")
        elif p.average_rating >= 3.5:
            trust_breakdown['sentiment_profile']['score'] += 10
            trust_breakdown['sentiment_profile']['factors'].append(f"Average rating: {p.average_rating}/5")
        elif p.average_rating > 0:
            trust_breakdown['sentiment_profile']['score'] += 5
            trust_breakdown['sentiment_profile']['factors'].append(f"Below average rating: {p.average_rating}/5")
        else:
            trust_breakdown['sentiment_profile']['factors'].append("No rating data available")
        
        # 5.2 License Verification (25 pts max)
        if p.license_status == 'Active':
            trust_breakdown['license_verification']['score'] += 20
            trust_breakdown['license_verification']['factors'].append(f"Active license in {p.jurisdiction}")
        if p.license_number:
            trust_breakdown['license_verification']['score'] += 5
            trust_breakdown['license_verification']['factors'].append("License number verified")
        if not p.license_status:
            trust_breakdown['license_verification']['factors'].append("License status unknown")
        
        # 5.3 Reputation Signals (25 pts max)
        if p.brokerage_name:
            trust_breakdown['reputation_signals']['score'] += 10
            trust_breakdown['reputation_signals']['factors'].append(f"Affiliated with {p.brokerage_name}")
        if p.credibility_tier == 'Elite':
            trust_breakdown['reputation_signals']['score'] += 10
            trust_breakdown['reputation_signals']['factors'].append("Elite credibility tier")
        elif p.credibility_tier:
            trust_breakdown['reputation_signals']['score'] += 5
            trust_breakdown['reputation_signals']['factors'].append(f"Credibility tier: {p.credibility_tier}")
        if p.total_reviews >= 50:
            trust_breakdown['reputation_signals']['score'] += 5
            trust_breakdown['reputation_signals']['factors'].append("Substantial review history")
        
        # 5.4 Outcome Proof (15 pts max)
        if p.career_sales:
            trust_breakdown['outcome_proof']['score'] += 8
            trust_breakdown['outcome_proof']['factors'].append(f"Documented sales: {p.career_sales}")
        if p.years_experience >= 10:
            trust_breakdown['outcome_proof']['score'] += 4
            trust_breakdown['outcome_proof']['factors'].append("Long track record")
        if p.industry_ranking:
            trust_breakdown['outcome_proof']['score'] += 3
            trust_breakdown['outcome_proof']['factors'].append("Industry recognition as proof")
        if not trust_breakdown['outcome_proof']['factors']:
            trust_breakdown['outcome_proof']['factors'].append("Limited outcome documentation")
        
        trust = sum(s['score'] for s in trust_breakdown.values())
        for section in trust_breakdown.values():
            trust_f.extend(section['factors'])
        
        # ============== OVERALL SCORE ==============
        # S.A.L.T. weighted equally as each layer can collapse visibility
        semantic = min(semantic, 100)
        authority = min(authority, 100)
        location = min(location, 100)
        trust = min(trust, 100)
        overall = int((semantic + authority + location + trust) / 4)
        
        def grade(s): return "A+" if s>=97 else "A" if s>=93 else "A-" if s>=90 else "B+" if s>=87 else "B" if s>=83 else "B-" if s>=80 else "C+" if s>=77 else "C" if s>=73 else "C-" if s>=70 else "D" if s>=60 else "F"
        def tier(s): return "Elite" if s>=95 else "Exceptional" if s>=85 else "Strong" if s>=75 else "Solid" if s>=65 else "Developing"
        
        links = {k:v for k,v in {"website":p.website,"linkedin":p.linkedin_url,"instagram":p.instagram_url,"facebook":p.facebook_url}.items() if v}
        
        state_rank = lb.get('state_rank','N/A') if lb else 'N/A'
        city_rank = lb.get('city_rank','N/A') if lb else 'N/A'
        pct = lb.get('percentile','N/A') if lb else 'N/A'
        
        exec_sum = f"{p.full_name} is a {tier(overall).lower()}-tier real estate professional ranked #{state_rank} in {p.state} and #{city_rank} in {p.city}, placing them in the top {pct}% nationally. With {p.years_experience} years of experience and {p.career_sales or 'significant'} in career sales, they demonstrate {'exceptional' if overall>=85 else 'strong' if overall>=70 else 'developing'} market expertise. Client satisfaction is {'excellent' if p.average_rating>=4.8 else 'strong' if p.average_rating>=4.5 else 'good'} with a {p.average_rating}/5.0 rating across {p.total_reviews} reviews on {p.review_platform or 'review platforms'}. "
        if p.industry_ranking: exec_sum += f"Notable achievement: {p.industry_ranking}. "
        exec_sum += f"Specializing in {p.specialization or 'residential'} properties, they operate from {p.city}, {p.state}. "
        if links: exec_sum += f"Connect via: {', '.join([f'{k}: {v}' for k,v in list(links.items())[:2]])}. "
        exec_sum += f"{'Highly recommended' if overall>=85 else 'Recommended' if overall>=70 else 'Consider'} for buyers and sellers in the {p.city} market."
        
        platforms = sum([1 for x in [p.instagram_url, p.facebook_url, p.twitter_url, p.linkedin_url] if x])
        
        return {
            "scores": {
                "semantic": {
                    "score": semantic, 
                    "grade": grade(semantic), 
                    "factors": semantic_f, 
                    "summary": f"Semantic clarity score of {semantic}/100 measuring identity consistency and role clarity.",
                    "breakdown": semantic_breakdown
                },
                "authority": {
                    "score": authority, 
                    "grade": grade(authority), 
                    "factors": authority_f, 
                    "summary": f"Authority score of {authority}/100 based on owned content, reviews ({p.total_reviews}), and cite-worthiness.",
                    "breakdown": authority_breakdown
                },
                "location": {
                    "score": location, 
                    "grade": grade(location), 
                    "factors": location_f, 
                    "summary": f"Location visibility of {location}/100 for market grounding in {p.city}, {p.state}.",
                    "breakdown": location_breakdown
                },
                "trust": {
                    "score": trust, 
                    "grade": grade(trust), 
                    "factors": trust_f, 
                    "summary": f"Trust score of {trust}/100 based on sentiment ({p.average_rating}/5), licensing, and reputation signals.",
                    "breakdown": trust_breakdown
                },
                "overall": {"score": overall, "grade": grade(overall), "tier": tier(overall)}
            },
            "leaderboard": {"national_percentile": f"Top {pct}%", "state_rank": f"#{state_rank}", "city_rank": f"#{city_rank}", "comparative_analysis": f"Ranked #{state_rank} among {lb.get('state_total','N/A') if lb else 'N/A'} agents in {p.state}."},
            "profile_analysis": {"strengths": authority_f[:4], "areas_for_improvement": ["Expand digital presence"] if platforms<3 else ["Continue building reviews"], "unique_selling_points": [p.specialization or "Local expertise", p.industry_ranking or f"{p.years_experience} years experience"], "market_position": f"{p.specialization or 'Residential'} specialist in {p.city}", "ideal_client_match": f"Clients seeking {p.specialization or 'residential'} properties in {p.city}"},
            "competitive_insights": {"market_tier": "Luxury" if p.specialization=="Luxury" else "Mid-Market", "experience_level": "Veteran" if p.years_experience>=20 else "Established" if p.years_experience>=10 else "Growing", "digital_presence": "Excellent" if platforms>=4 else "Good" if platforms>=2 else "Needs Work", "reputation_strength": "Exceptional" if p.total_reviews>=100 else "Strong" if p.total_reviews>=50 else "Building"},
            "key_links": links,
            "actionable_insights": {
                "for_buyers": [f"Agent has {p.years_experience} years experience in {p.city} market", f"Verified {p.total_reviews} client reviews averaging {p.average_rating}/5", "Request recent buyer references and transaction details"],
                "for_sellers": [f"Career sales volume: {p.career_sales or 'substantial'}", f"Market specialization: {p.specialization or 'residential'}", "Ask about marketing strategy and listing exposure channels"],
                "red_flags": [] if overall >= 70 else [
                    f"Low review count ({p.total_reviews}): Fewer reviews means less client feedback and lower AI trust signals. Competitors with 50+ reviews rank higher in search results.",
                    f"Rating at {p.average_rating}/5: Investigate client satisfaction. AI systems prioritize agents with 4.7+ ratings.",
                    f"Limited online presence: Only {platforms} social platforms. Missing on channels where AI crawls for agent credentials."
                ] if overall < 60 else [
                    f"Developing review base: At {p.total_reviews} reviews, consistent growth strategy needed to compete",
                    f"Social presence gaps: Currently on {platforms} platforms, expand to all major channels"
                ],
                "questions_to_ask": ["What's your average days-on-market?", "How do you generate and maintain client reviews?", "What's your content marketing strategy?"],
                "geo_weaknesses": [
                    f"Review generation: Only {p.total_reviews} reviews - top agents have 100+. Each review is a strong AI trust signal.",
                    f"Social presence: Active on {platforms} platforms. AI prefers agents on 4+ channels (Google, Facebook, Instagram, LinkedIn, YouTube).",
                    f"{'Website optimization: ' + ('Not detected - critical gap for AI indexing' if not p.website else 'Ensure GEO keywords and monthly updates for freshness')}",
                    f"Content authority: Limited articles/market insights. Agents publishing monthly content rank 30% higher in AI systems."
                ]
            },
            "competitor_gaps": {
                "missing_signals": [
                    "YouTube channel with property tours and market analysis",
                    "Email newsletter establishing thought leadership",
                    "LinkedIn recommendations from past clients"
                ],
                "content_gaps": [
                    f"Monthly market reports for {p.city}: Agents publishing regularly show up more in AI searches",
                    f"Video content: Property walkthroughs and neighborhood guides (AI weighs video heavily)",
                    f"Blog posts with local SEO: Keyword-rich articles about {p.city} neighborhoods, market trends"
                ],
                "visibility_blockers": [
                    "Inconsistent profile information across platforms: AI struggles with conflicting data",
                    "Stale online content: Profiles not updated in 3+ months hurt freshness scores",
                    "Missing mobile optimization: Website and profiles must be fully mobile-responsive"
                ]
            },
            "geo_improvement_roadmap": {
                "critical_issues": [
                    f"Review momentum: {p.total_reviews} reviews is below market leader average (100+). Implement systematic review generation - each review boosts AI visibility 1-2%.",
                    f"Social platform gaps: Present on {platforms} platforms but AI ranks agents on all 5 major channels. Missing even one costs 15-20% visibility.",
                    f"{'Website SEO: No website detected - massive AI discovery gap.' if not p.website else 'Website exists but ensure regular updates and GEO-targeted keywords.'}"
                ] if overall < 70 else [
                    f"Review growth: Maintain trajectory above {p.total_reviews} - competitors are also improving",
                    f"Content freshness: Update online profiles and social media weekly - AI values recent activity"
                ],
                "high_priority": [
                    "Launch video strategy: 1 property tour/market insight video monthly - video appears in AI searches 5x more than text",
                    f"Implement review system: Automated follow-up to every transaction requesting Google/Zillow reviews - builds from {p.total_reviews} to 150+ in 12 months",
                    "Schema markup on website: Add structured data (Agent, LocalBusiness) so AI understands your credentials automatically",
                    "Authority building: Start monthly market report or newsletter - positions you as an expert AI systems recognize"
                ],
                "medium_priority": [
                    "LinkedIn optimization: Get 10+ recommendations from past clients - shows expertise to AI",
                    f"Geo-targeting: Add {p.city}, all neighborhoods, zip codes to website and profiles",
                    "Specialization emphasis: Highlight niche (luxury, investment, first-time buyers) across all platforms"
                ],
                "quick_wins": [
                    "Google My Business: Claim and verify - update photos, hours, description monthly (AI's #1 local signal)",
                    "Photo refresh: Professional headshots on all platforms (AI checks visual consistency across profiles)",
                    f"Local keywords: Add '{p.city} real estate agent' to all bios - AI matches user searches to profiles with these phrases",
                    "Review response: Reply to every review within 24 hours (AI sees engagement as credibility)"
                ],
                "estimated_impact": f"Current score: {overall}/100. With these improvements: Month 1-3 (+10-15 points via reviews/content), Month 4-6 (+10 points via video/authority), Month 7-12 (+10-15 points via SEO/consistency). Target: {min(overall + 35, 100)}/100 ({tier(min(overall + 35, 100))}) in 12 months."
            },
            "recommendations": {
                "for_buyers_sellers": f"With {p.years_experience} years experience and {p.total_reviews} reviews at {p.average_rating}/5, {p.full_name} is {'highly recommended' if overall>=85 else 'recommended'} for {p.city} real estate.",
                "for_agent": [
                    f"Review generation system: Currently at {p.total_reviews} reviews. Implement automated post-transaction review request - target 10 new reviews/month to reach top 10% visibility",
                    f"Video content production: Create monthly property tour and market insight videos. Video content is ranked 5x higher by AI systems than text-only profiles",
                    f"Market authority: Publish monthly market analysis for {p.city} and key neighborhoods. Thought leadership content makes you discoverable for 'best agent' queries",
                    f"Social media expansion: Expand from {platforms} to all 5 platforms (Google, Facebook, Instagram, LinkedIn, YouTube) with consistent posting 3x/week",
                    f"Website SEO optimization: If website exists, audit for {p.city}, neighborhood keywords, mobile responsiveness, and monthly blog updates. If not, priority #1 for AI discoverability"
                ]
            },
            "executive_summary": exec_sum
        }


class AgentDatabase:
    def __init__(self, excel_path: str):
        print(f"📂 Loading Excel database from: {excel_path}")
        self.df = pd.read_excel(excel_path)
        print(f"✅ Loaded {len(self.df)} records")
        self.df['name_lower'] = self.df['Full_Name'].str.lower().str.strip()
        print(f"⚙️  Computing rankings...")
        self._compute_rankings()
        print(f"🔍 Building search cache...")
        self._build_search_cache()
        print(f"✅ Database ready with {len(self.search_index)} search keys")

    def _build_search_cache(self):
        """Build comprehensive search index for fast lookup with partial matching"""
        from collections import defaultdict
        self.search_index = defaultdict(list)

        for idx, row in self.df.iterrows():
            name_lower = str(row.get('name_lower', '')).lower().strip()
            if not name_lower or name_lower == 'nan':
                continue

            # Get brokerage name safely
            brokerage = str(row.get('Brokerage_Name', ''))
            if brokerage == 'nan' or not brokerage:
                brokerage = ''

            agent_data = {
                'id': str(row.get('Agent_ID', '')),
                'name': str(row.get('Full_Name', '')),
                'city': str(row.get('City', '')),
                'state': str(row.get('State', '')),
                'brokerage': brokerage
            }

            # Skip if name is empty
            if not agent_data['name'] or agent_data['name'] == 'nan':
                continue

            # Index by full name
            self.search_index[name_lower].append(agent_data)

            # Index ALL prefixes for partial matching
            # This allows "jade m" to find "jade mills"
            parts = name_lower.split()
            for i in range(len(parts)):
                # Index individual words
                word = parts[i]
                if len(word) >= 2:  # Skip single letters
                    self.search_index[word].append(agent_data)

                # Index word prefixes (ja, jad, jade)
                for prefix_len in range(2, len(word) + 1):
                    self.search_index[word[:prefix_len]].append(agent_data)

                # Index multi-word combinations with partial last word
                # "jade m", "jade mi", "jade mil", "jade mill", "jade mills"
                for j in range(i+1, len(parts)+1):
                    last_word = parts[j-1]
                    # Full combination
                    full_combo = ' '.join(parts[i:j])
                    if full_combo != name_lower:
                        self.search_index[full_combo].append(agent_data)

                    # Partial last word (jade m, jade mi, etc.)
                    if j == i + 2:  # Only for two-word combinations
                        for prefix_len in range(1, len(last_word)):
                            partial = f"{parts[i]} {last_word[:prefix_len]}"
                            self.search_index[partial].append(agent_data)

    def _compute_rankings(self):
        # Ensure numeric columns exist and handle NaN values
        for col in ['Average_Rating', 'Total_Reviews', 'Years_Experience', 'Credibility_Score']:
            if col not in self.df.columns:
                self.df[col] = 0
            self.df[col] = pd.to_numeric(self.df[col], errors='coerce').fillna(0)

        self.df['rating_rank'] = self.df['Average_Rating'].rank(ascending=False, method='min', na_option='bottom')
        self.df['review_rank'] = self.df['Total_Reviews'].rank(ascending=False, method='min', na_option='bottom')
        self.df['experience_rank'] = self.df['Years_Experience'].rank(ascending=False, method='min', na_option='bottom')
        self.df['credibility_rank'] = self.df['Credibility_Score'].rank(ascending=False, method='min', na_option='bottom')
    
    def _safe_int(self, val, default=1):
        """Safely convert a value to int, handling NaN and None"""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default
    
    def get_leaderboard_context(self, agent_id: str) -> Dict:
        try:
            # Try to match agent_id with different types
            agent = self.df[self.df['Agent_ID'] == agent_id]
            if agent.empty:
                # Try matching as string
                agent = self.df[self.df['Agent_ID'].astype(str) == str(agent_id)]
            if agent.empty:
                print(f"⚠️ No agent found with ID: {agent_id}")
                return {}
            
            agent = agent.iloc[0]
            total = len(self.df)
            
            # Safe access to state/city
            state = agent.get('State', '') if hasattr(agent, 'get') else agent['State'] if 'State' in agent.index else ''
            city = agent.get('City', '') if hasattr(agent, 'get') else agent['City'] if 'City' in agent.index else ''
            
            # Handle state ranking
            state_rank = 1
            state_total = 0
            if state and not pd.isna(state):
                state_df = self.df[self.df['State'] == state]
                state_total = len(state_df)
                if not state_df.empty:
                    state_ranks = state_df['Credibility_Score'].rank(ascending=False, method='min', na_option='bottom')
                    state_rank = self._safe_int(state_ranks.get(agent.name, 1), 1)
            
            # Handle city ranking
            city_rank = 1
            city_total = 0
            if city and not pd.isna(city):
                city_df = self.df[self.df['City'] == city]
                city_total = len(city_df)
                if not city_df.empty:
                    city_ranks = city_df['Credibility_Score'].rank(ascending=False, method='min', na_option='bottom')
                    city_rank = self._safe_int(city_ranks.get(agent.name, 1), 1)
            
            # Safe access to rank columns
            rating_rank = self._safe_int(agent.get('rating_rank') if hasattr(agent, 'get') else agent['rating_rank'], 1)
            review_rank = self._safe_int(agent.get('review_rank') if hasattr(agent, 'get') else agent['review_rank'], 1)
            experience_rank = self._safe_int(agent.get('experience_rank') if hasattr(agent, 'get') else agent['experience_rank'], 1)
            credibility_rank = self._safe_int(agent.get('credibility_rank') if hasattr(agent, 'get') else agent['credibility_rank'], 1)
            
            percentile = round((1 - credibility_rank/total)*100, 1) if total > 0 else 0
            
            return {
                'total_agents': total,
                'rating_rank': rating_rank,
                'review_rank': review_rank,
                'experience_rank': experience_rank,
                'credibility_rank': credibility_rank,
                'percentile': percentile,
                'state_rank': state_rank,
                'state_total': state_total,
                'city_rank': city_rank,
                'city_total': city_total
            }
        except Exception as e:
            print(f"Error in get_leaderboard_context: {e}")
            return {}
    
    def search(self, query: str) -> List[Dict]:
        """Fast search using cached index"""
        q = query.lower().strip()
        if not q:
            return []

        # Check cache first for name matches
        if q in self.search_index:
            results = self.search_index[q]
            # Remove duplicates by agent ID
            seen = set()
            unique_results = []
            for r in results:
                if r['id'] not in seen:
                    seen.add(r['id'])
                    unique_results.append(r)
            return unique_results[:10]

        # Fallback to partial matching on city/state
        matches = []
        try:
            city_state = self.df[
                (self.df['City'].str.lower().str.contains(q, na=False, regex=False)) |
                (self.df['State'].str.lower().str.contains(q, na=False, regex=False))
            ].head(10)

            if not city_state.empty:
                for _, row in city_state.iterrows():
                    name = str(row.get('Full_Name', ''))
                    brokerage = str(row.get('Brokerage_Name', ''))
                    if brokerage == 'nan':
                        brokerage = ''
                    if name and name != 'nan':
                        matches.append({
                            'id': str(row.get('Agent_ID', '')),
                            'name': name,
                            'city': str(row.get('City', '')),
                            'state': str(row.get('State', '')),
                            'brokerage': brokerage
                        })
        except Exception as e:
            print(f"Error in city/state search: {e}")

        return matches
    
    def get_all_agents_for_map(self) -> List[Dict]:
        """Returns ALL agents for map - no limit"""
        agents = []
        for _, row in self.df.iterrows():
            zip_code = str(row.get('ZIP_Code', ''))
            lat, lng = get_coordinates_from_zip(zip_code)
            agents.append({
                'id': row.get('Agent_ID', ''), 'name': row.get('Full_Name', ''),
                'city': row.get('City', ''), 'state': row.get('State', ''),
                'zip': zip_code, 'lat': lat, 'lng': lng,
                'tier': row.get('Credibility_Tier', ''), 'rating': row.get('Average_Rating', 0),
                'brokerage': row.get('Brokerage_Name', ''), 'reviews': row.get('Total_Reviews', 0)
            })
        return agents
    
    def record_to_profile(self, record: Dict) -> AgentProfile:
        def g(k, d=None):
            """Get value from record, handling NaN and None"""
            v = record.get(k, d)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return d
            return v
        
        def g_int(k, d=0):
            """Get integer value, safely handling NaN"""
            v = g(k, d)
            if v is None or v == '' or (isinstance(v, float) and pd.isna(v)):
                return d
            try:
                return int(float(v))
            except (ValueError, TypeError):
                return d
        
        def g_float(k, d=0.0):
            """Get float value, safely handling NaN"""
            v = g(k, d)
            if v is None or v == '' or (isinstance(v, float) and pd.isna(v)):
                return d
            try:
                return float(v)
            except (ValueError, TypeError):
                return d
        
        def g_str(k, d=''):
            """Get string value, safely handling NaN"""
            v = g(k, d)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return d
            return str(v) if v else d
        
        zip_code = g_str('ZIP_Code', '')
        lat, lng = get_coordinates_from_zip(zip_code)
        
        return AgentProfile(
            agent_id=g_str('Agent_ID', ''),
            full_name=g_str('Full_Name', ''),
            license_number=g_str('License_Number', ''),
            license_status=g_str('License_Status', ''),
            jurisdiction=g_str('Jurisdiction', ''),
            city=g_str('City', ''),
            state=g_str('State', ''),
            zip_code=zip_code,
            office_address=g_str('Office_Address', ''),
            latitude=lat,
            longitude=lng,
            brokerage_name=g_str('Brokerage_Name', ''),
            profile_url=g_str('Profile_URL', ''),
            website=g_str('Website_Links', ''),
            instagram_url=g_str('Instagram_URL', ''),
            facebook_url=g_str('Facebook_URL', ''),
            twitter_url=g_str('Twitter_URL', ''),
            linkedin_url=g_str('LinkedIn_URL', ''),
            average_rating=g_float('Average_Rating', 0.0),
            total_reviews=g_int('Total_Reviews', 0),
            review_text=g_str('Review_Text', ''),
            review_platform=g_str('Review_Platform', ''),
            bio_text=g_str('Bio_Text', ''),
            phone_number=g_str('Phone_Number', ''),
            profile_image_url=g_str('Profile_Image_URL', ''),
            years_experience=g_int('Years_Experience', 0),
            specialization=g_str('Specialization', ''),
            career_sales=g_str('Career_Sales', ''),
            industry_ranking=g_str('Industry_Ranking', ''),
            credibility_score=g_int('Credibility_Score', 0),
            credibility_tier=g_str('Credibility_Tier', ''),
            verified_realtrends=g_str('Verified_RealTrends', ''),
            follower_count=g_int('Follower_Count', 0),
            verification_badge=g_str('Verification_Badge', ''),
            media_mentions_count=g_int('Media_Mentions_Count', 0),
            sample_listing_url=g_str('Sample_Listing_URL', ''),
            team_name=g_str('Team_Name', ''),
            observation_timestamp=g_str('Observation_Timestamp', '')
        )


class AgentIntelligenceSystem:
    def __init__(self, excel_path: str, gemini_api_key: Optional[str] = None, openai_api_key: Optional[str] = None):
        self.db = AgentDatabase(excel_path)
        # Initialize unified AI analyzer with both keys
        self.analyzer = AIAnalyzer(
            openai_api_key=openai_api_key or os.environ.get('OPENAI_API_KEY'),
            gemini_api_key=gemini_api_key or os.environ.get('GEMINI_API_KEY')
        )
        print(f"🤖 Active LLM: {self.analyzer.active_llm or 'None (algorithmic only)'}")
    
    def analyze_agent(self, name: str, enrich_web: bool = False) -> Dict:
        results = self.db.search(name)
        if not results: return {"error": f"No agent found matching '{name}'"}

        # Search returns simplified dict, need to get full record from DataFrame
        agent_id = results[0]['id']
        full_record = self.db.df[self.db.df['Agent_ID'] == agent_id].iloc[0].to_dict()
        profile = self.db.record_to_profile(full_record)
        leaderboard = self.db.get_leaderboard_context(profile.agent_id)
        
        # Debug logging
        print(f"📊 Agent: {profile.full_name} (ID: {profile.agent_id})")
        print(f"📍 Location: {profile.city}, {profile.state}")
        if leaderboard:
            print(f"🏆 Leaderboard: State #{leaderboard.get('state_rank')}/{leaderboard.get('state_total')}")
        
        # Use unified analyzer (always calculates SALT algorithmically, enhances with LLM if available)
        analysis = self.analyzer.analyze_agent(profile, leaderboard)
        
        return {
            "agent": {
                "id": profile.agent_id, "name": profile.full_name, "photo": profile.profile_image_url,
                "phone": profile.phone_number,
                "location": {"city": profile.city, "state": profile.state, "zip": profile.zip_code,
                            "address": profile.office_address, "coordinates": {"lat": profile.latitude, "lng": profile.longitude}},
                "brokerage": profile.brokerage_name,
                "license": {"number": profile.license_number, "status": profile.license_status, "jurisdiction": profile.jurisdiction},
                "experience": {"years": profile.years_experience, "specialization": profile.specialization,
                              "career_sales": profile.career_sales, "ranking": profile.industry_ranking, "team": profile.team_name},
                "online_presence": {"website": profile.website, "profile_url": profile.profile_url,
                                   "instagram": {"url": profile.instagram_url}, "facebook": {"url": profile.facebook_url},
                                   "twitter": {"url": profile.twitter_url}, "linkedin": {"url": profile.linkedin_url}},
                "social_metrics": {"followers": profile.follower_count, "verified": profile.verification_badge=='Yes', "media_mentions": profile.media_mentions_count},
                "reviews": {"average_rating": profile.average_rating, "total_count": profile.total_reviews,
                           "platform": profile.review_platform, "sample_review": profile.review_text},
                "bio": profile.bio_text,
                "credibility": {"score": profile.credibility_score, "tier": profile.credibility_tier, "realtrends_verified": profile.verified_realtrends=='Yes'}
            },
            "analysis": analysis,
            "leaderboard_context": leaderboard,
            "metadata": {
                "data_source": f"SALT Algorithm + {self.analyzer.active_llm or 'No LLM'}", 
                "database_updated": profile.observation_timestamp,
                "analysis_timestamp": datetime.now().isoformat(), 
                "total_agents": leaderboard.get('total_agents', 0) if leaderboard else 0,
                "active_llm": self.analyzer.active_llm
            }
        }
    
    def get_map_data(self, limit: Optional[int] = None) -> List[Dict]:
        """Get ALL agents for map - no limit by default"""
        agents = self.db.get_all_agents_for_map()
        return agents[:limit] if limit else agents


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['analyze', 'map'])
    parser.add_argument('--name', '-n')
    parser.add_argument('--gemini-key', '-g')
    parser.add_argument('--openai-key', '-o')
    parser.add_argument('--db', '-d', default='US_Real_Estate_Agents_Database.xlsx')
    args = parser.parse_args()
    
    system = AgentIntelligenceSystem(
        args.db, 
        gemini_api_key=args.gemini_key,
        openai_api_key=args.openai_key
    )
    
    if args.action == 'analyze' and args.name:
        print(json.dumps(system.analyze_agent(args.name), indent=2, default=str))
    elif args.action == 'map':
        data = system.get_map_data()
        print(json.dumps({'total': len(data), 'message': f'All {len(data)} agents available for map'}, indent=2))

if __name__ == '__main__':
    main()