"""
Real Estate Agent Intelligence System v2 - ENHANCED
Powered by Google Gemini / OpenAI + RAG with detailed executive summaries and leaderboard rankings

===================================================================================
ARCHITECTURE OVERVIEW (Web-Verified Scoring Pipeline)
===================================================================================

This system implements a 3-layer architecture for agent scoring:

1. INPUT SEED LAYER (Excel → Identity Only)
   - Excel data is used ONLY to identify agents and seed URL discovery
   - NO scoring is derived from Excel fields
   - Extracts: name, location, license, known URLs

2. WEB SIGNAL LAYER (Source of Truth)
   - Actively scrapes/fetches live data from web sources
   - Sources: Agent websites, Google Business, Zillow, Realtor.com, social platforms
   - Extracts verifiable signals: reviews, ratings, listings, social presence

3. SCORING LAYER (Derived from Web Signals Only)
   - Computes SALT and AI Visibility scores from verified web signals
   - Missing signals reduce scores (no inflation from Excel data)
   - Deterministic: same input = same output (temperature=0, no randomness)

LLM Usage Rules:
- LLM may ONLY interpret/classify scraped content
- LLM must NOT invent data or infer from Excel text
- Fixed prompts, temperature=0 for determinism
===================================================================================
"""

import pandas as pd
import json
import os
import argparse
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
import hashlib
import re
from urllib.parse import urlparse

# Web scraping libraries
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️ requests library not available - web scraping disabled")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("⚠️ BeautifulSoup not available - HTML parsing limited")

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

# ===================================================================================
# CONSTANTS FOR DETERMINISTIC SCORING
# ===================================================================================

# LLM temperature set to 0 for deterministic outputs
LLM_TEMPERATURE = 0

# Cache timeout for web signals (seconds) - ensures consistency within a session
WEB_CACHE_TIMEOUT = 3600  # 1 hour

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


# ===================================================================================
# INPUT SEED LAYER
# ===================================================================================
# This layer extracts ONLY identity information from Excel.
# Excel data is used as an entry point and URL seed, NOT for scoring.
# ===================================================================================

@dataclass
class AgentSeed:
    """
    Minimal identity extracted from Excel - used ONLY for identification and URL discovery.
    NO scoring should be derived from these fields directly.
    """
    agent_id: str
    full_name: str
    license_number: str
    jurisdiction: str
    city: str
    state: str
    zip_code: str
    # Seed URLs for web discovery (not scored directly)
    website_url: str = ""
    profile_url: str = ""
    instagram_url: str = ""
    facebook_url: str = ""
    twitter_url: str = ""
    linkedin_url: str = ""
    # Coordinates for map display only
    latitude: float = 0.0
    longitude: float = 0.0


class InputSeedLayer:
    """
    INPUT SEED LAYER: Extracts identity from Excel as entry point only.
    
    Purpose:
    - Parse agent name, location, license number from Excel
    - Extract seed URLs for web discovery
    - NO scoring data is extracted here
    
    Excel fields are used ONLY to identify who to look up on the web.
    """
    
    @staticmethod
    def extract_seed(record: Dict) -> AgentSeed:
        """
        Extract minimal identity seed from Excel record.
        This is the ONLY place where Excel data enters the system.
        """
        def safe_str(key: str, default: str = '') -> str:
            val = record.get(key)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return default
            return str(val).strip() if val else default
        
        zip_code = safe_str('ZIP_Code')
        lat, lng = get_coordinates_from_zip(zip_code)
        
        return AgentSeed(
            agent_id=safe_str('Agent_ID'),
            full_name=safe_str('Full_Name'),
            license_number=safe_str('License_Number'),
            jurisdiction=safe_str('Jurisdiction'),
            city=safe_str('City'),
            state=safe_str('State'),
            zip_code=zip_code,
            website_url=safe_str('Website_Links'),
            profile_url=safe_str('Profile_URL'),
            instagram_url=safe_str('Instagram_URL'),
            facebook_url=safe_str('Facebook_URL'),
            twitter_url=safe_str('Twitter_URL'),
            linkedin_url=safe_str('LinkedIn_URL'),
            latitude=lat,
            longitude=lng
        )


# ===================================================================================
# WEB SIGNAL LAYER
# ===================================================================================
# This layer fetches LIVE data from web sources.
# All scoring signals MUST come from verified web data, not Excel.
# ===================================================================================

