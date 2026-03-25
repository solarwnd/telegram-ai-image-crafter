import base64
from PIL import Image

def encode_image(image_path):
    """Encodes image to base64 for API requests"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def needs_upscale(image_path, threshold=1024):
    """Checks if image needs upscaling (if max dimension is below threshold)"""
    with Image.open(image_path) as img:
        w, h = img.size
        return max(w, h) < threshold

def get_original_dimensions(image_path, max_dim=1024):
    """Calculates proportional dimensions for 'original' ratio, multiple of 16"""
    with Image.open(image_path) as img:
        w, h = img.size
    ratio = min(max_dim/w, max_dim/h)
    new_w = max(64, round((w * ratio) / 16) * 16)
    new_h = max(64, round((h * ratio) / 16) * 16)
    return new_w, new_h

def convert_to_jpeg(image_path):
    """Converts image (PNG, etc.) to JPEG and returns path to new file. Old file is deleted."""
    import os
    if not image_path.lower().endswith(".jpg") and not image_path.lower().endswith(".jpeg"):
        jpg_path = image_path.rsplit('.', 1)[0] + ".jpg"
        with Image.open(image_path) as img:
            rgb_im = img.convert('RGB')
            rgb_im.save(jpg_path, 'JPEG', quality=95)
        try: os.remove(image_path)
        except: pass
        return jpg_path
    return image_path
