from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow

# Configurer l'authentification Google Drive
SERVICE_ACCOUNT_FILE = './utils/service_account.json'
SCOPES = ['https://www.googleapis.com/auth/drive.file']
# SCOPES = ['https://www.googleapis.com/auth/drive']
#
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# flow = InstalledAppFlow.from_client_secrets_file('./utils/credentials.json', SCOPES)
# credentials = flow.run_local_server(port=0)

drive_service = build('drive', 'v3', credentials=credentials)

def list_files_in_folder(folder_id):
    query = f"'{folder_id}' in parents and trashed=false"
    page_token = None
    all_files = []

    print(f"Querying folder with ID: {folder_id}")

    try:
        while True:
            print("Making API request to list files...")
            results = drive_service.files().list(
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
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='image/png')
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id,webContentLink'
    ).execute()

    # Return the public URL of the uploaded file
    return uploaded_file.get('webContentLink')
