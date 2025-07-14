#!/usr/bin/env python3
"""
Test script to verify the optimized system is properly integrated into production
"""

import logging
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

def test_main_import():
    """Test that the optimized main.py can be imported correctly"""
    print("=== Testing Main.py Import ===")
    
    try:
        from main import generate_newsletter_for_user, OptimizedNewsletterGenerator
        print("✅ Successfully imported optimized functions from main.py")
        
        # Test that the OptimizedNewsletterGenerator class exists
        generator = OptimizedNewsletterGenerator()
        print("✅ Successfully created OptimizedNewsletterGenerator instance")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_portfolio_analysis_import():
    """Test that portfolio_analysis.py still works"""
    print("\n=== Testing Portfolio Analysis Import ===")
    
    try:
        from portfolio_analysis import get_batch_stock_data, get_batch_price_performance
        print("✅ Successfully imported portfolio analysis functions")
        return True
    except Exception as e:
        print(f"❌ Portfolio analysis import failed: {e}")
        return False

def test_alpha_vantage_import():
    """Test that alpha_vantage_service.py still works"""
    print("\n=== Testing Alpha Vantage Import ===")
    
    try:
        from alpha_vantage_service import get_alpha_vantage_service
        service = get_alpha_vantage_service()
        print("✅ Successfully imported Alpha Vantage service")
        return True
    except Exception as e:
        print(f"❌ Alpha Vantage import failed: {e}")
        return False

def test_optimized_functionality():
    """Test the optimized functionality with a small portfolio"""
    print("\n=== Testing Optimized Functionality ===")
    
    try:
        from main import OptimizedNewsletterGenerator
        
        # Create test portfolio
        test_portfolio = {
            "AAPL": 10,
            "MSFT": 15,
            "GOOGL": 5
        }
        
        # Create generator
        generator = OptimizedNewsletterGenerator()
        
        # Test data fetching
        print("Testing optimized data fetching...")
        result = generator.get_portfolio_data_efficiently(tuple(test_portfolio.keys()), test_portfolio)
        
        print(f"✅ Data fetch successful: {result['success_rate']:.1f}% success rate")
        print(f"💰 Portfolio change: {result['portfolio_performance']['overall_change_pct']:.2f}%")
        
        if result['performance_data']:
            # Test AI analysis
            print("Testing optimized AI analysis...")
            ticker = list(result['performance_data'].keys())[0]
            price_data = result['performance_data'][ticker]
            company_name = result['company_data'][ticker]['company_name']
            
            analysis = generator.generate_ai_analysis_with_correct_data(ticker, price_data, company_name)
            print(f"✅ AI analysis generated for {ticker}")
            print(f"Analysis preview: {analysis[:100]}...")
        
        return True
    except Exception as e:
        print(f"❌ Optimized functionality test failed: {e}")
        logging.error(f"Test error: {e}", exc_info=True)
        return False

def test_app_integration():
    """Test that the app.py can still import the main functions"""
    print("\n=== Testing App Integration ===")
    
    try:
        # Test that app.py can import the necessary functions
        from main import generate_newsletter_for_user
        from portfolio_analysis import get_batch_stock_data
        from google_sheets_storage import save_user_portfolio_to_sheets
        
        print("✅ App.py can import all necessary functions")
        return True
    except Exception as e:
        print(f"❌ App integration test failed: {e}")
        return False

def main():
    """Run all integration tests"""
    print("🚀 Testing Production Integration")
    print("=" * 50)
    
    tests = [
        test_main_import,
        test_portfolio_analysis_import,
        test_alpha_vantage_import,
        test_optimized_functionality,
        test_app_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"✅ Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Production integration is ready.")
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    main() 