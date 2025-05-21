from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch
import io

def load_blip():
    try:
        blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        return True, blip_processor, blip_model
    except Exception as e:
        print(f"BLIP model could not be loaded: {e}")
        return False, None, None

def caption_image(blip_processor, blip_model, img_bytes):
    image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
    inputs = blip_processor(images=image, return_tensors="pt")
    with torch.no_grad():
        out = blip_model.generate(**inputs)
    caption = blip_processor.decode(out[0], skip_special_tokens=True)
    return caption
