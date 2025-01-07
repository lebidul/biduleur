import requests

# Upload the image to Facebook
def upload_image_to_facebook(page_id, access_token, image_path, message):
    url = f"https://graph.facebook.com/v17.0/{page_id}/photos"
    with open(image_path, "rb") as image_file:
        files = {"source": image_file}
        data = {"access_token": access_token, "message": message}
        response = requests.post(url, files=files, data=data)

    # Handle the response
    if response.status_code == 200:
        print("Image posted successfully!")
        print("Post ID:", response.json().get("post_id"))
    else:
        print("Error posting image:", response.json())
