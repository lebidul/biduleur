import requests
import cv2  # OpenCV
import numpy as np
import fitz  # PyMuPDF
# from  indexer_ia.utils.google_drive import upload_file_to_drive
#from  indexer_ia.utils.google_drive_2 import upload_file_to_drive
#from utils.google_drive_2 import upload_file_to_drive
from utils.local import upload_file_to_local

def mistral_ocr(document_url, api_key):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        "model": "mistral-ocr-latest",
        "document": {
            "type": "image_url",  # Ensure this matches the API's expected type
            "image_url": document_url  # Use 'image_url' instead of 'document_url'
        },
        "include_image_base64": True
    }

    # Print the payload for debugging
    print("Sending payload to OCR API:", payload)

    response = requests.post("https://api.mistral.ai/v1/ocr", headers=headers, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        print("Error:", response.status_code, response.text)
        response.raise_for_status()

def extract_pages_text(ocr_response, pages=[0, 1]):
    text_elements = []
    for page_num in pages:
        page = ocr_response.get('pages')[page_num]
        if page and 'markdown' in page:
            text_elements.append(page['markdown'])
    return "\n".join(text_elements)

def correct_orientation(image):
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Use edge detection to find potential text regions
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Use Hough Line Transform to detect lines
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

    if lines is not None:
        angles = []
        for rho, theta in lines[:, 0]:
            angle = np.degrees(theta)
            angles.append(angle)

        # Calculate the median angle
        median_angle = np.median(angles)

        # Correct the orientation based on the median angle
        if 45 < median_angle <= 135:
            # Rotate 90 degrees clockwise
            image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        elif 135 < median_angle <= 225:
            # Rotate 180 degrees
            image = cv2.rotate(image, cv2.ROTATE_180)
        elif 225 < median_angle <= 315:
            # Rotate 270 degrees clockwise
            image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)

    return image

def prepare_image_for_ocr(file_path, page_num):
    doc = fitz.open(file_path)
    page = doc.load_page(page_num)
    pix = page.get_pixmap()
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

    # Correct the orientation if needed
    img = correct_orientation(img)

    # Save the corrected image temporarily
    temp_image_path = f"./tmp/page_{page_num}.png"
    cv2.imwrite(temp_image_path, img)

    return temp_image_path

def ocr_with_orientation_correction(file_path, api_key, folder_id, pages=[0, 1]):
    all_text = []
    for page_num in pages:
        temp_image_path = prepare_image_for_ocr(file_path, page_num)

        # Upload the image to Google Drive
        image_url = upload_file_to_local(temp_image_path, folder_id, f"page_{page_num}.png")

        # Call the OCR API with the image URL
        ocr_response = mistral_ocr(image_url, api_key)
        page_text = extract_pages_text(ocr_response, pages=[page_num + 1])
        all_text.append(page_text)
    return "\n".join(all_text)

import pytesseract
import os
from pdf2image import convert_from_path

def convert_pdf_to_images(file_path, page_nums):
    """Convertit les pages spécifiées d'un PDF en images."""
    images = convert_from_path(file_path, first_page=min(page_nums) + 1, last_page=max(page_nums) + 1)
    image_paths = []
    for i, image in enumerate(images):
        temp_image_path = f"temp_page_{page_nums[i]}.png"
        image.save(temp_image_path, 'PNG')
        image_paths.append(temp_image_path)
    return image_paths

def prepare_image_for_ocr(image_path, page_num):
    # Charger l'image
    img = cv2.imread(image_path)
    # Traiter l'image pour l'OCR
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    # Sauvegarder l'image temporairement
    temp_image_path = f"temp_processed_page_{page_num}.png"
    cv2.imwrite(temp_image_path, thresh)
    return temp_image_path

def local_ocr(image_path):
    # Utiliser pytesseract pour extraire le texte de l'image
    text = pytesseract.image_to_string(image_path)
    return text

def ocr_with_orientation_correction_Geof(file_path, api_key, folder_id, pages=[0, 1]):
    all_text = []
    # Convertir les pages du PDF en images
    image_paths = convert_pdf_to_images(file_path, pages)
    for page_num, image_path in zip(pages, image_paths):
        # Préparer l'image pour l'OCR
        temp_image_path = prepare_image_for_ocr(image_path, page_num)
        # Effectuer l'OCR sur l'image préparée
        page_text = local_ocr(temp_image_path)
        all_text.append(page_text)
        # Supprimer les images temporaires après traitement
        os.remove(image_path)
        os.remove(temp_image_path)
    return "\n".join(all_text)
