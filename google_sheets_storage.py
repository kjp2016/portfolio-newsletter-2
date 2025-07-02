import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
from typing import Dict, List, Any, Optional
import logging

# Hardcoded Google Sheets Configuration
SPREADSHEET_ID = "1A9-OWgN_yZvqY-BpzG22-3y9jyy4nrxfQcWJABWanrY"
SHEET_NAME = "Portfolio_Data"

@st.cache_resource
def get_google_sheets_client():
    """Initialize Google Sheets API client."""
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["sheets_credentials"],
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

def init_google_sheet():
    """Initialize Google Sheet with headers if needed."""
    sheets = get_google_sheets_client()
    if not sheets:
        logging.error("Failed to initialize Google Sheets client.")
        return False
    try:
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1:D1"
        ).execute()
        values = result.get('values', [])
        if not values:
            headers = [['Email', 'Ticker', 'Shares', 'Last_Updated']]
            sheets.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A1:D1",
                valueInputOption='RAW',
                body={'values': headers}
            ).execute()
        return True
    except Exception as e:
        logging.error(f"Error initializing Google Sheet: {e}")
        return False

def save_user_portfolio_to_sheets(email: str, holdings: Dict[str, float]) -> bool:
    """Save portfolio to Google Sheets."""
    sheets = get_google_sheets_client()
    if not sheets:
        logging.error("Failed to initialize Google Sheets client.")
        return False
    try:
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:D"
        ).execute()
        all_values = result.get('values', [])
        new_values = [all_values[0]] if all_values else [['Email', 'Ticker', 'Shares', 'Last_Updated']]
        for row in all_values[1:]:
            if row and row[0] != email:
                new_values.append(row)
        timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        for ticker, shares in holdings.items():
            new_values.append([email, ticker, str(shares), timestamp])
        sheets.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:D"
        ).execute()
        sheets.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption='RAW',
            body={'values': new_values}
        ).execute()
        return True
    except Exception as e:
        logging.error(f"Error saving to Google Sheets: {e}")
        return False

def get_user_portfolio_from_sheets(email: str) -> Dict[str, float]:
    """Get user portfolio from Google Sheets."""
    sheets = get_google_sheets_client()
    if not sheets:
        logging.error("Failed to initialize Google Sheets client.")
        return {}
    try:
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:C"
        ).execute()
        values = result.get('values', [])
        holdings = {}
        for row in values[1:]:  # Skip header
            if row and row[0] == email:
                ticker = row[1]
                shares = float(row[2])
                holdings[ticker] = shares
        return holdings
    except Exception as e:
        logging.error(f"Error reading from Google Sheets: {e}")
        return {}

def get_all_users_from_sheets() -> List[Dict[str, Any]]:
    """Get all users from Google Sheets."""
    sheets = get_google_sheets_client()
    if not sheets:
        logging.error("Failed to initialize Google Sheets client.")
        return []
    try:
        result = sheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:D"
        ).execute()
        values = result.get('values', [])
        users = {}
        for row in values[1:]:  # Skip header
            if row:
                email = row[0]
                ticker = row[1]
                shares = float(row[2])
                last_updated = row[3] if len(row) > 3 else ""
                if email not in users:
                    users[email] = {
                        'email': email,
                        'last_updated': last_updated,
                        'holdings': {}
                    }
                users[email]['holdings'][ticker] = shares
        return list(users.values())
    except Exception as e:
        logging.error(f"Error getting users from Google Sheets: {e}")
        return []