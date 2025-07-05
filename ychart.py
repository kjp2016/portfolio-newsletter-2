import os
import requests
import pandas as pd
import time

API_KEY = "GgdROA2I2sLyl0VIdJRDjA"
BASE_URL = "https://api.ycharts.com/v3/separate_accounts"
HEADERS = {
    "X-YCHARTSAUTHORIZATION": API_KEY,
    "accept": "application/json"
}

def fetch_separate_accounts(limit=100, retries=3, wait_time=60):
    """
    Fetches separate accounts from the YCharts API.
    Automatically handles rate limit errors by retrying after a wait period.
    """
    for attempt in range(retries):
        try:
            response = requests.get(
                BASE_URL,
                headers=HEADERS,
                params={"limit": limit}
            )
            # Check if the API request was successful
            response.raise_for_status()
            data = response.json()
            
            # Check for API-specific errors in the response
            if "meta" in data and data["meta"].get("status") == "error":
                error_code = data["meta"].get("error_code")
                error_message = data["meta"].get("error_message")
                if error_code == 403:
                    print(f"Rate limit exceeded. Attempt {attempt + 1}/{retries}")
                    if attempt < retries - 1:
                        print(f"Waiting {wait_time} seconds before retrying...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded after {retries} retries.")
                raise Exception(f"API Error: {error_message}")
            
            # Extract accounts data
            accts = data.get("separate_accounts", [])
            if not accts:
                raise ValueError("No accounts data returned.")
            return pd.DataFrame(accts)[["symbol", "name"]]

        except requests.HTTPError as e:
            print(f"HTTP Error: {e}")
        except Exception as e:
            print(f"Error: {e}")
            break
    return pd.DataFrame()  # Return an empty DataFrame on failure

# Fetch and display the separate accounts
df = fetch_separate_accounts()
if not df.empty:
    print("Separate Accounts Data:")
    print(df.head())
else:
    print("No data retrieved or rate limit exceeded.")