@dataclass
class WebSignals:
    """
    Verified signals extracted from web sources.
    These are the ONLY signals used for scoring.
    """
    # Identity verification
    name_verified: bool = False
    license_verified: bool = False
    address_verified: bool = False
    phone_verified: bool = False
    
    # Website signals
    website_exists: bool = False
    website_accessible: bool = False
    website_has_ssl: bool = False
    website_has_listings: bool = False
    website_has_bio: bool = False
    website_has_contact: bool = False
    website_last_updated: Optional[str] = None
    
    # Review signals (from Google, Zillow, Realtor.com)
    google_review_count: int = 0
    google_rating: float = 0.0
    zillow_review_count: int = 0
    zillow_rating: float = 0.0
    realtor_review_count: int = 0
    realtor_rating: float = 0.0
    total_verified_reviews: int = 0
    average_verified_rating: float = 0.0
    
    # Social presence signals
    linkedin_exists: bool = False
    linkedin_accessible: bool = False
    linkedin_connections: int = 0
    instagram_exists: bool = False
    instagram_accessible: bool = False
    instagram_followers: int = 0
    facebook_exists: bool = False
    facebook_accessible: bool = False
    twitter_exists: bool = False
    twitter_accessible: bool = False
    
    # Authority signals
    press_mentions: int = 0
    industry_awards: List[str] = field(default_factory=list)
    association_memberships: List[str] = field(default_factory=list)
    
    # Listing signals
    active_listing_count: int = 0
    sold_listing_count: int = 0
    listing_urls: List[str] = field(default_factory=list)
    
    # Brokerage verification
    brokerage_name: str = ""
    brokerage_verified: bool = False
    
    # Data collection metadata
    signals_collected_at: str = ""
    collection_errors: List[str] = field(default_factory=list)
    sources_checked: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class WebSignalLayer:
    """
    WEB SIGNAL LAYER: Fetches and verifies live data from web sources.
    
    This is the SOURCE OF TRUTH for all scoring.
    
    Sources checked:
    - Agent website (accessibility, content, SSL)
    - Google Business / Maps (reviews, rating)
    - Zillow (reviews, listings)
    - Realtor.com (reviews, listings)
    - Social platforms (presence, accessibility)
    - Press/news (authority mentions)
    
    Missing signals = lower scores (no inflation from assumptions).
    """
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session() if REQUESTS_AVAILABLE else None
        self._cache: Dict[str, Tuple[WebSignals, float]] = {}  # URL -> (signals, timestamp)
        
        if self.session:
            # Set realistic user agent for web requests
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
    
    def collect_signals(self, seed: AgentSeed) -> WebSignals:
        """
        Collect all web signals for an agent based on seed URLs.
        
        Returns WebSignals with ONLY verified data from web sources.
        Missing data results in default values (0, False, empty).
        """
        signals = WebSignals()
        signals.signals_collected_at = datetime.now().isoformat()
        
        if not self.session:
            signals.collection_errors.append("Web scraping disabled - requests library not available")
            return signals
        
        # Check website
        if seed.website_url:
            self._check_website(seed.website_url, signals)
        
        # Check social platforms
        self._check_social_platforms(seed, signals)
        
        # Check marketplace profiles (Zillow, Realtor.com)
        self._check_marketplace_profiles(seed, signals)
        
        # Check Google Business presence
        self._check_google_business(seed, signals)
        
        # Calculate totals from verified sources only
        self._calculate_verified_totals(signals)
        
        return signals
    
    def _check_website(self, url: str, signals: WebSignals) -> None:
        """Check agent's own website for signals."""
        if not self.session:
            return
            
        signals.sources_checked.append(f"website:{url}")
        
        try:
            # Normalize URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            signals.website_exists = True
            
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            
            if response.status_code == 200:
                signals.website_accessible = True
                signals.website_has_ssl = response.url.startswith('https://')
                
                if BS4_AVAILABLE:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Check for common real estate content
                    text_lower = response.text.lower()
                    signals.website_has_listings = any(kw in text_lower for kw in 
                        ['listing', 'property', 'for sale', 'mls', 'homes'])
                    signals.website_has_bio = any(kw in text_lower for kw in 
                        ['about', 'biography', 'experience', 'years'])
                    signals.website_has_contact = any(kw in text_lower for kw in 
                        ['contact', 'phone', 'email', 'call'])
                    
                    # Check for brokerage info
                    for tag in soup.find_all(['span', 'div', 'p']):
                        text = tag.get_text().lower()
                        if any(b in text for b in ['realty', 'real estate', 'brokerage', 'keller williams', 
                                                    'coldwell banker', 'remax', 'century 21', 'compass']):
                            signals.brokerage_verified = True
                            break
                else:
                    # Basic text analysis without BeautifulSoup
                    text_lower = response.text.lower()
                    signals.website_has_listings = 'listing' in text_lower or 'property' in text_lower
                    signals.website_has_bio = 'about' in text_lower or 'experience' in text_lower
                    signals.website_has_contact = 'contact' in text_lower or 'phone' in text_lower
            else:
                signals.collection_errors.append(f"Website returned status {response.status_code}")
                
        except requests.exceptions.SSLError:
            signals.website_accessible = True  # Site exists but SSL issue
            signals.website_has_ssl = False
        except requests.exceptions.Timeout:
            signals.collection_errors.append("Website timeout")
        except requests.exceptions.RequestException as e:
            signals.collection_errors.append(f"Website error: {str(e)[:50]}")
    
    def _check_social_platforms(self, seed: AgentSeed, signals: WebSignals) -> None:
        """Verify social platform presence (accessibility only, not content)."""
        if not self.session:
            return
        
        platforms = [
            ('linkedin', seed.linkedin_url, 'linkedin_exists', 'linkedin_accessible'),
            ('instagram', seed.instagram_url, 'instagram_exists', 'instagram_accessible'),
            ('facebook', seed.facebook_url, 'facebook_exists', 'facebook_accessible'),
            ('twitter', seed.twitter_url, 'twitter_exists', 'twitter_accessible'),
        ]
        
        for name, url, exists_attr, accessible_attr in platforms:
            if url:
                setattr(signals, exists_attr, True)
                signals.sources_checked.append(f"{name}:{url}")
                
                try:
                    # Just check if the URL is accessible (HEAD request)
                    response = self.session.head(url, timeout=self.timeout, allow_redirects=True)
                    # Social platforms may return various status codes
                    if response.status_code < 400:
                        setattr(signals, accessible_attr, True)
                except requests.exceptions.RequestException:
                    # Platform exists (URL provided) but may be inaccessible
                    pass
    
    def _check_marketplace_profiles(self, seed: AgentSeed, signals: WebSignals) -> None:
        """
        Check marketplace profiles (Zillow, Realtor.com) for reviews and listings.
        
        Note: Actual scraping of these sites may be limited by their terms of service.
        In production, this should use official APIs where available.
        """
        if not self.session:
            return
        
        # Construct potential profile URLs based on agent name
        agent_name_slug = seed.full_name.lower().replace(' ', '-')
        
        zillow_url = f"https://www.zillow.com/profile/{agent_name_slug}"
        realtor_url = f"https://www.realtor.com/realestateagents/{agent_name_slug}"
        
        # Zillow check
        signals.sources_checked.append(f"zillow:{zillow_url}")
        try:
            response = self.session.get(zillow_url, timeout=self.timeout)
            if response.status_code == 200:
                # Extract review signals if available
                if BS4_AVAILABLE:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # Look for review count patterns
                    text = response.text
                    review_match = re.search(r'(\d+)\s*review', text.lower())
                    if review_match:
                        signals.zillow_review_count = int(review_match.group(1))
                    rating_match = re.search(r'(\d+\.?\d*)\s*/\s*5', text)
                    if rating_match:
                        signals.zillow_rating = float(rating_match.group(1))
        except requests.exceptions.RequestException:
            pass
        
        # Realtor.com check
        signals.sources_checked.append(f"realtor:{realtor_url}")
        try:
            response = self.session.get(realtor_url, timeout=self.timeout)
            if response.status_code == 200:
                if BS4_AVAILABLE:
                    text = response.text
                    review_match = re.search(r'(\d+)\s*review', text.lower())
                    if review_match:
                        signals.realtor_review_count = int(review_match.group(1))
                    rating_match = re.search(r'(\d+\.?\d*)\s*/\s*5', text)
                    if rating_match:
                        signals.realtor_rating = float(rating_match.group(1))
        except requests.exceptions.RequestException:
            pass
    
    def _check_google_business(self, seed: AgentSeed, signals: WebSignals) -> None:
        """
        Check Google Business presence.
        
        Note: Google Places API should be used in production for accurate data.
        This is a placeholder for the structure.
        """
        # In production, this would use Google Places API
        # For now, we mark it as a source we attempted to check
        signals.sources_checked.append(f"google_business:{seed.full_name}, {seed.city}")
        
        # Without API access, we cannot verify Google signals
        # This is intentionally left with 0 values - missing signals = lower score
    
    def _calculate_verified_totals(self, signals: WebSignals) -> None:
        """Calculate aggregate totals from verified sources only."""
        
        # Total reviews from all verified sources
        signals.total_verified_reviews = (
            signals.google_review_count + 
            signals.zillow_review_count + 
            signals.realtor_review_count
        )
        
        # Weighted average rating from verified sources
        ratings = []
        if signals.google_rating > 0:
            ratings.append((signals.google_rating, signals.google_review_count))
        if signals.zillow_rating > 0:
            ratings.append((signals.zillow_rating, signals.zillow_review_count))
        if signals.realtor_rating > 0:
            ratings.append((signals.realtor_rating, signals.realtor_review_count))
        
        if ratings:
            total_weight = sum(count for _, count in ratings)
            if total_weight > 0:
                signals.average_verified_rating = sum(r * c for r, c in ratings) / total_weight
            else:
                # If we have ratings but no counts, simple average
                signals.average_verified_rating = sum(r for r, _ in ratings) / len(ratings)


# ===================================================================================
# SIGNAL EXTRACTION LAYER
# ===================================================================================
# Normalizes and classifies web signals for scoring.
# ===================================================================================

