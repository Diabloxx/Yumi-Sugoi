import aiohttp
import base64
import requests
import json
import re

OLLAMA_API_URL = "http://10.0.0.28:11434/api/generate"  # Change if your Ollama instance is on a different port
OLLAMA_MODEL = "llava:7b"  # Change this to match your running model (e.g., "llava-phi")

def clean_response(text: str) -> str:
    # Replace multiple whitespace characters (space, tabs, newlines) with a single space
    cleaned = re.sub(r'\s+', ' ', text).strip()
    return cleaned

async def download_image_bytes(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()
            else:
                raise Exception(f"Failed to download image: {resp.status}")

async def query_ollama_with_image(image_bytes: bytes, prompt: str) -> str:
    try:
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        data = {
            "model": OLLAMA_MODEL,
            "prompt": prompt or "What is in this image?",
            "images": [image_base64]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(OLLAMA_API_URL, json=data) as resp:
                resp.raise_for_status()
                text = await resp.text()

                # Split NDJSON response into lines
                raw_lines = text.strip().split('\n')

                # Parse each line as JSON
                json_objs = [json.loads(line) for line in raw_lines if line.strip()]

                # Extract all "response" fields and join them
                combined_response = " ".join(obj.get("response", "") for obj in json_objs).strip()

                # Clean weird spaces and normalize spacing
                cleaned_response = clean_response(combined_response)

                return cleaned_response or "Sorry, I couldn't understand the image."

    except Exception as e:
        return f"[Vision Error] {str(e)}"
