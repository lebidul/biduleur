import sys
from publisher.utils import get_date_in_french, extract_event_by_date_from_tapage, html_to_image
from biduleur.bidul_parser import parse_bidul_event
from publisher.instagram import post_to_instagram, get_post_text
from constants import *
from publisher.templates import *
import numpy as np

def main(instagram_post=False, local_env=True):
    # print("Environment Variables:")
    # for key, value in os.environ.items():
    #     print(f"{key}: {value}")

    # username = os.getenv("INSTAGRAM_USERNAME")
    # password = os.getenv("INSTAGRAM_PASSWORD")
    #
    # if not username or not password:
    #     print("Error: Environment variables not set!")

    date_french_post, date_french_tapage = get_date_in_french()
    date_french_tapage = "Mardi 33"
    data =  extract_event_by_date_from_tapage(CSV_TAPAGE, date_french_tapage)

    if data.empty:
        print(f"No data found for {date_french_post}.")
        return

    sorted_data = data.sort_values([GENRE_EVT, HORAIRE])
    cleaned_df = sorted_data.replace({np.nan: None})

    html_array = []
    for index, row in cleaned_df.iterrows():
        _, _, formatted_event, _ = parse_bidul_event(row)
        html_array.append(formatted_event)



    # html_array = data['event'].values
    html_text = "\n\n".join(html_array)

    # Create image from html
    output_image_path = html_to_image(html_text, date_french_tapage, OUTPUT_IMAGE, HTML_TEMPLATE_GREEN_GREY_ORANGE)

    # Post to Instagram
    if instagram_post:
        text_post = get_post_text(date_french_tapage)
        post_to_instagram(output_image_path[0], text_post, local_env)
        print(f"Instagram post for {date_french_post} published - output file: {output_image_path}")

    print(f"Image Generated for {date_french_post} - output file: {output_image_path}")


if __name__ == "__main__":
    instagram_post = "--post-to-instagram" in sys.argv
    local_env =  "--local-env" in sys.argv
    main(instagram_post, local_env)
