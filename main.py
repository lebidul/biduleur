import pandas as pd
import sys
from utils import get_date_info, extract_markdown_by_date, html_to_image
from instagram import post_to_instagram, get_post_text
import constants
import templates

def main(instagram_post=True):
    # print("Environment Variables:")
    # for key, value in os.environ.items():
    #     print(f"{key}: {value}")

    # username = os.getenv("INSTAGRAM_USERNAME")
    # password = os.getenv("INSTAGRAM_PASSWORD")
    #
    # if not username or not password:
    #     print("Error: Environment variables not set!")
    #     return

    day, today, date_in_french = get_date_info()
    # day = "12"
    data = extract_markdown_by_date(constants.CSV_FILE, day)

    if data.empty:
        print(f"No data found for {today}.")
        return

    html_array = data['event'].values
    html_text = "\n\n".join(html_array)

    # Create image from html
    output_image_path = html_to_image(html_text, date_in_french, constants.OUTPUT_IMAGE, templates.HTML_TEMPLATE_GREEN_GREY_ORANGE)

    # Post to Instagram
    if instagram_post:
        text_post = get_post_text(date_in_french)
        post_to_instagram(output_image_path[0], text_post)
        print(f"Instagram post for {today} published - output file: {output_image_path}")

    print(f"Image Generated for {today} - output file: {output_image_path}")


if __name__ == "__main__":
    instagram_post = "False" not in sys.argv
    main(instagram_post)