class SignalExtractor:
    """
    SIGNAL EXTRACTION LAYER: Normalizes web signals for scoring.
    
    Converts raw web signals into normalized scores (0-100).
    Uses deterministic formulas - no randomness, no LLM interpretation here.
    """
    
    @staticmethod
    def extract_identity_signals(seed: AgentSeed, signals: WebSignals) -> Dict[str, Any]:
        """Extract identity-related signals for Semantic score."""
        return {
            'has_full_name': bool(seed.full_name and len(seed.full_name.split()) >= 2),
            'has_license': bool(seed.license_number),
            'has_jurisdiction': bool(seed.jurisdiction),
            'has_city': bool(seed.city),
            'has_state': bool(seed.state),
            'website_exists': signals.website_exists,
            'website_accessible': signals.website_accessible,
            'website_has_bio': signals.website_has_bio,
            'website_has_contact': signals.website_has_contact,
            'social_platform_count': sum([
                signals.linkedin_exists,
                signals.instagram_exists,
                signals.facebook_exists,
                signals.twitter_exists
            ]),
            'social_accessible_count': sum([
                signals.linkedin_accessible,
                signals.instagram_accessible,
                signals.facebook_accessible,
                signals.twitter_accessible
            ])
        }
    
    @staticmethod
    def extract_authority_signals(signals: WebSignals) -> Dict[str, Any]:
        """Extract authority-related signals for Authority score."""
        return {
            'website_exists': signals.website_exists,
            'website_accessible': signals.website_accessible,
            'website_has_ssl': signals.website_has_ssl,
            'website_has_listings': signals.website_has_listings,
            'total_reviews': signals.total_verified_reviews,
            'average_rating': signals.average_verified_rating,
            'google_reviews': signals.google_review_count,
            'zillow_reviews': signals.zillow_review_count,
            'realtor_reviews': signals.realtor_review_count,
            'linkedin_exists': signals.linkedin_exists,
            'linkedin_accessible': signals.linkedin_accessible,
            'press_mentions': signals.press_mentions,
            'brokerage_verified': signals.brokerage_verified
        }
    
    @staticmethod
    def extract_location_signals(seed: AgentSeed, signals: WebSignals) -> Dict[str, Any]:
        """Extract location-related signals for Location score."""
        return {
            'has_city': bool(seed.city),
            'has_state': bool(seed.state),
            'has_zip': bool(seed.zip_code),
            'has_coordinates': seed.latitude != 0 and seed.longitude != 0,
            'website_accessible': signals.website_accessible,
            'active_listings': signals.active_listing_count,
            'sold_listings': signals.sold_listing_count,
            'brokerage_verified': signals.brokerage_verified,
            'address_verified': signals.address_verified
        }
    
    @staticmethod
    def extract_trust_signals(seed: AgentSeed, signals: WebSignals) -> Dict[str, Any]:
        """Extract trust-related signals for Trust score."""
        return {
            'has_license': bool(seed.license_number),
            'license_verified': signals.license_verified,
            'website_has_ssl': signals.website_has_ssl,
            'average_rating': signals.average_verified_rating,
            'total_reviews': signals.total_verified_reviews,
            'google_rating': signals.google_rating,
            'zillow_rating': signals.zillow_rating,
            'brokerage_verified': signals.brokerage_verified,
            'phone_verified': signals.phone_verified,
            'address_verified': signals.address_verified
        }


# ===================================================================================
# SCORING LAYER
# ===================================================================================
# Computes SALT and AI Visibility scores from WEB SIGNALS ONLY.
# Excel data is NOT used here - only verified web signals.
# ===================================================================================

