from biduleur.csv_utils import parse_bidul_event
from instagram import post_to_instagram, get_post_text
import numpy as np
from datetime import datetime
import constants
import os
from html2image import Html2Image
import pandas as pd
import templates
import utils

from os import walk

def publish_daily_post(instagram_post=False, local_env=False, facebook_post=False):
    day, today, date_in_french, date_in_french_fichier_tapage = get_date_info()
    # day = "12"
    data = extract_markdown_by_date(constants.CSV_FILE, day)
    data_from_tapage =  extract_markdown_by_date_from_tapage(constants.CSV_TAPAGE, date_in_french_fichier_tapage)
    sorted_data = data_from_tapage.sort_values([constants.GENRE_EVT, constants.HORAIRE])
    cleaned_data_data_frame = sorted_data.replace({np.nan: None})

    html_text = ""
    for index, row in cleaned_data_data_frame.iterrows():
        _, _, formatted_event, _ = parse_bidul_event(row)
        html_text += f"""{formatted_event}\n\n"""

    # parsed_event = parse_bidul_event(data_from_tapage)
    if data.empty:
        print(f"No data found for {today}.")
        return

    # Create image from html
    output_image_path = html_to_image(html_text, date_in_french, constants.OUTPUT_IMAGE, templates.HTML_TEMPLATE_GREEN_GREY_ORANGE)

    # Post to Instagram
    if instagram_post:
        text_post = get_post_text(date_in_french)
        post_to_instagram(output_image_path[0], text_post, local_env)
        print(f"Instagram post for {today} published - output file: {output_image_path}")

    print(f"Image Generated for {today} - output file: {output_image_path}")


def get_date_info():
    today = datetime.now().strftime("%Y-%m-%d")
    day = datetime.now().strftime("%d")

    date_in_french, date_in_french_fichier_tapage = get_date_in_french()

    return day, today, date_in_french, date_in_french_fichier_tapage

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
    return f"{day_name} {day:02d} {month_name}", f"{utils.capfirst(day_name)} {day}"


def extract_markdown_by_date(csv_file, date):
    # Load data
    filenames = next(walk('.'), (None, None, []))[2]  # [] if no file
    df = pd.read_csv(csv_file, sep="|")
    # Filter rows matching the date
    today_data = df[df['date'] == int(date)]
    return today_data

def extract_markdown_by_date_from_tapage(csv_file, date):
    # Load data
    df = pd.read_csv(csv_file)
    # Filter rows matching the date
    today_data = df[df['date'] == date]
    return today_data


def html_to_image(html_content, date, output_image, template):

    rendered_html = templates.render_template(
        template,
        content=html_content,
        date=date
    )

    # sorted_csv_reader = sorted(csv_reader, key=lambda d: (d[DATE].split()[1].zfill(2), d[GENRE_EVT], d[HORAIRE]))


    # Render HTML to an image
    hti = Html2Image(output_path=constants.OUTPUT_PATH)
    html_output_file_name = os.path.join(constants.OUTPUT_PATH, f"{output_image}.html")
    open(html_output_file_name, 'w+', encoding='utf-8').write(rendered_html)
    return hti.screenshot(html_str=rendered_html, save_as=output_image, size=(1080, 1080))
