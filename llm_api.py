import aiohttp
import json
from config import OPENROUTER_API_KEY
from utils import encode_image
from prompts import SAFETY_CHECK_PROMPT, get_flux_system_prompt

async def check_image_safety(image_path):
    """
    Checks image for NSFW, drugs, and prohibited content using AI.
    """
    base64_image = encode_image(image_path)
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = SAFETY_CHECK_PROMPT
    
    data = {
        "model": "openai/gpt-5-nano",
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    try:
                        parsed = json.loads(content)
                        return parsed.get("safe", True), parsed.get("reason", "")
                    except:
                        return True, ""
                else:
                    return True, ""
        except Exception as e:
            print(f"Safety check error: {e}")
            return True, ""

async def generate_flux_prompt(image_path, mode, proportion, view="Front view"):
    """
    Creates detailed prompt for Flux based on selected mode, view, and proportions.
    """
    base64_image = encode_image(image_path)
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = get_flux_system_prompt(mode, view, proportion)

    
    data = {
        "model": "google/gemini-3-flash-preview",
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content']
                    if content.startswith("```json"):
                        content = content[7:-3].strip()
                    try:
                        parsed = json.loads(content)
                        return parsed.get("prompt", f"masterpiece, high quality, {mode}")
                    except json.JSONDecodeError:
                        return f"masterpiece, {mode}, highly detailed"
                else:
                    return f"masterpiece, {mode}"
        except Exception as e:
            print(f"Exception calling LLM for prompt: {e}")
            return f"masterpiece, {mode}"
