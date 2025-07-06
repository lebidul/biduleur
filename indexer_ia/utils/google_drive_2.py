from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
import os
import pickle

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/drive']

creds = None
if os.path.exists('./utils/token.pickle'):
    with open('./utils/token.pickle', 'rb') as token:
        creds = pickle.load(token)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file('./utils/credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)

    with open('./utils/token.pickle', 'wb') as token:
        pickle.dump(creds, token)

service = build('drive', 'v3', credentials=creds)


# List all files in a folder
def list_files_in_folder(folder_id):
    query = f"'{folder_id}' in parents and trashed=false"
    page_token = None
    all_files = []

    print(f"Querying folder with ID: {folder_id}")

    try:
        while True:
            print("Making API request to list files...")
            results = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, webContentLink)",
                pageToken=page_token
            ).execute()

            files = results.get('files', [])
            if not files:
                print("No files found in the specified folder.")
            else:
                print(f"Found {len(files)} files in the folder.")
                all_files.extend(files)

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        # Sort the files by name
        all_files.sort(key=lambda x: x['name'].lower())

        print(f"Total files retrieved: {len(all_files)}")


    except HttpError as error:
        print(f"An error occurred: {error}")

    return all_files

def upload_file_to_drive(file_path, folder_id, file_name):
    """Upload a file to the specified Google Drive folder"""
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"\n✅ File '{file_name}' uploaded with ID: {file.get('id')}")
    return file.get('webContentLink')
