"""
Quick Test: Verify vieweo.py will now get proper scores
"""
import sys
sys.path.insert(0, '.')

from agent_intelligence_v2 import AgentIntelligenceSystem

print("="*60)
print("TESTING VIEWEO API SCORE GENERATION")
print("="*60)

# Initialize system with Test RE database
system = AgentIntelligenceSystem('US_Real_Estate_Agents_Database2.xlsx')

# Get first agent
test_agent = system.db.df.iloc[0]['Full_Name']
print(f"\nTesting with: {test_agent}")

# Analyze (this is what vieweo.py calls)
result = system.analyze_agent(test_agent)

# Check what scores we get
if 'error' in result:
    print(f"\nERROR: {result['error']}")
else:
    agent = result['agent']
    analysis = result['analysis']
    scores = analysis.get('scores', {})
    
    print(f"\nAgent: {agent['name']}")
    print(f"Location: {agent['location']['city']}, {agent['location']['state']}")
    
    print(f"\nSALT Scores (what vieweo.py will get):")
    print(f"  Semantic:  {scores.get('semantic', {}).get('score', 0)}/100")
    print(f"  Authority: {scores.get('authority', {}).get('score', 0)}/100")
    print(f"  Location:  {scores.get('location', {}).get('score', 0)}/100")
    print(f"  Trust:     {scores.get('trust', {}).get('score', 0)}/100")
    print(f"  Overall:   {scores.get('overall', {}).get('score', 0)}/100")
    print(f"  Tier:      {scores.get('overall', {}).get('tier', 'N/A')}")
    
    # Check web signals
    web_summary = analysis.get('web_signals_summary', {})
    print(f"\nWeb Signals:")
    print(f"  Sources checked: {web_summary.get('sources_checked', 0)}")
    print(f"  Total reviews: {web_summary.get('total_verified_reviews', 0)}")
    print(f"  Website accessible: {web_summary.get('website_accessible', False)}")
    
    print("\n" + "="*60)
    if scores.get('overall', {}).get('score', 0) > 40:
        print("SUCCESS: Scores are being calculated properly!")
    else:
        print("ISSUE: Scores are still too low. Check web scraping.")
    print("="*60)
