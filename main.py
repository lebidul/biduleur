import csv
import os

from bidul_parser import parse_bidul
from utils import output_html_file, output_file

# TODO: edge cases: entree libre, info complementaire
# TODO: executable
# TODO: doc francais


def run_biduleur(filename):
    """
    Function that takes a bidul agenda csv file reads it and returns a html file
    
    :param filename:
    :return: 
    """
    html_body_bidul = 'error'
    html_body_agenda = 'error'

    with open(filename, "r", errors="ignore", encoding="utf8") as csvfile:
        reader = csv.DictReader(csvfile)
        html_body_bidul, html_body_agenda, body_post, number_of_lines = parse_bidul(reader)
        print(f"number of lines: {number_of_lines}")

    output_html_file(html_body_bidul, original_file_name=filename, output_filename=os.path.basename(filename) + ".html")
    output_html_file(html_body_agenda, original_file_name=filename, output_filename=os.path.basename(filename) + ".agenda.html")
    output_file(body_post, output_filename=os.path.basename(filename) + ".md.tsv")


if __name__ == '__main__':

    filename = './tapages/202501_tapage_biduleur_janvier_2025.csv'
    # filename = './tapages/202407_tapage_biduleur_juillet_2024.sans_affranchis.csv'
    # filename = './tapages/202408_tapage_biduleur_aout_2024.csv'
    run_biduleur(filename)
