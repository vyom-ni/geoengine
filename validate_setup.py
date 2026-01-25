"""
Validation Script for Test RE.xlsx Processing
==============================================

This script validates your setup before running the main processing:
- Checks if required files exist
- Validates Excel file structure
- Tests web scraping capabilities
- Provides recommendations

Run this before process_test_re.py to ensure everything is set up correctly.
"""

import sys
from pathlib import Path

def validate_environment():
    """Check if all required packages are installed."""
    print("Checking Python packages...")
    
    required_packages = {
        'pandas': 'Data processing',
        'requests': 'Web scraping',
        'openpyxl': 'Excel file support',
        'beautifulsoup4': 'HTML parsing (optional but recommended)'
    }
    
    missing = []
    for package, purpose in required_packages.items():
        try:
            __import__(package if package != 'beautifulsoup4' else 'bs4')
            print(f"  [OK] {package} - {purpose}")
        except ImportError:
            print(f"  [MISSING] {package} - {purpose}")
            missing.append(package)
    
    if missing:
        print(f"\nInstall missing packages with:")
        print(f"  pip install {' '.join(missing)}")
        return False
    
    print("\nAll required packages are installed!")
    return True


def validate_files():
    """Check if required files exist."""
    print("\nChecking files...")
    
    required_files = {
        'Test RE.xlsx': 'Input data file',
        'agent_intelligence_v2.py': 'Main scoring engine',
        'process_test_re.py': 'Processing script'
    }
    
    missing = []
    for filename, purpose in required_files.items():
        filepath = Path(filename)
        if filepath.exists():
            print(f"  [OK] {filename} - {purpose}")
        else:
            print(f"  [MISSING] {filename} - {purpose}")
            missing.append(filename)
    
    if missing:
        print(f"\nMissing files: {', '.join(missing)}")
        return False
    
    print("\nAll required files are present!")
    return True


def validate_excel_structure():
    """Validate Excel file has required columns."""
    print("\nValidating Excel structure...")
    
    try:
        import pandas as pd
        df = pd.read_excel('Test RE.xlsx')
        
        print(f"  [OK] File loaded: {len(df)} rows")
        print(f"  [OK] Columns found: {len(df.columns)}")
        
        # Check for key columns
        required_cols = ['Realtor Name', 'Realtor ID']
        url_cols = ['Zillow ', 'Homes', 'Realtor', 'Brokerage', 
                   'Instagram', 'Facebook', 'Linkedin', 'Google business profile']
        
        found_required = [col for col in required_cols if col in df.columns]
        found_urls = [col for col in url_cols if col in df.columns]
        
        print(f"\n  Required columns found: {len(found_required)}/{len(required_cols)}")
        for col in found_required:
            print(f"    - {col}")
        
        print(f"\n  URL columns found: {len(found_urls)}/{len(url_cols)}")
        for col in found_urls:
            # Count non-empty URLs
            non_empty = df[col].notna().sum()
            print(f"    - {col}: {non_empty} agents have URLs")
        
        if len(found_required) < len(required_cols):
            print("\n  [WARNING] Missing required columns")
            print("  The script may still work with alternate column names")
        
        if len(found_urls) < 3:
            print("\n  [WARNING] Few URL columns found")
            print("  More URLs = better scoring. Consider adding more platform links.")
        
        return True
        
    except Exception as e:
        print(f"  [ERROR] Failed to validate Excel: {e}")
        return False


def test_web_scraping():
    """Test if web scraping works."""
    print("\nTesting web scraping capabilities...")
    
    try:
        import requests
        
        # Test a simple request
        response = requests.get('https://httpbin.org/get', timeout=5)
        if response.status_code == 200:
            print("  [OK] Web requests working")
        else:
            print(f"  [WARNING] Web request returned status {response.status_code}")
        
        # Test BeautifulSoup
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            print("  [OK] HTML parsing working")
        except ImportError:
            print("  [WARNING] BeautifulSoup not available")
            print("    The script will use basic regex patterns instead")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Web scraping test failed: {e}")
        print("  Check your internet connection")
        return False
    except Exception as e:
        print(f"  [ERROR] Unexpected error: {e}")
        return False


def print_recommendations():
    """Print recommendations for better results."""
    print("\n" + "="*80)
    print("RECOMMENDATIONS FOR BEST RESULTS")
    print("="*80)
    
    recommendations = [
        ("Ensure all URLs are complete", 
         "Include https:// prefix in Excel for all URLs"),
        
        ("Maximize URL coverage",
         "More URLs per agent = more accurate scoring"),
        
        ("Run during off-peak hours",
         "Some websites may rate-limit during peak traffic"),
        
        ("Review the output JSON",
         "Check 'collection_errors' field to see what failed"),
        
        ("Use --detailed flag",
         "Get detailed breakdowns of score components for analysis"),
        
        ("Process in batches if needed",
         "For very large files, process in batches to avoid timeouts")
    ]
    
    for i, (title, description) in enumerate(recommendations, 1):
        print(f"\n{i}. {title}")
        print(f"   {description}")


def main():
    print("="*80)
    print("VALIDATION CHECK FOR TEST RE.XLSX PROCESSING")
    print("="*80)
    print()
    
    all_valid = True
    
    # Run all validations
    all_valid &= validate_environment()
    all_valid &= validate_files()
    all_valid &= validate_excel_structure()
    all_valid &= test_web_scraping()
    
    print("\n" + "="*80)
    if all_valid:
        print("VALIDATION COMPLETE - READY TO PROCESS")
        print("="*80)
        print("\nYou can now run:")
        print("  python process_test_re.py")
        print("\nOr with options:")
        print("  python process_test_re.py --detailed")
    else:
        print("VALIDATION FAILED - PLEASE FIX ISSUES ABOVE")
        print("="*80)
        sys.exit(1)
    
    print_recommendations()
    print("\n" + "="*80)


if __name__ == '__main__':
    main()
