import os
import pytesseract
from pdf2image import convert_from_path
import sys
import shutil
import PyPDF2
import argparse
import collections
import string
import nltk
from nltk.corpus import stopwords
import constants

# Ensure stopwords are available
nltk.download('stopwords')


def extract_text_from_pdf(pdf_path, text_output_path):
    """Extracts text from a PDF. If the PDF contains selectable text, extract it directly; otherwise, use OCR."""
    text = ""

    with open(pdf_path, "rb") as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            try:
                extracted_text = page.extract_text()
            except:
                print(f"File corrupted. Skipped: {pdf_path}")
                return

            if extracted_text:
                text += extracted_text + "\n"

    if not text.strip():  # If no text was extracted, use OCR
        images = convert_from_path(pdf_path)
        for image in images:
            text += pytesseract.image_to_string(image) + "\n"

    with open(text_output_path, "w+", encoding="utf-8") as text_file:
        text_file.write(text)


def process_pdfs_in_directory(directory = "./archives/"):
    """Recursively scans a directory for PDFs, extracts text, and saves it alongside the original PDF."""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                text_output_path = os.path.splitext(pdf_path)[0] + ".txt"

                # if not os.path.exists(text_output_path):  # Avoid reprocessing existing files
                extract_text_from_pdf(pdf_path, text_output_path)
                print(f"Processed: {pdf_path}")


def search_text_in_files(directory="./", search_strings=[]):
    """Searches for multiple strings in text files within the directory and subdirectories."""
    matching_files = set()

    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".txt"):
                text_file_path = os.path.join(root, file)
                with open(text_file_path, "r", encoding="utf-8") as text_file:
                    content = text_file.read()
                    if any(search_string.lower() in content.lower() for search_string in search_strings):
                        matching_files.add(text_file_path)

    return list(matching_files)


def compute_word_frequencies(directory="./", top_n=10, excluded_words=None):
    """Computes and prints the most frequent words in all extracted text files, with an exclusion list."""
    if excluded_words is None:
        excluded_words = constants.EXCLUDED_WORDS

    word_counts = collections.Counter()
    stop_words = set(stopwords.words("english")) | set(excluded_words)

    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".txt"):
                text_file_path = os.path.join(root, file)
                with open(text_file_path, "r", encoding="utf-8") as text_file:
                    content = text_file.read().lower()
                    content = content.translate(str.maketrans("", "", string.punctuation))  # Remove punctuation
                    words = content.split()
                    words = [word for word in words if
                             word not in stop_words and len(word) > 2]  # Filter stopwords and short words
                    word_counts.update(words)

    print(f"Top {top_n} most common words (excluding: {', '.join(excluded_words)}):")
    for word, count in word_counts.most_common(top_n):
        print(f"{word}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process PDFs and search extracted text.")
    parser.add_argument("folder_path", help="Path to the folder containing PDFs")
    parser.add_argument("--search", nargs='*', help="Search strings (comma-separated)", default=[])
    parser.add_argument("--index", action='store_true', help="Run the PDF processing step")
    parser.add_argument("--stats", action='store_true', help="Compute the most frequent words in extracted text")
    parser.add_argument("--top", type=int, help="Number of top words to display", default=10)
    args = parser.parse_args()

    if args.index:
        process_pdfs_in_directory(args.folder_path)

    # search_terms = input("Enter search strings (comma-separated): ").split(',')
    # search_terms = ["tenia", "ténia"]
    if args.search:
        results = search_text_in_files(args.folder_path, args.search)

        if results:
            print("Files containing the search strings:")
            for result in results:
                print(result)
        else:
            print("No matches found.")

    if args.stats:
        compute_word_frequencies(args.folder_path, top_n=args.top)
