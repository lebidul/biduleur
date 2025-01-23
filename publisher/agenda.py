import constants
import requests
from biduleur.bidul_parser import parse_bidul
from io import BytesIO
import pandas as pd

def publish_agenda(agenda_url: str = constants.AGENDA_URL, from_remote=True, remote_tapage_url= constants.TAPAGE_URL,
                   tapage_path=constants.CSV_TAPAGE, local_env=False):
    html = agenda_html(from_remote, remote_tapage_url, tapage_path)
    publish()
    return

def agenda_html(from_remote, remote_tapage_url, tapage_path):
    html = ""
    if from_remote:
        get_data_tapage(remote_tapage_url)
    else:
        body = parse_bidul(tapage_path)
    return html

def get_data_tapage(tapage_url):
    # onedrive_url = "https://<onedrive_link>/download"

    # Download the file
    response = requests.get(tapage_url)
    response.raise_for_status()  # Ensure the request was successful

    # Load the file into a pandas DataFrame
    excel_data = pd.ExcelFile(BytesIO(response.content), engine="openpyxl")

    # Access specific sheets
    df = excel_data.parse("biduleur")  # Replace "Sheet1" with your sheet name
    print(df.head())

    return

def publish():
    return
