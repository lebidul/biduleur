from datetime import datetime
import constants
import os
from html2image import Html2Image
import pandas as pd
import templates

def get_date_info():
    today = datetime.now().strftime("%Y-%m-%d")
    day = datetime.now().strftime("%d")

    date_in_french = get_date_in_french()

    return day, today, date_in_french

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


def extract_markdown_by_date(csv_file, date):
    # Load data
    df = pd.read_csv(csv_file, sep="|")
    # Filter rows matching the date
    today_data = df[df['date'] == int(date)]
    return today_data


def html_to_image(html_content, date, output_image, template):

    rendered_html = templates.render_template(
        template,
        content=html_content,
        date=date
    )

    # Render HTML to an image
    hti = Html2Image(output_path='./output/')
    html_output_file_name = os.path.join(constants.OUTPUT_PATH, f"{output_image}.html")
    open(html_output_file_name, 'w+', encoding='utf-8').write(rendered_html)
    return hti.screenshot(html_str=rendered_html, save_as=output_image, size=(1080, 1080))