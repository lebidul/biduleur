import fitz  # PyMuPDF
import cv2  # OpenCV
import numpy as np

def extract_text_from_pdf(file_path, pages=[0, 1]):
    doc = fitz.open(file_path)
    text = []
    for page_num in pages:
        if page_num < len(doc):
            page = doc.load_page(page_num)
            """ pix = page.get_pixmap()
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

            # Correct the orientation if needed
            img = correct_orientation(img)

            # Extract text directly from the page """
            text.append(page.get_text("text"))
    return "\n".join(text)

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
