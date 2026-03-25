import asyncio
import logging
import os
import time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from PIL import Image

from config import TELEGRAM_BOT_TOKEN, DOWNLOADS_DIR, OUTPUTS_DIR
from states import BotStates
from utils import convert_to_jpeg
from llm_api import generate_flux_prompt, check_image_safety
from comfy_api import process_in_comfy, process_upscale

# Logging initialization
logging.basicConfig(level=logging.INFO)

# Bot and dispatcher initialization
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# Global queue for generation tasks
processing_queue = asyncio.Queue()

async def worker():
    """Background worker that takes tasks from queue and sends them to ComfyUI"""
    while True:
        task = await processing_queue.get()
        try:
            await execute_generation(task)
        except Exception as e:
            logging.error(f"Worker error: {e}")
            await task['callback'].message.answer("❌ Error occurred during queue processing.")
        finally:
            processing_queue.task_done()

async def execute_generation(task):
    callback = task['callback']
    image_path = task['image_path']
    mode = task.get('mode')
    view = task.get('view')
    proportion = task.get('proportion')
    is_upscale = task.get('is_upscale', False)
    
    try:
        if is_upscale:
            try: await callback.message.edit_text("⏳ Upscaling in progress...", parse_mode="Markdown")
            except Exception: pass
            
            original_png_path = await process_upscale(image_path)
            if not original_png_path:
                await callback.message.answer("❌ Upscale failed. Please try another photo.")
                return
                
            final_jpeg_path = convert_to_jpeg(original_png_path)
                
            await callback.message.delete()
            document_filename = f"Upscale_{int(time.time())}.jpg"
            document = FSInputFile(final_jpeg_path, filename=document_filename)
            await bot.send_document(
                chat_id=callback.message.chat.id,
                document=document,
                caption="✅ Done!"
            )
            
            # Targeted cleanup
            try: os.remove(image_path)
            except: pass
            try: os.remove(original_png_path)
            except: pass
            try: os.remove(final_jpeg_path)
            except: pass
            
        else:
            try: await callback.message.edit_text("⏳ Generation in progress...", parse_mode="Markdown")
            except Exception: pass
            
            actual_prompt = await generate_flux_prompt(image_path, mode, proportion, view)
            
            async def update_progress(text):
                print(f"ComfyUI Progress: {text}")

            original_png_path = await process_in_comfy(image_path, actual_prompt, proportion, progress_callback=update_progress)
            
            if not original_png_path:
                await callback.message.answer("❌ Generation error. Please try another photo.")
                return
                
            final_jpeg_path = convert_to_jpeg(original_png_path)
                
            await callback.message.delete()
            document_filename = f"{mode}_{int(time.time())}.jpg"
            document = FSInputFile(final_jpeg_path, filename=document_filename)
            await bot.send_document(
                chat_id=callback.message.chat.id,
                document=document,
                caption=f"✅ Done! {mode} · {view} · {proportion}"
            )
            
            # Targeted cleanup
            try: os.remove(image_path)
            except: pass
            try: os.remove(original_png_path)
            except: pass
            try: os.remove(final_jpeg_path)
            except: pass
            
    except Exception as e:
        logging.error(f"Execution error: {e}")
        await callback.message.answer("❌ Error during generation. Please try again.")


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "✅ Ready to work!\n\n"
        "Send a product photo to get started.",
        parse_mode="Markdown"
    )

@dp.message(F.photo | F.document)
async def handle_photo(message: Message, state: FSMContext):
    if message.document and not message.document.mime_type.startswith('image/'):
        await message.answer("❌ Please send an image file (JPG/PNG).")
        return

    status_msg = await message.answer("⏳ Checking photo...")
    
    try:
        if message.photo: file_id = message.photo[-1].file_id
        else: file_id = message.document.file_id
            
        file_info = await bot.get_file(file_id)
        filename = f"{message.from_user.id}_{file_id}.jpg"
        image_path = os.path.join(DOWNLOADS_DIR, filename)
        await bot.download_file(file_info.file_path, image_path)

        is_safe, reason = await check_image_safety(image_path)
        if not is_safe:
            await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
            await message.answer(f"❌ **Photo rejected.**\n{reason}", parse_mode="Markdown")
            try: os.remove(image_path)
            except: pass
            return

        text_response = (
            "**Image received**\n\n"
            "Select processing type:\n"
            "• `Product` — clean white background for catalog/listing\n"
            "• `Scene` — natural environment for commercial use\n"
            "• `Upscale` — increase resolution without generation"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Product", callback_data="mode_product")],
            [InlineKeyboardButton(text="🌄 Scene", callback_data="mode_scene")],
            [InlineKeyboardButton(text="🔎 Upscale", callback_data="mode_upscale")]
        ])
        
        await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        menu_msg = await message.answer(text_response, reply_markup=keyboard, parse_mode="Markdown")
        await state.set_state(BotStates.waiting_for_mode_selection)
        
        # Save image_path strictly for this specific menu ID
        data = await state.get_data()
        sessions = data.get("sessions", {})
        sessions[str(menu_msg.message_id)] = {"image_path": image_path}
        await state.update_data(sessions=sessions)
        
    except Exception as e:
        logging.error(f"Error handling photo: {e}")
        await message.answer("Error processing image.")

