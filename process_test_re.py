"""
Process Test RE.xlsx with Enhanced SALT and GEO Scoring
========================================================

This script processes all agents in Test RE.xlsx and:
1. Scrapes ALL provided URLs (Brokerage, Zillow, Homes.com, Realtor.com, social platforms)
2. Calculates consistent SALT scores (Semantic, Authority, Location, Trust)
3. Generates GEO scores based on location signals
4. Creates comprehensive reports with detailed breakdowns

Usage:
    python process_test_re.py
    python process_test_re.py --output results.json
    python process_test_re.py --gemini-key YOUR_KEY --detailed
"""

import pandas as pd
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import asdict

# Import the enhanced agent intelligence system
from agent_intelligence_v2 import (
    AgentSeed, InputSeedLayer, WebSignalLayer, SignalExtractor, 
    ScoringLayer, WebSignals
)


class TestREProcessor:
    """Process Test RE.xlsx with enhanced SALT and GEO scoring."""
    
    def __init__(self, excel_path: str = "Test RE.xlsx"):
        self.excel_path = excel_path
        self.df = pd.read_excel(excel_path)
        self.web_layer = WebSignalLayer(timeout=15)
        self.results = []
        
        print(f"📂 Loaded {len(self.df)} agents from {excel_path}")
        print(f"📋 Columns: {list(self.df.columns)}")
    
    def process_all_agents(self, detailed: bool = False) -> List[Dict[str, Any]]:
        """Process all agents and generate SALT scores."""
        
        print(f"\n{'='*80}")
        print(f"PROCESSING {len(self.df)} AGENTS")
        print(f"{'='*80}\n")
        
        for idx, row in self.df.iterrows():
            agent_num = idx + 1
            print(f"\n{'─'*80}")
            print(f"[{agent_num}/{len(self.df)}] Processing Agent...")
            print(f"{'─'*80}")
            
            result = self.process_agent(row.to_dict(), detailed=detailed)
            self.results.append(result)
            
            # Print summary
            scores = result['scores']
            print(f"\n✅ {result['agent']['name']}")
            print(f"   Location: {result['agent']['city']}, {result['agent']['state']}")
            print(f"   SALT Scores:")
            print(f"     • Semantic:  {scores['semantic']['score']}/100 ({scores['semantic']['grade']})")
            print(f"     • Authority: {scores['authority']['score']}/100 ({scores['authority']['grade']})")
            print(f"     • Location:  {scores['location']['score']}/100 ({scores['location']['grade']})")
            print(f"     • Trust:     {scores['trust']['score']}/100 ({scores['trust']['grade']})")
            print(f"   Overall: {scores['overall']['score']}/100 ({scores['overall']['grade']}) - {scores['overall']['tier']}")
        
        return self.results
    
    def process_agent(self, record: Dict, detailed: bool = False) -> Dict[str, Any]:
        """Process a single agent record."""
        
        # Step 1: Extract seed data from Excel
        seed = InputSeedLayer.extract_seed(record)
        
        print(f"   Agent: {seed.full_name}")
        print(f"   ID: {seed.agent_id}")
        print(f"   Location: {seed.city}, {seed.state}")
        
        # Count URLs to scrape
        urls_to_check = []
        if seed.website_url: urls_to_check.append(("Website", seed.website_url))
        if seed.zillow_url: urls_to_check.append(("Zillow", seed.zillow_url))
        if seed.homes_url: urls_to_check.append(("Homes.com", seed.homes_url))
        if seed.realtor_url: urls_to_check.append(("Realtor.com", seed.realtor_url))
        if seed.google_business_url: urls_to_check.append(("Google Business", seed.google_business_url))
        if seed.linkedin_url: urls_to_check.append(("LinkedIn", seed.linkedin_url))
        if seed.instagram_url: urls_to_check.append(("Instagram", seed.instagram_url))
        if seed.facebook_url: urls_to_check.append(("Facebook", seed.facebook_url))
        
        print(f"   URLs to scrape: {len(urls_to_check)}")
        for name, url in urls_to_check:
            print(f"     • {name}: {url[:60]}...")
        
        # Step 2: Collect web signals
        print(f"\n   🌐 Scraping web sources...")
        signals = self.web_layer.collect_signals(seed)
        
        # Print collection summary
        print(f"   ✓ Checked {len(signals.sources_checked)} sources")
        if signals.collection_errors:
            print(f"   ⚠️  {len(signals.collection_errors)} errors encountered")
        
        # Step 3: Extract signals for scoring
        identity_signals = SignalExtractor.extract_identity_signals(seed, signals)
        authority_signals = SignalExtractor.extract_authority_signals(signals)
        location_signals = SignalExtractor.extract_location_signals(seed, signals)
        trust_signals = SignalExtractor.extract_trust_signals(seed, signals)
        
        # Step 4: Calculate SALT scores
        print(f"   📊 Calculating SALT scores...")
        semantic_score = ScoringLayer.compute_semantic_score(identity_signals)
        authority_score = ScoringLayer.compute_authority_score(authority_signals)
        location_score = ScoringLayer.compute_location_score(location_signals, seed.city, seed.state)
        trust_score = ScoringLayer.compute_trust_score(trust_signals)
        
        # Calculate overall score
        overall = (semantic_score['score'] + authority_score['score'] + 
                   location_score['score'] + trust_score['score']) / 4
        overall_grade = ScoringLayer._grade(int(overall))
        overall_tier = ScoringLayer._tier(int(overall))
        
        # Step 5: Calculate LLM visibility scores
        llm_scores = ScoringLayer.compute_llm_visibility_scores(
            semantic_score['score'], 
            authority_score['score'], 
            location_score['score'], 
            trust_score['score'],
            signals
        )
        
        # Compile result
        result = {
            'agent': {
                'name': seed.full_name,
                'id': seed.agent_id,
                'license': seed.license_number,
                'city': seed.city,
                'state': seed.state,
                'zip': seed.zip_code,
                'jurisdiction': seed.jurisdiction
            },
            'urls_checked': {
                'website': seed.website_url,
                'zillow': seed.zillow_url,
                'homes': seed.homes_url,
                'realtor': seed.realtor_url,
                'google_business': seed.google_business_url,
                'linkedin': seed.linkedin_url,
                'instagram': seed.instagram_url,
                'facebook': seed.facebook_url
            },
            'scores': {
                'semantic': {
                    'score': semantic_score['score'],
                    'grade': semantic_score['grade'],
                    'factors': semantic_score['factors'] if detailed else None,
                    'breakdown': semantic_score['breakdown'] if detailed else None
                },
                'authority': {
                    'score': authority_score['score'],
                    'grade': authority_score['grade'],
                    'factors': authority_score['factors'] if detailed else None,
                    'breakdown': authority_score['breakdown'] if detailed else None
                },
                'location': {
                    'score': location_score['score'],
                    'grade': location_score['grade'],
                    'factors': location_score['factors'] if detailed else None,
                    'breakdown': location_score['breakdown'] if detailed else None
                },
                'trust': {
                    'score': trust_score['score'],
                    'grade': trust_score['grade'],
                    'factors': trust_score['factors'] if detailed else None,
                    'breakdown': trust_score['breakdown'] if detailed else None
                },
                'overall': {
                    'score': int(overall),
                    'grade': overall_grade,
                    'tier': overall_tier
                },
                'llm_visibility': llm_scores
            },
            'web_signals': {
                'total_reviews': signals.total_verified_reviews,
                'average_rating': signals.average_verified_rating,
                'sources_checked': signals.sources_checked if detailed else len(signals.sources_checked),
                'collection_errors': signals.collection_errors if detailed else len(signals.collection_errors),
                'website_accessible': signals.website_accessible,
                'website_has_ssl': signals.website_has_ssl,
                'social_platforms': {
                    'linkedin': signals.linkedin_accessible,
                    'instagram': signals.instagram_accessible,
                    'facebook': signals.facebook_accessible,
                    'twitter': signals.twitter_accessible
                },
                'review_sources': {
                    'google': {'count': signals.google_review_count, 'rating': signals.google_rating},
                    'zillow': {'count': signals.zillow_review_count, 'rating': signals.zillow_rating},
                    'realtor': {'count': signals.realtor_review_count, 'rating': signals.realtor_rating}
                },
                'listings': {
                    'active': signals.active_listing_count,
                    'sold': signals.sold_listing_count
                }
            },
            'processed_at': datetime.now().isoformat()
        }
        
        return result
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate a summary report of all processed agents."""
        
        if not self.results:
            return {'error': 'No results to summarize'}
        
        # Calculate statistics
        semantic_scores = [r['scores']['semantic']['score'] for r in self.results]
        authority_scores = [r['scores']['authority']['score'] for r in self.results]
        location_scores = [r['scores']['location']['score'] for r in self.results]
        trust_scores = [r['scores']['trust']['score'] for r in self.results]
        overall_scores = [r['scores']['overall']['score'] for r in self.results]
        
        summary = {
            'total_agents': len(self.results),
            'processed_at': datetime.now().isoformat(),
            'statistics': {
                'semantic': {
                    'average': round(sum(semantic_scores) / len(semantic_scores), 2),
                    'min': min(semantic_scores),
                    'max': max(semantic_scores)
                },
                'authority': {
                    'average': round(sum(authority_scores) / len(authority_scores), 2),
                    'min': min(authority_scores),
                    'max': max(authority_scores)
                },
                'location': {
                    'average': round(sum(location_scores) / len(location_scores), 2),
                    'min': min(location_scores),
                    'max': max(location_scores)
                },
                'trust': {
                    'average': round(sum(trust_scores) / len(trust_scores), 2),
                    'min': min(trust_scores),
                    'max': max(trust_scores)
                },
                'overall': {
                    'average': round(sum(overall_scores) / len(overall_scores), 2),
                    'min': min(overall_scores),
                    'max': max(overall_scores)
                }
            },
            'tier_distribution': {
                'Elite': sum(1 for r in self.results if r['scores']['overall']['tier'] == 'Elite'),
                'Exceptional': sum(1 for r in self.results if r['scores']['overall']['tier'] == 'Exceptional'),
                'Strong': sum(1 for r in self.results if r['scores']['overall']['tier'] == 'Strong'),
                'Solid': sum(1 for r in self.results if r['scores']['overall']['tier'] == 'Solid'),
                'Developing': sum(1 for r in self.results if r['scores']['overall']['tier'] == 'Developing')
            },
            'top_performers': sorted(
                self.results, 
                key=lambda x: x['scores']['overall']['score'], 
                reverse=True
            )[:5]
        }
        
        return summary
    
    def save_results(self, output_path: str = "test_re_results.json"):
        """Save results to JSON file."""
        
        output = {
            'metadata': {
                'source_file': self.excel_path,
                'total_agents': len(self.results),
                'processed_at': datetime.now().isoformat(),
                'version': 'Enhanced SALT Scoring v2.0'
            },
            'summary': self.generate_summary_report(),
            'agents': self.results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"\n✅ Results saved to: {output_path}")
        return output_path


def main():
    parser = argparse.ArgumentParser(description='Process Test RE.xlsx with enhanced SALT scoring')
    parser.add_argument('--input', '-i', default='Test RE.xlsx', help='Input Excel file')
    parser.add_argument('--output', '-o', default='test_re_results.json', help='Output JSON file')
    parser.add_argument('--detailed', '-d', action='store_true', help='Include detailed breakdowns')
    args = parser.parse_args()
    
    # Check if input file exists
    if not Path(args.input).exists():
        print(f"❌ Error: File not found: {args.input}")
        return
    
    # Process all agents
    processor = TestREProcessor(args.input)
    processor.process_all_agents(detailed=args.detailed)
    
    # Save results
    output_path = processor.save_results(args.output)
    
    # Print summary
    summary = processor.generate_summary_report()
    print(f"\n{'='*80}")
    print(f"SUMMARY REPORT")
    print(f"{'='*80}")
    print(f"\nTotal Agents Processed: {summary['total_agents']}")
    print(f"\nAverage Scores:")
    print(f"  • Semantic:  {summary['statistics']['semantic']['average']}/100")
    print(f"  • Authority: {summary['statistics']['authority']['average']}/100")
    print(f"  • Location:  {summary['statistics']['location']['average']}/100")
    print(f"  • Trust:     {summary['statistics']['trust']['average']}/100")
    print(f"  • Overall:   {summary['statistics']['overall']['average']}/100")
    print(f"\nTier Distribution:")
    for tier, count in summary['tier_distribution'].items():
        print(f"  • {tier}: {count} agents")
    print(f"\nTop 5 Performers:")
    for i, agent in enumerate(summary['top_performers'], 1):
        print(f"  {i}. {agent['agent']['name']}: {agent['scores']['overall']['score']}/100 ({agent['scores']['overall']['tier']})")
    print(f"\n{'='*80}")
    print(f"✅ Processing complete! Results saved to: {output_path}")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
