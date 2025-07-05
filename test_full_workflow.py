#!/usr/bin/env python3
"""
Test script to simulate the full portfolio upload workflow.
"""

import streamlit as st
import pandas as pd
import json
import logging
from io import BytesIO
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_test_csv():
    """Create a test CSV file with sample portfolio data."""
    test_data = {
        'Ticker': ['AAPL', 'MSFT', 'GOOGL', 'AMZN'],
        'Shares': [100, 50, 25, 75],
        'Company': ['Apple Inc.', 'Microsoft Corp.', 'Alphabet Inc.', 'Amazon.com Inc.']
    }
    df = pd.DataFrame(test_data)
    return df.to_csv(index=False).encode('utf-8')

def test_csv_extraction():
    """Test CSV file extraction."""
    print("🔍 Testing CSV file extraction...")
    
    try:
        # Create test CSV
        csv_bytes = create_test_csv()
        print(f"✅ Created test CSV ({len(csv_bytes)} bytes)")
        
        # Test extraction
        df = pd.read_csv(BytesIO(csv_bytes))
        print(f"✅ CSV extracted successfully. Shape: {df.shape}")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Data: {df.to_dict('records')}")
        
        return df.to_string()
    except Exception as e:
        print(f"❌ CSV extraction failed: {e}")
        return ""

def test_ai_extraction(content):
    """Test AI portfolio extraction."""
    print("\n🔍 Testing AI portfolio extraction...")
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        
        prompt = f"""
        Analyze the following CSV content and extract stock portfolio information.
        Extract all stock tickers and the number of shares held. Look for:
        - Stock symbols (like AAPL, MSFT, GOOGL, etc.)
        - Company names that can be mapped to tickers
        - Number of shares, quantities, or positions
        Content:
        {content[:4000]}
        Return the data as a JSON object with this exact format:
        {{
            "holdings": [
                {{"ticker": "AAPL", "shares": 100}},
                {{"ticker": "MSFT", "shares": 50}}
            ]
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a financial analyst expert at extracting portfolio data from documents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        potential_holdings = {
            item.get("ticker", "").upper(): float(item.get("shares", 100))
            for item in result.get("holdings", []) if item.get("ticker")
        }
        
        print(f"✅ AI extraction successful. Found holdings: {potential_holdings}")
        return potential_holdings
        
    except Exception as e:
        print(f"❌ AI extraction failed: {e}")
        return {}

def test_google_sheets_save(email, holdings):
    """Test saving to Google Sheets."""
    print(f"\n🔍 Testing Google Sheets save for {email}...")
    
    try:
        # Initialize Google Sheets
        credentials_info = st.secrets["sheets_credentials"]
        creds = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=creds)
        sheets = service.spreadsheets()
        
        SPREADSHEET_ID = "1A9-OWgN_yZvqY-BpzG22-3y9jyy4nrxfQcWJABWanrY"
        SHEET_NAME = "Portfolio_Data"
        
        # Read existing data
        print("   Reading existing data...")
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:D"
        ).execute()
        all_values = result.get('values', [])
        print(f"   Found {len(all_values)} existing rows")
        
        # Prepare new data
        new_values = [all_values[0]] if all_values else [['Email', 'Ticker', 'Shares', 'Last_Updated']]
        for row in all_values[1:]:
            if row and row[0] != email:
                new_values.append(row)
        
        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        for ticker, shares in holdings.items():
            new_values.append([email, ticker, str(shares), timestamp])
        
        print(f"   Preparing to write {len(new_values)} rows...")
        
        # Clear and update
        print("   Clearing existing data...")
        sheets.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:D"
        ).execute()
        
        print("   Writing new data...")
        sheets.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption='RAW',
            body={'values': new_values}
        ).execute()
        
        print("✅ Google Sheets save successful!")
        return True
        
    except HttpError as e:
        print(f"❌ HTTP Error {e.resp.status}: {e}")
        if e.resp.status == 403:
            print("   This is the 403 Forbidden error you're seeing!")
        return False
    except Exception as e:
        print(f"❌ Google Sheets save failed: {e}")
        return False

def test_full_workflow():
    """Test the complete workflow."""
    print("🧪 Full Portfolio Upload Workflow Test")
    print("=" * 60)
    
    # Step 1: CSV Extraction
    content = test_csv_extraction()
    if not content:
        print("❌ Workflow failed at CSV extraction")
        return False
    
    # Step 2: AI Extraction
    holdings = test_ai_extraction(content)
    if not holdings:
        print("❌ Workflow failed at AI extraction")
        return False
    
    # Step 3: Google Sheets Save
    test_email = "test@example.com"
    success = test_google_sheets_save(test_email, holdings)
    
    if success:
        print("\n🎉 Full workflow test completed successfully!")
        return True
    else:
        print("\n❌ Workflow failed at Google Sheets save")
        return False

if __name__ == "__main__":
    success = test_full_workflow()
    
    if success:
        print("\n✅ The full workflow is working correctly!")
        print("   The 403 error might be happening in the Streamlit app due to:")
        print("   - Session state issues")
        print("   - Different execution context")
        print("   - Caching problems")
    else:
        print("\n❌ Workflow test failed. Check the error above.") 