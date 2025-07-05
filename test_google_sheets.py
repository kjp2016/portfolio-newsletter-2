#!/usr/bin/env python3
"""
Test script to diagnose Google Sheets API connection issues.
"""

import streamlit as st
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_google_sheets_connection():
    """Test Google Sheets API connection and permissions."""
    print("🔍 Testing Google Sheets API Connection...")
    
    try:
        # Test 1: Check if secrets are available
        print("\n1. Checking Streamlit secrets...")
        try:
            credentials_info = st.secrets["sheets_credentials"]
            print("✅ Sheets credentials found in Streamlit secrets")
        except Exception as e:
            print(f"❌ Error accessing sheets_credentials: {e}")
            return False
        
        # Test 2: Initialize credentials
        print("\n2. Initializing service account credentials...")
        try:
            creds = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            print("✅ Service account credentials created successfully")
        except Exception as e:
            print(f"❌ Error creating credentials: {e}")
            return False
        
        # Test 3: Build service
        print("\n3. Building Google Sheets service...")
        try:
            service = build('sheets', 'v4', credentials=creds)
            sheets = service.spreadsheets()
            print("✅ Google Sheets service built successfully")
        except Exception as e:
            print(f"❌ Error building service: {e}")
            return False
        
        # Test 4: Test spreadsheet access
        print("\n4. Testing spreadsheet access...")
        SPREADSHEET_ID = "1A9-OWgN_yZvqY-BpzG22-3y9jyy4nrxfQcWJABWanrY"
        try:
            result = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
            print(f"✅ Successfully accessed spreadsheet: {result.get('properties', {}).get('title', 'Unknown')}")
        except HttpError as e:
            if e.resp.status == 403:
                print("❌ 403 Forbidden - Service account doesn't have permission to access this spreadsheet")
                print("   Please check:")
                print("   - The service account email has been added as an editor to the spreadsheet")
                print("   - The spreadsheet ID is correct")
                print("   - The Google Sheets API is enabled in Google Cloud Console")
            elif e.resp.status == 404:
                print("❌ 404 Not Found - Spreadsheet doesn't exist or ID is incorrect")
            else:
                print(f"❌ HTTP Error {e.resp.status}: {e}")
            return False
        except Exception as e:
            print(f"❌ Error accessing spreadsheet: {e}")
            return False
        
        # Test 5: Test reading from sheet
        print("\n5. Testing sheet reading...")
        try:
            result = sheets.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range="Portfolio_Data!A1:D1"
            ).execute()
            values = result.get('values', [])
            print(f"✅ Successfully read from sheet. Found {len(values)} rows")
        except Exception as e:
            print(f"❌ Error reading from sheet: {e}")
            return False
        
        print("\n🎉 All Google Sheets tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Google Sheets Connection Test")
    print("=" * 50)
    
    success = test_google_sheets_connection()
    
    if success:
        print("\n✅ Google Sheets is properly configured!")
    else:
        print("\n❌ Google Sheets configuration needs attention.")
        print("\n📋 Troubleshooting steps:")
        print("1. Enable Google Sheets API in Google Cloud Console")
        print("2. Create a service account and download credentials")
        print("3. Add service account email as editor to the spreadsheet")
        print("4. Update .streamlit/secrets.toml with the credentials") 