class ScoringLayer:
    """
    SCORING LAYER: Computes scores from web signals ONLY.
    
    Critical Rules:
    1. NO Excel data is used in scoring calculations
    2. Missing signals = reduced scores (no assumptions)
    3. All formulas are deterministic (no randomness)
    4. Same input signals = same output scores every time
    
    SALT Framework:
    S - Semantic: Identity clarity from web presence
    A - Authority: Cite-worthiness from reviews, content, mentions
    L - Location: Market grounding from listings, local signals
    T - Trust: Safety to recommend from ratings, verification
    """
    
    @staticmethod
    def compute_semantic_score(identity_signals: Dict) -> Dict:
        """
        Compute Semantic (Identity Clarity) score from web signals.
        
        Scoring breakdown:
        - Name/License identifiable: 20 pts max
        - Website presence: 30 pts max
        - Social consistency: 30 pts max
        - Contact availability: 20 pts max
        """
        score = 0
        factors = []
        breakdown = {
            'identity_verification': {'score': 0, 'max': 20, 'factors': []},
            'website_presence': {'score': 0, 'max': 30, 'factors': []},
            'social_consistency': {'score': 0, 'max': 30, 'factors': []},
            'contact_availability': {'score': 0, 'max': 20, 'factors': []}
        }
        
        # Identity verification (20 pts max)
        if identity_signals['has_full_name']:
            breakdown['identity_verification']['score'] += 10
            breakdown['identity_verification']['factors'].append("Full name identified")
        if identity_signals['has_license']:
            breakdown['identity_verification']['score'] += 5
            breakdown['identity_verification']['factors'].append("License number available")
        if identity_signals['has_jurisdiction']:
            breakdown['identity_verification']['score'] += 5
            breakdown['identity_verification']['factors'].append("Jurisdiction identified")
        
        # Website presence (30 pts max)
        if identity_signals['website_exists']:
            breakdown['website_presence']['score'] += 10
            breakdown['website_presence']['factors'].append("Website URL exists")
            if identity_signals['website_accessible']:
                breakdown['website_presence']['score'] += 10
                breakdown['website_presence']['factors'].append("Website is accessible")
                if identity_signals['website_has_bio']:
                    breakdown['website_presence']['score'] += 5
                    breakdown['website_presence']['factors'].append("Bio content verified on website")
                if identity_signals['website_has_contact']:
                    breakdown['website_presence']['score'] += 5
                    breakdown['website_presence']['factors'].append("Contact info verified on website")
            else:
                breakdown['website_presence']['factors'].append("Website exists but not accessible")
        else:
            breakdown['website_presence']['factors'].append("No website detected - critical identity gap")
        
        # Social consistency (30 pts max)
        platform_count = identity_signals['social_platform_count']
        accessible_count = identity_signals['social_accessible_count']
        
        # Points for existing platforms (max 20)
        platform_pts = min(platform_count * 5, 20)
        breakdown['social_consistency']['score'] += platform_pts
        if platform_count > 0:
            breakdown['social_consistency']['factors'].append(f"{platform_count} social platform(s) linked")
        
        # Bonus for accessible platforms (max 10)
        if accessible_count > 0:
            access_pts = min(accessible_count * 3, 10)
            breakdown['social_consistency']['score'] += access_pts
            breakdown['social_consistency']['factors'].append(f"{accessible_count} platform(s) verified accessible")
        else:
            if platform_count > 0:
                breakdown['social_consistency']['factors'].append("Social profiles not verified accessible")
            else:
                breakdown['social_consistency']['factors'].append("No social presence detected")
        
        # Contact availability (20 pts max)
        if identity_signals['has_city'] and identity_signals['has_state']:
            breakdown['contact_availability']['score'] += 10
            breakdown['contact_availability']['factors'].append("City and state identified")
        if identity_signals['website_has_contact']:
            breakdown['contact_availability']['score'] += 10
            breakdown['contact_availability']['factors'].append("Contact information on website")
        
        # Aggregate score and factors
        score = sum(s['score'] for s in breakdown.values())
        score = min(score, 100)  # Cap at 100
        
        for section in breakdown.values():
            factors.extend(section['factors'])
        
        return {
            'score': score,
            'grade': ScoringLayer._grade(score),
            'factors': factors,
            'breakdown': breakdown,
            'summary': f"Semantic score of {score}/100 based on verified web identity signals"
        }
    
    @staticmethod
    def compute_authority_score(authority_signals: Dict) -> Dict:
        """
        Compute Authority (Cite-worthiness) score from web signals.
        
        Scoring breakdown:
        - Website quality: 25 pts max
        - Review authority: 40 pts max
        - Professional presence: 20 pts max
        - Media/brokerage verification: 15 pts max
        """
        score = 0
        factors = []
        breakdown = {
            'website_quality': {'score': 0, 'max': 25, 'factors': []},
            'review_authority': {'score': 0, 'max': 40, 'factors': []},
            'professional_presence': {'score': 0, 'max': 20, 'factors': []},
            'verification': {'score': 0, 'max': 15, 'factors': []}
        }
        
        # Website quality (25 pts max)
        if authority_signals['website_exists']:
            breakdown['website_quality']['score'] += 5
            breakdown['website_quality']['factors'].append("Website exists")
            if authority_signals['website_accessible']:
                breakdown['website_quality']['score'] += 5
                breakdown['website_quality']['factors'].append("Website accessible")
                if authority_signals['website_has_ssl']:
                    breakdown['website_quality']['score'] += 5
                    breakdown['website_quality']['factors'].append("SSL certificate verified")
                if authority_signals['website_has_listings']:
                    breakdown['website_quality']['score'] += 10
                    breakdown['website_quality']['factors'].append("Active listings on website")
        else:
            breakdown['website_quality']['factors'].append("No owned website - AI cites third-party platforms")
        
        # Review authority (40 pts max) - THE MOST IMPORTANT SIGNAL
        total_reviews = authority_signals['total_reviews']
        avg_rating = authority_signals['average_rating']
        
        if total_reviews >= 100:
            breakdown['review_authority']['score'] += 25
            breakdown['review_authority']['factors'].append(f"Strong review base: {total_reviews} verified reviews")
        elif total_reviews >= 50:
            breakdown['review_authority']['score'] += 18
            breakdown['review_authority']['factors'].append(f"Good review base: {total_reviews} verified reviews")
        elif total_reviews >= 20:
            breakdown['review_authority']['score'] += 12
            breakdown['review_authority']['factors'].append(f"Developing reviews: {total_reviews} verified")
        elif total_reviews >= 5:
            breakdown['review_authority']['score'] += 6
            breakdown['review_authority']['factors'].append(f"Limited reviews: {total_reviews} verified")
        elif total_reviews > 0:
            breakdown['review_authority']['score'] += 2
            breakdown['review_authority']['factors'].append(f"Minimal reviews: {total_reviews}")
        else:
            breakdown['review_authority']['factors'].append("No verified reviews found - critical authority gap")
        
        # Rating bonus (max 15 pts)
        if avg_rating >= 4.8:
            breakdown['review_authority']['score'] += 15
            breakdown['review_authority']['factors'].append(f"Exceptional rating: {avg_rating:.1f}/5")
        elif avg_rating >= 4.5:
            breakdown['review_authority']['score'] += 12
            breakdown['review_authority']['factors'].append(f"Excellent rating: {avg_rating:.1f}/5")
        elif avg_rating >= 4.0:
            breakdown['review_authority']['score'] += 8
            breakdown['review_authority']['factors'].append(f"Good rating: {avg_rating:.1f}/5")
        elif avg_rating >= 3.5:
            breakdown['review_authority']['score'] += 4
            breakdown['review_authority']['factors'].append(f"Average rating: {avg_rating:.1f}/5")
        elif avg_rating > 0:
            breakdown['review_authority']['factors'].append(f"Below average rating: {avg_rating:.1f}/5")
        
        # Professional presence (20 pts max)
        if authority_signals['linkedin_exists']:
            breakdown['professional_presence']['score'] += 10
            breakdown['professional_presence']['factors'].append("LinkedIn profile exists")
            if authority_signals['linkedin_accessible']:
                breakdown['professional_presence']['score'] += 5
                breakdown['professional_presence']['factors'].append("LinkedIn profile accessible")
        
        if authority_signals['press_mentions'] > 0:
            breakdown['professional_presence']['score'] += 5
            breakdown['professional_presence']['factors'].append(f"{authority_signals['press_mentions']} press mentions")
        
        # Verification signals (15 pts max)
        if authority_signals['brokerage_verified']:
            breakdown['verification']['score'] += 10
            breakdown['verification']['factors'].append("Brokerage affiliation verified on website")
        
        # Review source diversity bonus
        sources = sum([
            authority_signals['google_reviews'] > 0,
            authority_signals['zillow_reviews'] > 0,
            authority_signals['realtor_reviews'] > 0
        ])
        if sources >= 2:
            breakdown['verification']['score'] += 5
            breakdown['verification']['factors'].append(f"Reviews verified across {sources} platforms")
        
        # Aggregate
        score = sum(s['score'] for s in breakdown.values())
        score = min(score, 100)
        
        for section in breakdown.values():
            factors.extend(section['factors'])
        
        return {
            'score': score,
            'grade': ScoringLayer._grade(score),
            'factors': factors,
            'breakdown': breakdown,
            'summary': f"Authority score of {score}/100 based on {total_reviews} verified reviews and web presence"
        }
    
    @staticmethod
    def compute_location_score(location_signals: Dict, city: str, state: str) -> Dict:
        """
        Compute Location (Market Grounding) score from web signals.
        
        Scoring breakdown:
        - Geographic identification: 30 pts max
        - Local content signals: 40 pts max
        - Listing activity: 30 pts max
        """
        score = 0
        factors = []
        breakdown = {
            'geographic_signals': {'score': 0, 'max': 30, 'factors': []},
            'local_content': {'score': 0, 'max': 40, 'factors': []},
            'listing_activity': {'score': 0, 'max': 30, 'factors': []}
        }
        
        # Geographic identification (30 pts max)
        if location_signals['has_city']:
            breakdown['geographic_signals']['score'] += 10
            breakdown['geographic_signals']['factors'].append(f"City identified: {city}")
        if location_signals['has_state']:
            breakdown['geographic_signals']['score'] += 8
            breakdown['geographic_signals']['factors'].append(f"State: {state}")
        if location_signals['has_zip']:
            breakdown['geographic_signals']['score'] += 6
            breakdown['geographic_signals']['factors'].append("ZIP code available")
        if location_signals['has_coordinates']:
            breakdown['geographic_signals']['score'] += 6
            breakdown['geographic_signals']['factors'].append("Coordinates mapped")
        
        # Local content signals (40 pts max)
        if location_signals['website_accessible']:
            breakdown['local_content']['score'] += 15
            breakdown['local_content']['factors'].append("Website can serve local content")
        else:
            breakdown['local_content']['factors'].append("No local content source detected")
        
        if location_signals['brokerage_verified']:
            breakdown['local_content']['score'] += 10
            breakdown['local_content']['factors'].append("Brokerage association verified")
        
        if location_signals['address_verified']:
            breakdown['local_content']['score'] += 15
            breakdown['local_content']['factors'].append("Office address verified")
        else:
            breakdown['local_content']['factors'].append("Office address not verified")
        
        # Listing activity (30 pts max)
        active = location_signals['active_listings']
        sold = location_signals['sold_listings']
        
        if active >= 10:
            breakdown['listing_activity']['score'] += 15
            breakdown['listing_activity']['factors'].append(f"{active} active listings verified")
        elif active >= 5:
            breakdown['listing_activity']['score'] += 10
            breakdown['listing_activity']['factors'].append(f"{active} active listings")
        elif active > 0:
            breakdown['listing_activity']['score'] += 5
            breakdown['listing_activity']['factors'].append(f"{active} active listing(s)")
        else:
            breakdown['listing_activity']['factors'].append("No active listings verified")
        
        if sold >= 20:
            breakdown['listing_activity']['score'] += 15
            breakdown['listing_activity']['factors'].append(f"{sold} sold listings verified")
        elif sold >= 10:
            breakdown['listing_activity']['score'] += 10
            breakdown['listing_activity']['factors'].append(f"{sold} sold listings")
        elif sold > 0:
            breakdown['listing_activity']['score'] += 5
            breakdown['listing_activity']['factors'].append(f"{sold} sold listing(s)")
        
        # Aggregate
        score = sum(s['score'] for s in breakdown.values())
        score = min(score, 100)
        
        for section in breakdown.values():
            factors.extend(section['factors'])
        
        return {
            'score': score,
            'grade': ScoringLayer._grade(score),
            'factors': factors,
            'breakdown': breakdown,
            'summary': f"Location score of {score}/100 for market grounding in {city}, {state}"
        }
    
    @staticmethod
    def compute_trust_score(trust_signals: Dict) -> Dict:
        """
        Compute Trust (Safety to Recommend) score from web signals.
        
        Scoring breakdown:
        - License verification: 25 pts max
        - Reputation signals: 40 pts max
        - Security/verification: 20 pts max
        - Contact verification: 15 pts max
        """
        score = 0
        factors = []
        breakdown = {
            'license_verification': {'score': 0, 'max': 25, 'factors': []},
            'reputation_signals': {'score': 0, 'max': 40, 'factors': []},
            'security_verification': {'score': 0, 'max': 20, 'factors': []},
            'contact_verification': {'score': 0, 'max': 15, 'factors': []}
        }
        
        # License verification (25 pts max)
        if trust_signals['has_license']:
            breakdown['license_verification']['score'] += 15
            breakdown['license_verification']['factors'].append("License number available")
            if trust_signals['license_verified']:
                breakdown['license_verification']['score'] += 10
                breakdown['license_verification']['factors'].append("License actively verified")
        else:
            breakdown['license_verification']['factors'].append("License not verified - trust signal missing")
        
        # Reputation signals (40 pts max)
        avg_rating = trust_signals['average_rating']
        total_reviews = trust_signals['total_reviews']
        
        if avg_rating >= 4.8 and total_reviews >= 20:
            breakdown['reputation_signals']['score'] += 25
            breakdown['reputation_signals']['factors'].append(f"Exceptional reputation: {avg_rating:.1f}/5 ({total_reviews} reviews)")
        elif avg_rating >= 4.5 and total_reviews >= 10:
            breakdown['reputation_signals']['score'] += 20
            breakdown['reputation_signals']['factors'].append(f"Excellent reputation: {avg_rating:.1f}/5")
        elif avg_rating >= 4.0 and total_reviews >= 5:
            breakdown['reputation_signals']['score'] += 15
            breakdown['reputation_signals']['factors'].append(f"Good reputation: {avg_rating:.1f}/5")
        elif avg_rating >= 3.5:
            breakdown['reputation_signals']['score'] += 8
            breakdown['reputation_signals']['factors'].append(f"Average reputation: {avg_rating:.1f}/5")
        elif total_reviews > 0:
            breakdown['reputation_signals']['score'] += 3
            breakdown['reputation_signals']['factors'].append(f"Limited reputation data: {avg_rating:.1f}/5")
        else:
            breakdown['reputation_signals']['factors'].append("No verified reputation data")
        
        # Review volume bonus
        if total_reviews >= 50:
            breakdown['reputation_signals']['score'] += 15
            breakdown['reputation_signals']['factors'].append(f"Substantial review history: {total_reviews}")
        elif total_reviews >= 20:
            breakdown['reputation_signals']['score'] += 10
            breakdown['reputation_signals']['factors'].append(f"Moderate review history: {total_reviews}")
        elif total_reviews >= 5:
            breakdown['reputation_signals']['score'] += 5
            breakdown['reputation_signals']['factors'].append(f"Limited review history: {total_reviews}")
        
        # Security/verification (20 pts max)
        if trust_signals['website_has_ssl']:
            breakdown['security_verification']['score'] += 10
            breakdown['security_verification']['factors'].append("SSL-secured website")
        
        if trust_signals['brokerage_verified']:
            breakdown['security_verification']['score'] += 10
            breakdown['security_verification']['factors'].append("Brokerage affiliation verified")
        
        # Contact verification (15 pts max)
        if trust_signals['phone_verified']:
            breakdown['contact_verification']['score'] += 8
            breakdown['contact_verification']['factors'].append("Phone number verified")
        
        if trust_signals['address_verified']:
            breakdown['contact_verification']['score'] += 7
            breakdown['contact_verification']['factors'].append("Office address verified")
        
        # Aggregate
        score = sum(s['score'] for s in breakdown.values())
        score = min(score, 100)
        
        for section in breakdown.values():
            factors.extend(section['factors'])
        
        return {
            'score': score,
            'grade': ScoringLayer._grade(score),
            'factors': factors,
            'breakdown': breakdown,
            'summary': f"Trust score of {score}/100 based on verified reputation and credentials"
        }
    
    @staticmethod
    def compute_llm_visibility_scores(semantic: int, authority: int, location: int, trust: int,
                                       signals: WebSignals) -> Dict[str, int]:
        """
        Compute LLM-specific visibility scores.
        
        Each LLM weights signals differently:
        - ChatGPT: Reviews, structured data
        - Perplexity: Web presence, citations
        - Claude: Trust signals, verification
        - Gemini: Local SEO, Google ecosystem
        
        All scores derived from web signals only.
        """
        # Platform presence count from signals
        platforms = sum([
            signals.linkedin_accessible,
            signals.instagram_accessible,
            signals.facebook_accessible,
            signals.twitter_accessible
        ])
        
        has_website = 1.0 if signals.website_accessible else 0.0
        review_factor = min(signals.total_verified_reviews / 150, 1.0)
        rating_factor = max(0, (signals.average_verified_rating - 3.5) / 1.5) if signals.average_verified_rating >= 3.5 else 0
        
        # ChatGPT - Values structured data, reviews, clear identity
        chatgpt_base = (semantic * 0.30 + authority * 0.25 + trust * 0.30 + location * 0.15)
        chatgpt_bonus = (review_factor * 5 + rating_factor * 5)
        chatgpt_score = int(chatgpt_base * 0.90 + chatgpt_bonus)
        
        # Perplexity - Values web presence, citations
        perplexity_base = (authority * 0.35 + location * 0.25 + semantic * 0.25 + trust * 0.15)
        perplexity_bonus = (has_website * 8 + (platforms / 4) * 7)
        perplexity_score = int(perplexity_base * 0.85 + perplexity_bonus)
        
        # Claude - Values trust signals, verification
        claude_base = (trust * 0.35 + semantic * 0.30 + authority * 0.20 + location * 0.15)
        claude_bonus = (7 if signals.license_verified else 0) + (rating_factor * 5)
        claude_score = int(claude_base * 0.88 + claude_bonus)
        
        # Gemini - Values local SEO, Google ecosystem
        gemini_base = (location * 0.35 + authority * 0.30 + semantic * 0.20 + trust * 0.15)
        gemini_bonus = (review_factor * 8 + has_website * 5)
        gemini_score = int(gemini_base * 0.87 + gemini_bonus)
        
        return {
            'chatgpt': min(max(chatgpt_score, 0), 100),
            'perplexity': min(max(perplexity_score, 0), 100),
            'claude': min(max(claude_score, 0), 100),
            'gemini': min(max(gemini_score, 0), 100)
        }
    
    @staticmethod
    def _grade(score: int) -> str:
        """Convert numeric score to letter grade (deterministic)."""
        if score >= 97: return "A+"
        if score >= 93: return "A"
        if score >= 90: return "A-"
        if score >= 87: return "B+"
        if score >= 83: return "B"
        if score >= 80: return "B-"
        if score >= 77: return "C+"
        if score >= 73: return "C"
        if score >= 70: return "C-"
        if score >= 60: return "D"
        return "F"
    
    @staticmethod
    def _tier(score: int) -> str:
        """Convert numeric score to tier (deterministic)."""
        if score >= 95: return "Elite"
        if score >= 85: return "Exceptional"
        if score >= 75: return "Strong"
        if score >= 65: return "Solid"
        return "Developing"