@dp.callback_query(BotStates.waiting_for_mode_selection, F.data.startswith("mode_"))
async def handle_mode_selection(callback: CallbackQuery, state: FSMContext):
    mode_str = callback.data.split("_")[1]
    
    data = await state.get_data()
    sessions = data.get("sessions", {})
    session_data = sessions.get(str(callback.message.message_id))
    
    if not session_data or not session_data.get("image_path") or not os.path.exists(session_data["image_path"]):
        await callback.message.answer("❌ Original image lost. Please send the photo again.")
        return
        
    if mode_str == "upscale":
        qsize = processing_queue.qsize()
        if qsize > 0:
            await callback.message.edit_text(f"⏳ Added to queue (ahead of you: {qsize}). Processing will start when resources are available.")
        else:
            await callback.message.edit_text("⏳ Preparing upscale...", parse_mode="Markdown")
            
        await processing_queue.put({
            "callback": callback,
            "image_path": session_data["image_path"],
            "is_upscale": True
        })
        return

    mode = mode_str.capitalize()
    session_data["mode"] = mode
    sessions[str(callback.message.message_id)] = session_data
    await state.update_data(sessions=sessions)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Front", callback_data="view_front"), InlineKeyboardButton(text="Side", callback_data="view_side")],
        [InlineKeyboardButton(text="Top", callback_data="view_top"), InlineKeyboardButton(text="3/4 View", callback_data="view_3/4")]
    ])
    
    await callback.message.edit_text(
        f"✅ **{mode}**\nSelect angle:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.waiting_for_view_selection)

@dp.callback_query(BotStates.waiting_for_view_selection, F.data.startswith("view_"))
async def handle_view_selection(callback: CallbackQuery, state: FSMContext):
    view_map = {
        "front": "Front view",
        "side": "Side view",
        "top": "Top down flatlay view",
        "3/4": "3/4 isometric perspective view"
    }
    view_key = callback.data.split("_", 1)[1]
    view_en = view_map.get(view_key, "Front view")
    
    data = await state.get_data()
    sessions = data.get("sessions", {})
    session_data = sessions.get(str(callback.message.message_id))
    if not session_data: return
    
    session_data["view"] = view_en
    sessions[str(callback.message.message_id)] = session_data
    await state.update_data(sessions=sessions)
    
    mode = session_data.get("mode", "Product")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Square 1:1", callback_data="prop_1:1"), InlineKeyboardButton(text="Vertical 4:5", callback_data="prop_4:5")],
        [InlineKeyboardButton(text="Vertical 9:16", callback_data="prop_9:16"), InlineKeyboardButton(text="Horizontal 16:9", callback_data="prop_16:9")],
        [InlineKeyboardButton(text="Original proportions", callback_data="prop_original")]
    ])
    
    await callback.message.edit_text(
        f"✅ **{mode}** · {view_key}\nSelect proportions:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(BotStates.waiting_for_proportion_selection)

@dp.callback_query(BotStates.waiting_for_proportion_selection, F.data.startswith("prop_"))
async def handle_proportion_selection(callback: CallbackQuery, state: FSMContext):
    proportion = callback.data.split("_")[1]
    
    data = await state.get_data()
    sessions = data.get("sessions", {})
    session_data = sessions.get(str(callback.message.message_id))
    if not session_data: return
    
    image_path = session_data.get("image_path")
    mode = session_data.get("mode", "Product")
    view = session_data.get("view", "Front view")
    
    if not image_path or not os.path.exists(image_path):
        await callback.message.answer("❌ Original image lost. Please send the photo again.")
        return
        
    qsize = processing_queue.qsize()
    if qsize > 0:
        await callback.message.edit_text(
            f"⏳ Added to queue (waiting: {qsize}). Processing will start when resources are available.", 
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text("⏳ Generation in progress...", parse_mode="Markdown")
    
    await processing_queue.put({
        "callback": callback,
        "image_path": image_path,
        "mode": mode,
        "view": view,
        "proportion": proportion,
        "is_upscale": False
    })
    
@dp.message()
async def handle_other_messages(message: Message):
    await message.answer("❌ Sorry, I only accept images.")

async def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("ERROR: Please set TELEGRAM_BOT_TOKEN in .env")
        return
    if not os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY") == "your_openrouter_api_key_here":
        print("WARNING: OPENROUTER_API_KEY is not set. LLM analysis will not work.")
        
    print("Starting Telegram bot and worker...")
    asyncio.create_task(worker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
