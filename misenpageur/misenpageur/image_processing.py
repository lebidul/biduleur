from PIL import Image
import os

def resize_images(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for img_name in os.listdir(input_dir):
        img_path = os.path.join(input_dir, img_name)
        img = Image.open(img_path)
        if img.mode in ('P', 'PA'):
            img = img.convert('RGBA')
        img.thumbnail((80, 80))
        img.convert('RGB').save(os.path.join(output_dir, f"optimised_{img_name}"))

def resize_cover_image(input_path, output_path):
    img = Image.open(input_path)
    if img.mode in ('P', 'PA'):
        img = img.convert('RGBA')
    img.thumbnail((1485, 2100))
    img.convert('RGB').save(output_path)
