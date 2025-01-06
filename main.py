import pandas as pd
from html2image import Html2Image
from instagrapi import Client
import templates
import os
import schedule
import locale
from datetime import datetime
import requests

# Configuration
CSV_FILE = "./sample/202501_tapage_biduleur_janvier_2025.csv.md.tsv"
OUTPUT_IMAGE = "output_image.png"
OUTPUT_PATH = "./output/"
INSTAGRAM_USERNAME = "le_bidul_72"
INSTAGRAM_PASSWORD = "Cucarach@1997"

# Facebook API credentials
ACCESS_TOKEN = "your_page_access_token"
PAGE_ID = "your_page_id"


# Image and message details
IMAGE_PATH = "path_to_your_image.jpg"  # Path to the image
MESSAGE = "Your message for the Facebook post."


# Upload the image to Facebook
def upload_image_to_facebook(page_id, access_token, image_path, message):
    url = f"https://graph.facebook.com/v17.0/{page_id}/photos"
    with open(image_path, "rb") as image_file:
        files = {"source": image_file}
        data = {"access_token": access_token, "message": message}
        response = requests.post(url, files=files, data=data)

    # Handle the response
    if response.status_code == 200:
        print("Image posted successfully!")
        print("Post ID:", response.json().get("post_id"))
    else:
        print("Error posting image:", response.json())

# Call the function to post the image
upload_image_to_facebook(PAGE_ID, ACCESS_TOKEN, IMAGE_PATH, MESSAGE)

## automate in cloud (git ?)
## post facebook
## integrate enhanced biduleur to directly format the extracted string
## push code to github


def extract_markdown_by_date(csv_file, date):
    # Load data
    df = pd.read_csv(csv_file, sep="|")
    # Filter rows matching the date
    today_data = df[df['date'] == int(date)]
    return today_data


def get_post_text(date):
    return f"""Les dates Bidul du {date} (liste non exhaustive)"""


def get_date_info():
    today = datetime.now().strftime("%Y-%m-%d")
    day = datetime.now().strftime("%d")

    locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
    today_in_french = datetime.now()
    date_in_french = today_in_french.strftime("%A %d %B")

    return day, today, date_in_french


def html_to_image(html_content, date, output_image):

    rendered_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Instagram Image</title>
            <style>
                body {{            
                    margin: 0;
                    padding: 0;
                    height: 100vh;
                    width: 100vw;
                    background-color: #313438;
                    background-position: center;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    position: relative;
                }}
                .text {{
                    color: #5F826B;
                    font-size: 2rem;
                    font-family: Lucida Console;
                    text-shadow: 2px 2px 5px rgba(0, 0, 0, 0.7);
                    text-align: left;
                }}
                .top-left,
                .top-right {{
                    position: absolute;
                    top: 20px;
                    font-family: Lucida Console;
                    font-size: 4rem; 
                    color: #5F826B;
                    text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7);
                }}
                .top-left {{
                    left: 25px;
                }}
                .top-right {{
                    right: 25px;
                    text-align: right;
                }}
            </style>
        </head>
        <body>
            <div class="top-left">Le Bidul<br>{date}</div>
            <div class="text">
                {html_content}
            </div>
        </body>
        </html>
    """

    # Render HTML to an image
    hti = Html2Image(output_path='./output/')
    html_output_file_name = os.path.join(OUTPUT_PATH, f"{output_image}.html")
    open(html_output_file_name, 'w+', encoding='utf-8').write(rendered_html)
    return hti.screenshot(html_str=rendered_html, save_as=output_image, size=(1080, 1080))


def post_to_instagram(image_path, caption, username, password):
    cl = Client()
    cl.login(username, password)
    cl.photo_upload(image_path, caption)


def main():
    day, today, date_in_french = get_date_info()
    day = datetime.now().strftime("%d")
    day = "12"
    data = extract_markdown_by_date(CSV_FILE, day)

    if data.empty:
        print(f"No data found for {today}.")
        return

    # Format data into a string
    # html_text = data.iloc[0]['event']

    html_array = data['event'].values
    html_text = "\n\n".join(html_array)

    # Create image from Markdown
    output_image_path = html_to_image(html_text, date_in_french, OUTPUT_IMAGE)

    # Post to Instagram
    text_post = get_post_text(date_in_french)
    post_to_instagram(output_image_path[0], text_post, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    print(f"Posted update for {today} - output file: {output_image_path}")


# # Schedule the task daily at a specific time
# schedule.every().day.at("08:00").do(main)
#
# # Run the scheduler
# while True:
#     schedule.run_pending()
#     time.sleep(1)


if __name__ == "__main__":
    main()