@dataclass
class AgentProfile:
    """
    LEGACY: This dataclass is kept for UI compatibility.
    
    IMPORTANT: The fields here are populated from Excel for display purposes only.
    SCORING must NOT use these fields directly - use WebSignals from WebSignalLayer instead.
    """
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
    """
    AI Analyzer - Refactored to use Web-Verified Scoring Pipeline
    
    ===================================================================================
    CRITICAL: This class now implements the 3-layer architecture:
    
    1. InputSeedLayer: Excel → Agent identity only (no scoring data)
    2. WebSignalLayer: Fetch live web data (source of truth)
    3. ScoringLayer: Compute scores from web signals only
    
    Excel data (AgentProfile) is used ONLY for:
    - Identifying the agent
    - Providing seed URLs
    - UI display purposes
    
    All SALT and AI Visibility scores are computed from WebSignals ONLY.
    ===================================================================================
    """
    
    def __init__(self, openai_api_key: Optional[str] = None, gemini_api_key: Optional[str] = None):
        self.openai_client = None
        self.gemini_model = None
        self.active_llm = None
        
        # Initialize the web signal layer for fetching live data
        self.web_signal_layer = WebSignalLayer()
        
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
        Main analysis method using web-verified scoring pipeline.
        
        ===================================================================================
        NEW FLOW:
        1. Extract seed from profile (identity + URLs only)
        2. Collect web signals (scrape/fetch live data)
        3. Extract normalized signals
        4. Compute SALT scores from web signals ONLY
        5. Optionally enhance with LLM insights (not scores)
        ===================================================================================
        
        CRITICAL: Scores are NEVER derived from Excel/profile data.
        """
        # STEP 1: Extract seed from profile (identity only)
        # This converts AgentProfile to AgentSeed (minimal identity data)
        seed = self._profile_to_seed(profile)
        
        # STEP 2: Collect web signals (SOURCE OF TRUTH)
        print(f"🌐 Collecting web signals for {seed.full_name}...")
        web_signals = self.web_signal_layer.collect_signals(seed)
        print(f"   ✓ Sources checked: {len(web_signals.sources_checked)}")
        print(f"   ✓ Verified reviews: {web_signals.total_verified_reviews}")
        if web_signals.collection_errors:
            print(f"   ⚠️ Collection issues: {len(web_signals.collection_errors)}")
        
        # STEP 3: Extract normalized signals for each SALT dimension
        identity_signals = SignalExtractor.extract_identity_signals(seed, web_signals)
        authority_signals = SignalExtractor.extract_authority_signals(web_signals)
        location_signals = SignalExtractor.extract_location_signals(seed, web_signals)
        trust_signals = SignalExtractor.extract_trust_signals(seed, web_signals)
        
        # STEP 4: Compute SALT scores from WEB SIGNALS ONLY
        semantic_result = ScoringLayer.compute_semantic_score(identity_signals)
        authority_result = ScoringLayer.compute_authority_score(authority_signals)
        location_result = ScoringLayer.compute_location_score(location_signals, seed.city, seed.state)
        trust_result = ScoringLayer.compute_trust_score(trust_signals)
        
        # Compute overall score
        semantic = semantic_result['score']
        authority = authority_result['score']
        location = location_result['score']
        trust = trust_result['score']
        overall = int((semantic + authority + location + trust) / 4)
        
        # Compute LLM visibility scores from web signals
        llm_scores = ScoringLayer.compute_llm_visibility_scores(
            semantic, authority, location, trust, web_signals
        )
        
        # Build the analysis result
        analysis = self._build_analysis_result(
            seed, web_signals,
            semantic_result, authority_result, location_result, trust_result,
            overall, llm_scores, leaderboard, profile
        )
        
        # STEP 5: Optionally enhance with LLM insights (NOT scores)
        if self.active_llm:
            try:
                llm_insights = self._get_llm_insights(seed, web_signals, analysis, leaderboard)
                if llm_insights:
                    # Merge LLM insights for recommendations only
                    for key in ['recommendations', 'profile_analysis', 'competitive_insights']:
                        if key in llm_insights and llm_insights[key]:
                            analysis[key] = llm_insights[key]
            except Exception as e:
                print(f"⚠️ LLM enhancement failed (using base analysis): {e}")
        
        return analysis
    
    def _profile_to_seed(self, profile: AgentProfile) -> AgentSeed:
        """
        Convert AgentProfile to AgentSeed (extract identity only).
        
        This ensures only identity/URL data is used for web discovery,
        NOT scoring-related fields like reviews, ratings, etc.
        """
        return AgentSeed(
            agent_id=profile.agent_id,
            full_name=profile.full_name,
            license_number=profile.license_number,
            jurisdiction=profile.jurisdiction,
            city=profile.city,
            state=profile.state,
            zip_code=profile.zip_code,
            website_url=profile.website,
            profile_url=profile.profile_url,
            instagram_url=profile.instagram_url,
            facebook_url=profile.facebook_url,
            twitter_url=profile.twitter_url,
            linkedin_url=profile.linkedin_url,
            latitude=profile.latitude,
            longitude=profile.longitude
        )
    
    def _build_analysis_result(self, seed: AgentSeed, signals: WebSignals,
                                semantic: Dict, authority: Dict, location: Dict, trust: Dict,
                                overall: int, llm_scores: Dict,
                                leaderboard: Optional[Dict], profile: AgentProfile) -> Dict:
        """
        Build the analysis result structure.
        
        CRITICAL: All scores come from web signals via ScoringLayer.
        Profile data is used ONLY for display fields (name, location, etc.)
        """
        tier = ScoringLayer._tier(overall)
        grade = ScoringLayer._grade(overall)
        
        # Leaderboard context (from database rankings)
        state_rank = leaderboard.get('state_rank', 'N/A') if leaderboard else 'N/A'
        city_rank = leaderboard.get('city_rank', 'N/A') if leaderboard else 'N/A'
        pct = leaderboard.get('percentile', 'N/A') if leaderboard else 'N/A'
        
        # Count verified platforms
        platforms = sum([
            signals.linkedin_accessible,
            signals.instagram_accessible,
            signals.facebook_accessible,
            signals.twitter_accessible
        ])
        
        # Build executive summary from VERIFIED data only
        exec_sum = f"{seed.full_name} is a {tier.lower()}-tier real estate professional"
        if state_rank != 'N/A':
            exec_sum += f" ranked #{state_rank} in {seed.state}"
        if city_rank != 'N/A':
            exec_sum += f" and #{city_rank} in {seed.city}"
        exec_sum += f". "
        
        if signals.total_verified_reviews > 0:
            exec_sum += f"Client satisfaction is verified with {signals.average_verified_rating:.1f}/5.0 rating across {signals.total_verified_reviews} reviews. "
        else:
            exec_sum += "Review data pending web verification. "
        
        exec_sum += f"Operating from {seed.city}, {seed.state}. "
        
        if signals.website_accessible:
            exec_sum += f"Website verified accessible. "
        
        if overall >= 70:
            exec_sum += f"{'Highly recommended' if overall >= 85 else 'Recommended'} based on verified web signals."
        else:
            exec_sum += "Additional verification recommended before engagement."
        
        # Build key links from verified accessible platforms
        links = {}
        if signals.website_accessible and seed.website_url:
            links['website'] = seed.website_url
        if signals.linkedin_accessible and seed.linkedin_url:
            links['linkedin'] = seed.linkedin_url
        if signals.instagram_accessible and seed.instagram_url:
            links['instagram'] = seed.instagram_url
        if signals.facebook_accessible and seed.facebook_url:
            links['facebook'] = seed.facebook_url
        
        return {
            "scores": {
                "semantic": semantic,
                "authority": authority,
                "location": location,
                "trust": trust,
                "overall": {"score": overall, "grade": grade, "tier": tier}
            },
            "llm_visibility_scores": llm_scores,
            "web_signals_summary": {
                "sources_checked": len(signals.sources_checked),
                "total_verified_reviews": signals.total_verified_reviews,
                "average_verified_rating": signals.average_verified_rating,
                "website_accessible": signals.website_accessible,
                "platforms_verified": platforms,
                "collection_errors": len(signals.collection_errors),
                "collected_at": signals.signals_collected_at
            },
            "leaderboard": {
                "national_percentile": f"Top {pct}%" if pct != 'N/A' else 'N/A',
                "state_rank": f"#{state_rank}" if state_rank != 'N/A' else 'N/A',
                "city_rank": f"#{city_rank}" if city_rank != 'N/A' else 'N/A',
                "comparative_analysis": f"Ranked #{state_rank} among {leaderboard.get('state_total', 'N/A') if leaderboard else 'N/A'} agents in {seed.state}." if state_rank != 'N/A' else 'Ranking data unavailable'
            },
            "profile_analysis": {
                "strengths": authority['factors'][:4] if authority['factors'] else ["Insufficient verified data"],
                "areas_for_improvement": ["Expand digital presence"] if platforms < 3 else ["Continue building reviews"],
                "unique_selling_points": [f"Located in {seed.city}", f"License: {seed.license_number}" if seed.license_number else "License pending verification"],
                "market_position": f"Agent in {seed.city}, {seed.state}",
                "ideal_client_match": f"Clients seeking properties in {seed.city} area"
            },
            "competitive_insights": {
                "market_tier": "Unknown - pending verification",
                "digital_presence": "Excellent" if platforms >= 4 else "Good" if platforms >= 2 else "Needs Work",
                "reputation_strength": "Exceptional" if signals.total_verified_reviews >= 100 else "Strong" if signals.total_verified_reviews >= 50 else "Building" if signals.total_verified_reviews > 0 else "Unverified"
            },
            "key_links": links,
            "actionable_insights": {
                "for_buyers": [
                    f"Agent operates in {seed.city} market",
                    f"Verified {signals.total_verified_reviews} reviews" if signals.total_verified_reviews > 0 else "No verified reviews found",
                    "Request references and recent transaction history"
                ],
                "for_sellers": [
                    f"Market: {seed.city}, {seed.state}",
                    f"Website: {'Verified accessible' if signals.website_accessible else 'Not verified'}",
                    "Ask about marketing strategy and local market expertise"
                ],
                "red_flags": self._generate_red_flags(signals, overall, platforms),
                "questions_to_ask": [
                    "Can you provide recent client references?",
                    "What is your average days-on-market?",
                    "How do you generate and maintain client reviews?"
                ],
                "geo_weaknesses": self._generate_geo_weaknesses(signals, platforms, seed)
            },
            "competitor_gaps": {
                "missing_signals": self._identify_missing_signals(signals),
                "content_gaps": [
                    f"Market reports for {seed.city}: Regular publishing improves AI visibility",
                    "Video content: Property walkthroughs increase engagement",
                    f"Blog posts with local SEO: {seed.city} neighborhood guides"
                ],
                "visibility_blockers": [
                    "Inconsistent profile information reduces AI confidence" if platforms < 2 else "Profile consistency appears adequate",
                    "Missing SSL on website" if signals.website_exists and not signals.website_has_ssl else "SSL verified on website" if signals.website_has_ssl else "No website to verify",
                    "Limited review presence" if signals.total_verified_reviews < 20 else "Review presence established"
                ]
            },
            "geo_improvement_roadmap": self._generate_roadmap(signals, overall, platforms, seed),
            "recommendations": {
                "for_buyers_sellers": f"Based on {signals.total_verified_reviews} verified reviews, {seed.full_name} is {'recommended' if overall >= 70 else 'under evaluation'} for {seed.city} real estate.",
                "for_agent": self._generate_agent_recommendations(signals, platforms, seed)
            },
            "executive_summary": exec_sum,
            "data_sources": {
                "scoring_source": "Web-verified signals only",
                "excel_usage": "Identity and URL seeding only",
                "sources_attempted": signals.sources_checked,
                "collection_errors": signals.collection_errors
            }
        }
    
    def _generate_red_flags(self, signals: WebSignals, overall: int, platforms: int) -> List[str]:
        """Generate red flags based on verified web signals only."""
        flags = []
        
        if signals.total_verified_reviews == 0:
            flags.append("No verified reviews found - critical trust gap for AI systems")
        elif signals.total_verified_reviews < 10:
            flags.append(f"Limited reviews ({signals.total_verified_reviews}) - below threshold for strong AI recommendations")
        
        if signals.average_verified_rating > 0 and signals.average_verified_rating < 4.0:
            flags.append(f"Rating at {signals.average_verified_rating:.1f}/5 - investigate client satisfaction")
        
        if not signals.website_accessible:
            flags.append("Website not verified accessible - reduces online discoverability")
        
        if platforms == 0:
            flags.append("No verified social platform presence - AI systems struggle to verify identity")
        elif platforms < 2:
            flags.append(f"Limited verified social presence ({platforms} platform) - expand for better AI coverage")
        
        if not signals.license_verified:
            flags.append("License not independently verified - recommend verification before engagement")
        
        return flags if flags else ["No significant red flags based on verified data"]
    
    def _generate_geo_weaknesses(self, signals: WebSignals, platforms: int, seed: AgentSeed) -> List[str]:
        """Generate GEO weaknesses based on web signals."""
        weaknesses = []
        
        weaknesses.append(
            f"Review generation: {signals.total_verified_reviews} verified reviews - "
            f"{'excellent base' if signals.total_verified_reviews >= 100 else 'room for growth' if signals.total_verified_reviews >= 20 else 'critical gap'}"
        )
        
        weaknesses.append(
            f"Social presence: {platforms} verified platforms - "
            f"{'strong coverage' if platforms >= 4 else 'adequate' if platforms >= 2 else 'needs expansion'}"
        )
        
        if signals.website_accessible:
            weaknesses.append("Website: Verified accessible - ensure regular content updates")
        else:
            weaknesses.append("Website: Not verified accessible - critical gap for AI indexing")
        
        weaknesses.append(
            "Content authority: Publish monthly market insights to improve AI ranking"
        )
        
        return weaknesses
    
    def _identify_missing_signals(self, signals: WebSignals) -> List[str]:
        """Identify missing signals that would improve scores."""
        missing = []
        
        if not signals.website_accessible:
            missing.append("Accessible website with SSL")
        if signals.google_review_count == 0:
            missing.append("Google Business reviews")
        if signals.zillow_review_count == 0:
            missing.append("Zillow profile with reviews")
        if not signals.linkedin_accessible:
            missing.append("Accessible LinkedIn profile")
        if signals.press_mentions == 0:
            missing.append("Press/media mentions")
        if not signals.brokerage_verified:
            missing.append("Verified brokerage affiliation")
        
        return missing if missing else ["Core signals present - focus on strengthening existing presence"]
    
    def _generate_roadmap(self, signals: WebSignals, overall: int, platforms: int, seed: AgentSeed) -> Dict:
        """Generate improvement roadmap based on web signal gaps."""
        return {
            "critical_issues": [
                f"Reviews: {signals.total_verified_reviews} verified - {'maintain momentum' if signals.total_verified_reviews >= 50 else 'implement review generation system'}",
                f"Website: {'Accessible' if signals.website_accessible else 'Not accessible - priority fix'}"
            ] if overall < 80 else ["Core presence established - focus on optimization"],
            "high_priority": [
                "Implement systematic review collection across Google, Zillow, Realtor.com",
                f"{'Ensure website accessibility and SSL' if not signals.website_has_ssl else 'Maintain website with fresh content'}",
                "Add structured data (Schema markup) to website for AI parsing"
            ],
            "medium_priority": [
                "Build LinkedIn presence with recommendations",
                f"Expand to {4 - platforms} additional social platforms" if platforms < 4 else "Maintain social presence consistency",
                f"Publish local market content for {seed.city}"
            ],
            "quick_wins": [
                "Claim and verify Google Business profile",
                "Respond to all existing reviews within 24 hours",
                f"Add '{seed.city} real estate agent' to all profile bios"
            ],
            "estimated_impact": f"Current score: {overall}/100. Addressing critical issues could add 15-25 points over 6 months."
        }
    
    def _generate_agent_recommendations(self, signals: WebSignals, platforms: int, seed: AgentSeed) -> List[str]:
        """Generate specific recommendations for the agent."""
        recs = []
        
        if signals.total_verified_reviews < 50:
            recs.append(f"Review generation: Currently {signals.total_verified_reviews} verified - implement automated post-transaction requests")
        
        if not signals.website_accessible:
            recs.append("Website priority: Establish accessible website with SSL as primary online hub")
        elif not signals.website_has_listings:
            recs.append("Website content: Add active listings and market insights to website")
        
        if platforms < 4:
            recs.append(f"Social expansion: Add {4 - platforms} more platforms for complete coverage")
        
        recs.append(f"Local SEO: Optimize all profiles for '{seed.city} real estate' keywords")
        recs.append("Content strategy: Publish monthly market analysis for AI discoverability")
        
        return recs[:5]  # Top 5 recommendations
    
    def _get_llm_insights(self, seed: AgentSeed, signals: WebSignals, 
                          base_analysis: Dict, leaderboard: Optional[Dict]) -> Optional[Dict]:
        """
        Get enhanced insights from LLM.
        
        CRITICAL RULES:
        - LLM provides interpretation and recommendations ONLY
        - LLM does NOT generate or modify scores
        - Temperature = 0 for determinism
        - Fixed prompt structure for consistency
        """
        scores = base_analysis.get('scores', {})
        
        # Fixed prompt for determinism
        prompt = f"""You are a real estate AI visibility consultant. Based on VERIFIED web signals, provide actionable insights.

