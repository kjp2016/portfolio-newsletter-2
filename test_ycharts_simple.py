#!/usr/bin/env python3
"""
Simple test script to debug YCharts API connection
"""

import json
from pycharts import CompanyClient

def test_ycharts_connection():
    """Test basic YCharts connection and see actual responses."""
    
    print("Testing YCharts API Connection...")
    print("=" * 50)
    
    # Initialize the client
    api_key = "GgdROA2I2sLyl0VIdJRDjA"
    client = CompanyClient(api_key)
    
    print(f"Using API key: {api_key}")
    print(f"Client base URL: {client.BASE_URL}")
    print(f"Client API version: {client.API_VERSION}")
    
    try:
        print("\n1. Testing get_points with AAPL...")
        response = client.get_points(["AAPL"], ["price"])
        print(f"Response type: {type(response)}")
        print(f"Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        print(f"Full response: {json.dumps(response, indent=2)}")
        
    except Exception as e:
        print(f"Error in get_points: {e}")
        print(f"Error type: {type(e)}")
        
        # Try to get more details about the error
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
    
    try:
        print("\n2. Testing get_info with AAPL...")
        response = client.get_info(["AAPL"], ["name"])
        print(f"Response type: {type(response)}")
        print(f"Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        print(f"Full response: {json.dumps(response, indent=2)}")
        
    except Exception as e:
        print(f"Error in get_info: {e}")
        print(f"Error type: {type(e)}")
        
        # Try to get more details about the error
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
    
    try:
        print("\n3. Testing get_series with AAPL...")
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        response = client.get_series(["AAPL"], ["price"], 
                                   query_start_date=start_date,
                                   query_end_date=end_date)
        print(f"Response type: {type(response)}")
        print(f"Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        print(f"Full response: {json.dumps(response, indent=2)}")
        
    except Exception as e:
        print(f"Error in get_series: {e}")
        print(f"Error type: {type(e)}")
        
        # Try to get more details about the error
        if hasattr(e, 'response'):
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")

if __name__ == "__main__":
    test_ycharts_connection() 