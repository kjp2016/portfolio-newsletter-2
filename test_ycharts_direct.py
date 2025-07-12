#!/usr/bin/env python3
"""
Direct test of YCharts API using requests library
"""

import requests
import json

def test_ycharts_direct():
    """Test YCharts API directly with requests library."""
    
    print("Testing YCharts API Directly...")
    print("=" * 50)
    
    api_key = "GgdROA2I2sLyl0VIdJRDjA"
    base_url = "https://api.ycharts.com/v3"
    
    print(f"Using API key: {api_key}")
    print(f"Base URL: {base_url}")
    
    # Test 1: Using X-Api-Key header (as per documentation)
    print("\n1. Testing with X-Api-Key header...")
    headers = {'X-Api-Key': api_key}
    
    try:
        response = requests.get(
            f"{base_url}/companies/AAPL/points",
            params={'calcs': 'price'},
            headers=headers,
            timeout=30
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: {response.text[:500]}...")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response JSON: {json.dumps(data, indent=2)}")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: Using api_key query parameter (as per documentation)
    print("\n2. Testing with api_key query parameter...")
    
    try:
        response = requests.get(
            f"{base_url}/companies/AAPL/points",
            params={'calcs': 'price', 'api_key': api_key},
            timeout=30
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: {response.text[:500]}...")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response JSON: {json.dumps(data, indent=2)}")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 3: Using X-YCHARTSAUTHORIZATION header (as pycharts does)
    print("\n3. Testing with X-YCHARTSAUTHORIZATION header...")
    headers = {'X-YCHARTSAUTHORIZATION': api_key}
    
    try:
        response = requests.get(
            f"{base_url}/companies/AAPL/points",
            params={'calcs': 'price'},
            headers=headers,
            timeout=30
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: {response.text[:500]}...")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response JSON: {json.dumps(data, indent=2)}")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 4: Try the old ycharts.com domain
    print("\n4. Testing with old ycharts.com domain...")
    old_base_url = "https://ycharts.com/api/v3"
    headers = {'X-Api-Key': api_key}
    
    try:
        response = requests.get(
            f"{old_base_url}/companies/AAPL/points",
            params={'calcs': 'price'},
            headers=headers,
            timeout=30
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: {response.text[:500]}...")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response JSON: {json.dumps(data, indent=2)}")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ycharts_direct() 