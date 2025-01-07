import pandas as pd
from html2image import Html2Image
from instagrapi import Client
import templates
import os
import schedule
import locale
from datetime import datetime
import requests
import sys

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

## automate in cloud (git ?)
## post facebook
## integrate enhanced bidul.biduleur to directly format the extracted string


def extract_markdown_by_date(csv_file, date):
    # Load data
    df = pd.read_csv(csv_file, sep="|")
    # Filter rows matching the date
    today_data = df[df['date'] == int(date)]
    return today_data


def get_post_text(date):
    return f"""Les dates Bidul du {date} (liste non exhaustive)"""


def get_date_in_french():
    # Mappings for days of the week and months
    days_of_week = {
        0: "lundi",
        1: "mardi",
        2: "mercredi",
        3: "jeudi",
        4: "vendredi",
        5: "samedi",
        6: "dimanche"
    }
    months = {
        1: "janvier",
        2: "février",
        3: "mars",
        4: "avril",
        5: "mai",
        6: "juin",
        7: "juillet",
        8: "août",
        9: "septembre",
        10: "octobre",
        11: "novembre",
        12: "décembre"
    }

    # Get today's date
    today = datetime.now()
    day_name = days_of_week[today.weekday()]  # Get the day of the week
    day = today.day                           # Get the day of the month
    month_name = months[today.month]          # Get the month

    # Format the date in the desired format
    return f"{day_name} {day:02d} {month_name}"


def get_date_info():
    today = datetime.now().strftime("%Y-%m-%d")
    day = datetime.now().strftime("%d")

    date_in_french = get_date_in_french()

    return day, today, date_in_french


def html_to_image(html_content, date, output_image):

    rendered_html = templates.render_template(
        templates.HTML_TEMPLATE_GREEN_GREY_ORANGE,
        content=html_content,
        date=date
    )

    # Render HTML to an image
    hti = Html2Image(output_path='./output/')
    html_output_file_name = os.path.join(OUTPUT_PATH, f"{output_image}.html")
    open(html_output_file_name, 'w+', encoding='utf-8').write(rendered_html)
    return hti.screenshot(html_str=rendered_html, save_as=output_image, size=(1080, 1080))


def post_to_instagram(image_path, caption, username, password):
    if post_to_instagram:
        cl = Client()
        cl.login(username, password)
        cl.photo_upload(image_path, caption)


def main(instagram_post=True):
    day, today, date_in_french = get_date_info()
    # day = "12"
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
    if instagram_post:
        post_to_instagram(output_image_path[0], text_post, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        print(f"Instagram post for {today} published - output file: {output_image_path}")

    print(f"Image Generated for {today} - output file: {output_image_path}")


# # Schedule the task daily at a specific time
# schedule.every().day.at("08:00").do(main)
#
# # Run the scheduler
# while True:
#     schedule.run_pending()
#     time.sleep(1)


if __name__ == "__main__":
    instagram_post = "False" not in sys.argv
    main(instagram_post)
