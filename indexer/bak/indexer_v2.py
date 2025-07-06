import os
import pytesseract
from pdf2image import convert_from_path
import shutil
import PyPDF2
import argparse
import collections
import string
import nltk
import sqlite3
from nltk.corpus import stopwords
import constants
from fastapi import FastAPI
from typing import List

# Ensure stopwords are available
nltk.download('stopwords')

# Initialize FastAPI
app = FastAPI()


def init_db():
    """Initialize the SQLite database."""
    conn = sqlite3.connect("documents.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            filepath TEXT UNIQUE,
            text TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_text_to_db(filename, filepath, text):
    """Save extracted text to the database."""
    conn = sqlite3.connect("documents.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO documents (filename, filepath, text) 
        VALUES (?, ?, ?) 
        ON CONFLICT(filepath) DO UPDATE SET text=excluded.text
    """, (filename, filepath, text))
    conn.commit()
    conn.close()


def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF. If the PDF contains selectable text, extract it directly; otherwise, use OCR."""
    text = ""

    with open(pdf_path, "rb") as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            extracted_text = page.extract_text()
            if extracted_text:
                text += extracted_text + "\n"

    if not text.strip():  # If no text was extracted, use OCR
        images = convert_from_path(pdf_path)
        for image in images:
            text += pytesseract.image_to_string(image) + "\n"

    return text


def process_pdfs_in_directory(directory):
    """Recursively scans a directory for PDFs, extracts text, and saves it in DB."""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                text = extract_text_from_pdf(pdf_path)
                save_text_to_db(file, pdf_path, text)
                print(f"Indexed: {pdf_path}")


def search_text_in_db(query):
    """Search for a keyword in the database."""
    conn = sqlite3.connect("documents.db")
    cursor = conn.cursor()
    cursor.execute("SELECT filename, filepath FROM documents WHERE text LIKE ?", (f"%{query}%",))
    results = cursor.fetchall()
    conn.close()
    return results


def compute_word_frequencies(directory="./", top_n=10, excluded_words=None):
    """Computes and prints the most frequent words in all extracted text files, with an exclusion list."""
    if excluded_words is None:
        excluded_words = constants.EXCLUDED_WORDS

    word_counts = collections.Counter()
    stop_words = set(stopwords.words("english")) | set(excluded_words)

    conn = sqlite3.connect("documents.db")
    cursor = conn.cursor()
    cursor.execute("SELECT text FROM documents")
    texts = cursor.fetchall()
    conn.close()

    for text in texts:
        content = text[0].lower()
        content = content.translate(str.maketrans("", "", string.punctuation))  # Remove punctuation
        words = content.split()
        words = [word for word in words if word not in stop_words and len(word) > 2]  # Filter stopwords and short words
        word_counts.update(words)

    print(f"Top {top_n} most common words (excluding: {', '.join(excluded_words)}):")
    for word, count in word_counts.most_common(top_n):
        print(f"{word}: {count}")


@app.get("/search")
def search_api(q: str):
    """API endpoint to search extracted text."""
    results = search_text_in_db(q)
    return {"matches": results}


@app.get("/files")
def list_files():
    """API endpoint to list all indexed files."""
    conn = sqlite3.connect("documents.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, filepath FROM documents")
    results = cursor.fetchall()
    conn.close()
    return {"files": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process PDFs and search extracted text.")
    parser.add_argument("folder_path", help="Path to the folder containing PDFs")
    parser.add_argument("--search", nargs='*', help="Search strings (comma-separated)", default=[])
    parser.add_argument("--index", action='store_true', help="Run the PDF processing step")
    parser.add_argument("--stats", action='store_true', help="Compute the most frequent words in extracted text")
    parser.add_argument("--api", action='store_true', help="Run the FastAPI server for text search")
    parser.add_argument("--top", type=int, help="Number of top words to display", default=10)
    args = parser.parse_args()

    init_db()  # Initialize database

    if args.index:
        process_pdfs_in_directory(args.folder_path)

    if args.search:
        results = search_text_in_db(args.search[0])
        if results:
            print("Files containing the search strings:")
            for result in results:
                print(result)
        else:
            print("No matches found.")

    if args.stats:
        compute_word_frequencies(args.folder_path, top_n=args.top)

    if args.api:
        import uvicorn

        uvicorn.run(app, host="127.0.0.1", port=8000)
