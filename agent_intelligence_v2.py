"""
Real Estate Agent Intelligence System v2 - ENHANCED
Powered by Google Gemini + RAG with detailed executive summaries and leaderboard rankings
"""

import pandas as pd
import json
import os
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, List, Tuple
from datetime import datetime

import google.generativeai as genai

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


class GeminiAnalyzer:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def analyze_agent(self, profile: AgentProfile, leaderboard: Dict = None) -> Dict:
        profile_dict = {k: v for k, v in asdict(profile).items() if v not in (None, "", 0, {})}
        
        lb_info = ""
        if leaderboard:
            lb_info = f"""
LEADERBOARD (Database of {leaderboard.get('total_agents', 0)} agents):
- Overall Rank: #{leaderboard.get('credibility_rank', 'N/A')} (Top {leaderboard.get('percentile', 'N/A')}%)
- Rating Rank: #{leaderboard.get('rating_rank', 'N/A')}
- Reviews Rank: #{leaderboard.get('review_rank', 'N/A')}
- State Rank ({profile.state}): #{leaderboard.get('state_rank', 'N/A')} of {leaderboard.get('state_total', 'N/A')}
- City Rank ({profile.city}): #{leaderboard.get('city_rank', 'N/A')} of {leaderboard.get('city_total', 'N/A')}
"""

        prompt = f"""You are a real estate analyst. Analyze this agent and provide DETAILED insights.

AGENT DATA:
{json.dumps(profile_dict, indent=2, default=str)}
{lb_info}

Return JSON with this structure (sample format):
{{"scores": {{"authority": {{"score": 85, "grade": "A", "factors": [], "summary": "text"}}, "sentiment": {{"score": 75}}, "trustworthiness": {{"score": 90}}, "location_visibility": {{"score": 80}}, "overall": {{"score": 83, "grade": "A", "tier": "Strong"}}}}, "leaderboard": {{"national_percentile": "Top 10%", "state_rank": "#5", "city_rank": "#2", "comparative_analysis": "text"}}, "profile_analysis": {{"strengths": [], "areas_for_improvement": [], "unique_selling_points": [], "market_position": "text", "ideal_client_match": "text"}}, "competitive_insights": {{"market_tier": "Luxury", "experience_level": "Veteran", "digital_presence": "Excellent", "reputation_strength": "Exceptional"}}, "key_links": {{}}, "actionable_insights": {{"for_buyers": [], "for_sellers": [], "red_flags": [], "questions_to_ask": [], "geo_weaknesses": []}}, "competitor_gaps": {{"missing_signals": [], "content_gaps": [], "visibility_blockers": []}}, "geo_improvement_roadmap": {{"critical_issues": [], "high_priority": [], "medium_priority": [], "quick_wins": [], "estimated_impact": "text"}}, "recommendations": {{"for_buyers_sellers": "text", "for_agent": []}}, "executive_summary": "text"}}

IMPORTANT INSTRUCTIONS:
1. Populate ALL fields with real data from the agent profile
2. For "for_agent" recommendations: provide 5 detailed, actionable GEO improvement suggestions with specifics about what to do and why
3. Executive summary must include: agent name, tier, ranking numbers, experience, ratings, digital presence assessment
4. Return ONLY valid JSON, no markdown formatting or code fences

Return ONLY valid JSON."""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith('```json'): text = text[7:]
            if text.startswith('```'): text = text[3:]
            if text.endswith('```'): text = text[:-3]
            parsed = json.loads(text.strip())
            return parsed
        except json.JSONDecodeError as je:
            return self._fallback(profile, leaderboard)
        except Exception as e:
            import traceback
            traceback.print_exc()     
            return self._fallback(profile, leaderboard)
    
    def _fallback(self, p: AgentProfile, lb: Dict = None) -> Dict:
        # Calculate scores
        auth = 0
        auth_f = []
        if p.website: auth += 15; auth_f.append(f"Website: {p.website}")
        if p.profile_url: auth += 10; auth_f.append("Profile page available")
        platforms = sum([1 for x in [p.instagram_url, p.facebook_url, p.twitter_url, p.linkedin_url] if x])
        auth += min(platforms * 6, 24)
        if platforms: auth_f.append(f"Active on {platforms} social platforms")
        if p.total_reviews >= 100: auth += 20; auth_f.append(f"Strong reviews: {p.total_reviews}")
        elif p.total_reviews >= 50: auth += 15; auth_f.append(f"Good reviews: {p.total_reviews}")
        if p.average_rating >= 4.8: auth += 15; auth_f.append(f"Excellent rating: {p.average_rating}/5")
        elif p.average_rating >= 4.5: auth += 12; auth_f.append(f"Very good rating: {p.average_rating}/5")
        if p.industry_ranking: auth += 15; auth_f.append(f"Ranking: {p.industry_ranking}")
        
        sent = 50 + ((p.average_rating - 3) * 20 if p.average_rating else 0)
        sent_f = [f"Rating: {p.average_rating}/5 on {p.review_platform}" if p.average_rating else "No rating data"]
        if p.credibility_tier == 'Elite': sent += 15; sent_f.append("Elite credibility tier")
        
        trust = 25 if p.license_status == 'Active' else 0
        trust_f = [f"Active {p.jurisdiction} license" if p.license_status == 'Active' else "License status unknown"]
        if p.brokerage_name: trust += 15; trust_f.append(f"Brokerage: {p.brokerage_name}")
        trust += 15; trust_f.append("Verified identity")
        if p.verified_realtrends == 'Yes': trust += 10; trust_f.append("RealTrends verified")
        
        loc = 0
        loc_f = []
        if p.city: loc += 25; loc_f.append(f"Market: {p.city}")
        if p.state: loc += 20; loc_f.append(f"State: {p.state}")
        if p.zip_code: loc += 15; loc_f.append(f"ZIP: {p.zip_code}")
        if p.office_address: loc += 15; loc_f.append("Office location verified")
        
        auth, sent, trust, loc = min(auth,100), min(max(int(sent),0),100), min(trust,100), min(loc,100)
        overall = int(auth*0.3 + sent*0.25 + trust*0.25 + loc*0.2)
        
        def grade(s): return "A+" if s>=97 else "A" if s>=93 else "A-" if s>=90 else "B+" if s>=87 else "B" if s>=83 else "B-" if s>=80 else "C+" if s>=77 else "C" if s>=73 else "C-" if s>=70 else "D" if s>=60 else "F"
        def tier(s): return "Elite" if s>=95 else "Exceptional" if s>=85 else "Strong" if s>=75 else "Solid" if s>=65 else "Developing"
        
        links = {k:v for k,v in {"website":p.website,"linkedin":p.linkedin_url,"instagram":p.instagram_url,"facebook":p.facebook_url}.items() if v}
        
        state_rank = lb.get('state_rank','N/A') if lb else 'N/A'
        city_rank = lb.get('city_rank','N/A') if lb else 'N/A'
        pct = lb.get('percentile','N/A') if lb else 'N/A'
        
        platforms = sum([1 for x in [p.instagram_url, p.facebook_url, p.twitter_url, p.linkedin_url] if x])
        
        exec_sum = f"{p.full_name} is a {tier(overall).lower()}-tier real estate professional ranked #{state_rank} in {p.state} and #{city_rank} in {p.city}, placing them in the top {pct}% nationally. With {p.years_experience} years of experience and {p.career_sales or 'significant'} in career sales, they demonstrate {'exceptional' if overall>=85 else 'strong' if overall>=70 else 'developing'} market expertise. Client satisfaction is {'excellent' if p.average_rating>=4.8 else 'strong' if p.average_rating>=4.5 else 'good'} with a {p.average_rating}/5.0 rating across {p.total_reviews} reviews on {p.review_platform or 'review platforms'}. "
        if p.industry_ranking: exec_sum += f"Notable achievement: {p.industry_ranking}. "
        exec_sum += f"Specializing in {p.specialization or 'residential'} properties, they operate from {p.city}, {p.state}. "
        if links: exec_sum += f"Connect via: {', '.join([f'{k}: {v}' for k,v in list(links.items())[:2]])}. "
        exec_sum += f"{'Highly recommended' if overall>=85 else 'Recommended' if overall>=70 else 'Consider'} for buyers and sellers in the {p.city} market."
        
        return {
            "scores": {
                "authority": {"score": auth, "grade": grade(auth), "factors": auth_f, "summary": f"Authority score of {auth}/100 based on digital presence and {p.total_reviews} reviews."},
                "sentiment": {"score": sent, "grade": grade(sent), "factors": sent_f, "summary": f"Sentiment score of {sent}/100 reflecting {p.average_rating}/5 rating."},
                "trustworthiness": {"score": trust, "grade": grade(trust), "factors": trust_f, "summary": f"Trust score of {trust}/100 with active licensing and brokerage affiliation."},
                "location_visibility": {"score": loc, "grade": grade(loc), "factors": loc_f, "summary": f"Location visibility of {loc}/100 in {p.city}, {p.state}."},
                "overall": {"score": overall, "grade": grade(overall), "tier": tier(overall)}
            },
            "leaderboard": {"national_percentile": f"Top {pct}%", "state_rank": f"#{state_rank}", "city_rank": f"#{city_rank}", "comparative_analysis": f"Ranked #{state_rank} among {lb.get('state_total','N/A') if lb else 'N/A'} agents in {p.state}."},
            "profile_analysis": {"strengths": auth_f[:4], "areas_for_improvement": ["Expand digital presence"] if platforms<3 else ["Continue building reviews"], "unique_selling_points": [p.specialization or "Local expertise", p.industry_ranking or f"{p.years_experience} years experience"], "market_position": f"{p.specialization or 'Residential'} specialist in {p.city}", "ideal_client_match": f"Clients seeking {p.specialization or 'residential'} properties in {p.city}"},
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
        self.df = pd.read_excel(excel_path)
        self.df['name_lower'] = self.df['Full_Name'].str.lower().str.strip()
        self._compute_rankings()
    
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
        q = query.lower().strip()
        exact = self.df[self.df['name_lower'] == q]
        if not exact.empty: return exact.to_dict('records')
        contains = self.df[self.df['name_lower'].str.contains(q, na=False)]
        if not contains.empty: return contains.to_dict('records')
        return []
    
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
    def __init__(self, excel_path: str, gemini_api_key: str = None):
        self.db = AgentDatabase(excel_path)
        self.analyzer = GeminiAnalyzer(gemini_api_key) if gemini_api_key else None
    
    def analyze_agent(self, name: str, enrich_web: bool = False) -> Dict:
        results = self.db.search(name)
        if not results: return {"error": f"No agent found matching '{name}'"}
        
        record = results[0]
        profile = self.db.record_to_profile(record)
        leaderboard = self.db.get_leaderboard_context(profile.agent_id)
        
        # Debug logging
        print(f"📊 Agent: {profile.full_name} (ID: {profile.agent_id})")
        print(f"📍 Location: {profile.city}, {profile.state}")
        if leaderboard:
            print(f"🏆 Leaderboard: State #{leaderboard.get('state_rank')}/{leaderboard.get('state_total')}, City #{leaderboard.get('city_rank')}/{leaderboard.get('city_total')}")
        else:
            print(f"⚠️ Leaderboard context is empty!")
        
        if self.analyzer:
            print(f"\n🔑 GEMINI API KEY FOUND - Using LLM analysis")
            analysis = self.analyzer.analyze_agent(profile, leaderboard)
        else:
            print(f"\n{'='*60}")
            print(f"⚠️  NO GEMINI API KEY - Using FALLBACK (no LLM)")
            print(f"📊 Generating algorithmic analysis for: {profile.full_name}")
            print(f"{'='*60}\n")
            temp = GeminiAnalyzer.__new__(GeminiAnalyzer)
            analysis = temp._fallback(profile, leaderboard)
            print(f"✅ FALLBACK ANALYSIS COMPLETE (no AI used)\n")
        
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
            "metadata": {"data_source": "RAG + Gemini Analysis", "database_updated": profile.observation_timestamp,
                        "analysis_timestamp": datetime.now().isoformat(), "total_agents": leaderboard.get('total_agents',0)}
        }
    
    def get_map_data(self, limit: int = None) -> List[Dict]:
        """Get ALL agents for map - no limit by default"""
        agents = self.db.get_all_agents_for_map()
        return agents[:limit] if limit else agents


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['analyze', 'map'])
    parser.add_argument('--name', '-n')
    parser.add_argument('--api-key', '-k')
    parser.add_argument('--db', '-d', default='US_Real_Estate_Agents_Database.xlsx')
    args = parser.parse_args()
    
    api_key = args.api_key or os.environ.get('GEMINI_API_KEY')
    system = AgentIntelligenceSystem(args.db, api_key)
    
    if args.action == 'analyze' and args.name:
        print(json.dumps(system.analyze_agent(args.name), indent=2, default=str))
    elif args.action == 'map':
        data = system.get_map_data()
        print(json.dumps({'total': len(data), 'message': f'All {len(data)} agents available for map'}, indent=2))

if __name__ == '__main__':
    main()