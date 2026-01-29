"""
Test Google Places API integration for real estate agent review extraction.

This script tests the new Google Places API functionality with Jay Kilby's data.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_intelligence_v2 import AgentSeed, WebSignalLayer

def test_google_places_api():
    """Test Google Places API with Jay Kilby"""

    print("=" * 80)
    print("Testing Google Places API Integration")
    print("=" * 80)

    # Check if API key is configured
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('GOOGLE_PLACES_API_KEY')
    if not api_key or api_key == '':
        print("\nWARNING: GOOGLE_PLACES_API_KEY not found in .env file")
        print("Please add your Google Places API key to the .env file:")
        print("  GOOGLE_PLACES_API_KEY=your_api_key_here")
        print("\nGet your API key from: https://console.cloud.google.com/apis/credentials")
        print("\nYou need to enable:")
        print("  - Places API")
        print("  - Maps JavaScript API (if not already enabled)")
        return

    print(f"API key found: {api_key[:10]}...{api_key[-4:]}\n")

    # Create test seed for Jay Kilby
    seed = AgentSeed(
        agent_id="test-001",
        full_name="Jay Kilby",
        license_number="",
        jurisdiction="NC",
        city="Durham",
        state="NC",
        zip_code="27701",
        website_url="https://www.zillow.com/profile/Jay-Kilby/",
        zillow_url="https://www.zillow.com/profile/Jay-Kilby/",
        realtor_url="",
        google_business_url=""
    )

    print(f"Testing agent: {seed.full_name}")
    print(f"Location: {seed.city}, {seed.state}\n")

    # Create web signal layer and collect signals
    web_layer = WebSignalLayer(timeout=15)

    print("\n" + "=" * 80)
    print("Collecting Web Signals...")
    print("=" * 80 + "\n")

    signals = web_layer.collect_signals(seed)

    # Display results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    print(f"\nGoogle Reviews:")
    print(f"   Rating: {signals.google_rating}/5.0")
    print(f"   Review Count: {signals.google_review_count}")

    print(f"\nZillow:")
    print(f"   Rating: {signals.zillow_rating}/5.0")
    print(f"   Review Count: {signals.zillow_review_count}")

    print(f"\nTotal Reviews:")
    print(f"   All Platforms: {signals.total_verified_reviews}")
    print(f"   Average Rating: {signals.average_verified_rating}/5.0")

    print(f"\nSentiment Keywords:")
    if signals.sentiment_keywords:
        for keyword, count in signals.sentiment_keywords.items():
            print(f"   {keyword}: {count}")
    else:
        print("   None found")

    print(f"\nSources Checked:")
    for source in signals.sources_checked:
        print(f"   - {source}")

    if signals.collection_errors:
        print(f"\nErrors:")
        for error in signals.collection_errors:
            print(f"   - {error}")

    print("\n" + "=" * 80)
    print("Test Complete!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    test_google_places_api()