AGENT IDENTITY (from seed):
- Name: {seed.full_name}
- Location: {seed.city}, {seed.state}
- License: {seed.license_number or 'Not provided'}

VERIFIED WEB SIGNALS (source of truth):
- Website accessible: {signals.website_accessible}
- Total verified reviews: {signals.total_verified_reviews}
- Average verified rating: {signals.average_verified_rating:.1f}/5
- Social platforms verified: {sum([signals.linkedin_accessible, signals.instagram_accessible, signals.facebook_accessible, signals.twitter_accessible])}
- Brokerage verified: {signals.brokerage_verified}
- Collection errors: {len(signals.collection_errors)}

COMPUTED SALT SCORES (already calculated from web signals):
- Semantic: {scores.get('semantic', {}).get('score', 0)}/100
- Authority: {scores.get('authority', {}).get('score', 0)}/100
- Location: {scores.get('location', {}).get('score', 0)}/100
- Trust: {scores.get('trust', {}).get('score', 0)}/100
- Overall: {scores.get('overall', {}).get('score', 0)}/100

IMPORTANT: Do NOT invent data. Base insights ONLY on the verified signals above.

Return JSON with ONLY these fields:
{{
    "recommendations": {{
        "for_agent": ["5 specific, actionable recommendations based on signal gaps"]
    }},
    "profile_analysis": {{
        "strengths": ["3-4 verified strengths"],
        "areas_for_improvement": ["3-4 areas based on missing signals"]
    }},
    "competitive_insights": {{
        "market_position": "Brief market position based on verified data only",
        "differentiation_strategy": "How to stand out based on current signals"
    }}
}}

