import cloudinary
import cloudinary.uploader
import cloudinary.api
import os

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

def upload_file_to_cloudinary(file_obj, folder: str, public_id: str):
    """
    Uploads file to Cloudinary and returns secure URL
    """
    result = cloudinary.uploader.upload(
        file_obj,
        folder=folder,
        public_id=public_id,
        resource_type="auto"  # IMPORTANT: supports images + PDFs
    )
    return result["secure_url"]
