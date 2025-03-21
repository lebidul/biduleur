import json
import requests
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# Load credentials
SERVICE_ACCOUNT_FILE = "credentials.json"  # Replace with your service account JSON file
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Your Google Sheet ID (from the URL)
SPREADSHEET_ID = "your_google_sheet_id_here"  # Replace with your sheet ID
SHEET_NAME = "Sheet1"  # The sheet/tab name


# Authenticate and get access token
def get_access_token():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    request = Request()
    credentials.refresh(request)
    return credentials.token


# Update a specific range in Google Sheets
def update_google_sheet(access_token, values, cell_range="A1"):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{SHEET_NAME}!{cell_range}?valueInputOption=RAW"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {"values": values}

    response = requests.put(url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"Successfully updated Google Sheet at {cell_range}")
    else:
        print(f"Failed to update Google Sheet: {response.text}")


# Main execution
if __name__ == "__main__":
    try:
        access_token = get_access_token()

        # Example data to insert into Google Sheets
        new_data = [
            ["Name", "Age", "City"],
            ["Alice", 25, "New York"],
            ["Bob", 30, "Los Angeles"]
        ]

        # Update Google Sheet
        update_google_sheet(access_token, new_data, "A1")

    except Exception as e:
        print(f"Error: {e}")