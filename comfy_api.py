import aiohttp
import json
import uuid
import os
import asyncio
import copy
from functools import lru_cache
from config import COMFYUI_SERVER_URL, OUTPUTS_DIR, BASE_DIR
from utils import needs_upscale, get_original_dimensions

@lru_cache(maxsize=4)
def _load_workflow_cached(filename):
    filepath = os.path.join(BASE_DIR, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

async def load_workflow(filename):
    # Using deepcopy since workflow is mutated before sending
    return copy.deepcopy(_load_workflow_cached(filename))

async def get_image(prompt_id, timeout_sec=300):
    """Waits for generation to complete and downloads result with timeout."""
    history_url = f"{COMFYUI_SERVER_URL}/history/{prompt_id}"
    start_time = asyncio.get_event_loop().time()
    
    async with aiohttp.ClientSession() as session:
        while True:
            if asyncio.get_event_loop().time() - start_time > timeout_sec:
                print(f"Timeout waiting for image generation for prompt {prompt_id}")
                return None
                
            try:
                async with session.get(history_url) as response:
                    if response.status == 200:
                        history = await response.json()
                        if prompt_id in history:
                            outputs = history[prompt_id]['outputs']
                            for node_id in outputs:
                                if 'images' in outputs[node_id]:
                                    image_data = outputs[node_id]['images'][0]
                                    filename = image_data['filename']
                                    subfolder = image_data['subfolder']
                                    folder_type = image_data['type']
                                    
                                    view_url = f"{COMFYUI_SERVER_URL}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"
                                    async with session.get(view_url) as img_resp:
                                        if img_resp.status == 200:
                                            img_bytes = await img_resp.read()
                                            save_path = os.path.join(OUTPUTS_DIR, filename)
                                            with open(save_path, 'wb') as f:
                                                f.write(img_bytes)
                                            return save_path
            except Exception as e:
                print(f"History pooling error: {e}")
            
            await asyncio.sleep(2)

async def process_upscale(image_path):
    """Sends Up.json workflow to ComfyUI"""
    workflow = await load_workflow('up_workflow.json')
    # Node 50: VHS_LoadImagePath
    workflow["50"]["inputs"]["image"] = os.path.abspath(image_path)
    
    client_id = str(uuid.uuid4())
    url = f"{COMFYUI_SERVER_URL}/prompt"
    data = {"prompt": workflow, "client_id": client_id}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    resp = await response.json()
                    prompt_id = resp['prompt_id']
                    return await get_image(prompt_id)
                return None
        except Exception as e:
            print(f"Upscale error: {e}")
            return None

async def process_edit(image_path, prompt_text, proportion):
    """Sends main Edit.json to ComfyUI"""
    workflow = await load_workflow('edit_workflow.json')
    
    # Calculate dimensions
    if proportion == "1:1": w, h = 1024, 1024
    elif proportion == "9:16": w, h = 576, 1024
    elif proportion == "16:9": w, h = 1024, 576
    elif proportion == "4:5": w, h = 832, 1024
    else: 
        w, h = get_original_dimensions(image_path)
        
    # Fill node inputs
    workflow["126"]["inputs"]["image"] = os.path.abspath(image_path)
    workflow["138"]["inputs"]["text"] = prompt_text
    workflow["141"]["inputs"]["value"] = w
    workflow["142"]["inputs"]["value"] = h

    client_id = str(uuid.uuid4())
    url = f"{COMFYUI_SERVER_URL}/prompt"
    data = {"prompt": workflow, "client_id": client_id}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    resp = await response.json()
                    prompt_id = resp['prompt_id']
                    return await get_image(prompt_id)
                return None
        except Exception as e:
            print(f"Edit error: {e}")
            return None

async def process_in_comfy(image_path, prompt_text, proportion, progress_callback=None):
    original_image_path = image_path
    upscaled_image_path = None
    
    if needs_upscale(image_path):
        if progress_callback:
            await progress_callback("🔎 Image is small: starting upscaling (Up.json)...")
        upscaled_image_path = await process_upscale(image_path)
        image_path = upscaled_image_path
        if not image_path:
            return None
            
    if progress_callback:
        await progress_callback("🎨 Starting generation Flux Klein 9B (Edit.json)...")
        
    result = await process_edit(image_path, prompt_text, proportion)
    
    # Remove temporary upscale file to prevent clutter
    if upscaled_image_path and os.path.exists(upscaled_image_path):
        try: os.remove(upscaled_image_path)
        except Exception: pass
        
    return result
