import logging
import csv
import os

from bidul_parser import parse_bidul
from utils import output_html_file

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

# TODO: add css
# TODO: edge cases: entree libre, info complementaire
# TODO: longueur de lignes (couper les mots)
# TODO: executable
# TODO: open source
# TODO: doc francais
# TODO: handle cas de ligne sans date


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
        html_body_bidul, html_body_agenda, number_of_lines = parse_bidul(reader)
        print(f"number of lines: {number_of_lines}")

    output_html_file(html_body_bidul, original_file_name=filename, output_filename=os.path.basename(filename) + ".html")
    output_html_file(html_body_agenda, original_file_name=filename, output_filename=os.path.basename(filename) + ".agenda.html")


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # filename = '../sample_bidul.csv'
    filename = '../tapages/202401_tapage_biduleur_janvier_2024.csv'
    # filename = '../tapages/202307_tapage_biduleur_juillet_2023.csv'
    run_biduleur(filename)