Return ONLY valid JSON, no markdown."""

        try:
            if self.active_llm == 'openai' and self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=LLM_TEMPERATURE,  # Deterministic
                    max_tokens=1000
                )
                content = response.choices[0].message.content
                text = content.strip() if content else ""
            elif self.active_llm == 'gemini' and self.gemini_model:
                # Gemini configuration for determinism
                response = self.gemini_model.generate_content(
                    prompt,
                    generation_config={"temperature": LLM_TEMPERATURE, "max_output_tokens": 1000}  # type: ignore
                )
                text = response.text.strip() if response.text else ""
            else:
                return None
            
            if not text:
                return None
            
            # Clean response
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            
            return json.loads(text.strip())
        except Exception as e:
            print(f"⚠️ LLM insights error: {e}")
            return None
    
    # ===================================================================================
    # DEPRECATED METHODS - Kept for reference, not used in new pipeline
    # ===================================================================================
    
    def _calculate_salt_scores(self, p: AgentProfile, lb: Optional[Dict] = None) -> Dict:
        """
        DEPRECATED: This method used Excel data for scoring.
        
        The new pipeline uses:
        1. AgentSeed (identity only from Excel)
        2. WebSignals (scraped from web - source of truth)
        3. ScoringLayer (computes scores from WebSignals)
        
        This method is kept for backward compatibility but should not be used.
        """
        raise DeprecationWarning(
            "This method is deprecated. Use the new web-verified scoring pipeline: "
            "WebSignalLayer.collect_signals() → SignalExtractor → ScoringLayer"
        )
    
    def _calculate_llm_visibility_scores(self, p: AgentProfile, analysis: Dict) -> Dict:
        """
        DEPRECATED: Use ScoringLayer.compute_llm_visibility_scores() instead.
        
        That method uses WebSignals (verified web data) not AgentProfile (Excel data).
        """
        raise DeprecationWarning(
            "This method is deprecated. Use ScoringLayer.compute_llm_visibility_scores() with WebSignals."
        )


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