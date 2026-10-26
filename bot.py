import os
import logging
import asyncio
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import ffmpeg

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fetch bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcoming message upon /start command."""
    await update.message.reply_text(
        "👋 Welcome! Send or forward me any video, video note, or video file, "
        "and I will convert it into an MP4 video for you."
    )

def convert_to_mp4(input_path: str, output_path: str) -> None:
    """Synchronous function to re-encode video to standard MP4 (H.264/AAC)."""
    (
        ffmpeg
        .input(input_path)
        .output(output_path, vcodec='libx264', acodec='aac', strict='experimental', pix_fmt='yuv420p')
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download incoming video, convert to MP4 asynchronously, and upload result."""
    message = update.message
    file_obj = None

    if message.video:
        file_obj = message.video
    elif message.video_note:
        file_obj = message.video_note
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("video/"):
        file_obj = message.document

    if not file_obj:
        await message.reply_text("Please send a valid video file.")
        return

    status_msg = await message.reply_text("📥 Downloading your video...")

    # Unique filenames based on update/message ID
    base_id = f"{update.effective_user.id}_{message.message_id}"
    input_path = f"input_{base_id}"
    output_path = f"converted_{base_id}.mp4"

    try:
        # Step 1: Download file from Telegram
        tg_file = await context.bot.get_file(file_obj.file_id)
        await tg_file.download_to_drive(input_path)

        # Step 2: Convert file off the main async event loop using asyncio.to_thread
        await status_msg.edit_text("⚙️ Converting video to MP4...")
        await asyncio.to_thread(convert_to_mp4, input_path, output_path)

        # Step 3: Send back converted video
        await status_msg.edit_text("📤 Uploading MP4...")
        with open(output_path, 'rb') as converted_file:
            await message.reply_video(
                video=converted_file,
                caption="✅ Here is your converted MP4 video!"
            )
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error during video conversion: {e}")
        await status_msg.edit_text("❌ Failed to convert video. Make sure the file format is supported.")

    finally:
        # Clean up temporary files
        for path in (input_path, output_path):
            if os.paths.exists(path) if hasattr(os, 'paths') else os.path.exists(path):
                os.remove(path)

async def post_init(application: Application) -> None:
    """Automatically configure commands, description, and about text on startup."""
    # 1. Set command menu
    commands = [
        BotCommand("start", "Start the bot & get instructions"),
    ]
    await application.bot.set_my_commands(commands)
    
    # 2. Set Bot Description (Seen before pressing /start)
    description_text = (
        "👋 Welcome to Video to MP4 Converter!\n\n"
        "Send or forward any:\n"
        "🎥 Video files (.mkv, .avi, .mov, .webm, etc.)\n"
        "📹 Video Notes\n"
        "📁 Video Documents\n\n"
        "⚡️ Features:\n"
        "• Fast MP4 H.264 & AAC encoding\n"
        "• Standard compatibility across all devices\n"
        "• 100% Free & automatic conversion\n\n"
        "Click START below to begin! 🚀"
    )
    await application.bot.set_my_description(description_text)

    # 3. Set Bot About Text (Appears on the profile card)
    about_text = "🎬 Convert any video format, video note, or clip into high-quality MP4 instantly. Fast, free, and easy to use!"
    await application.bot.set_my_short_description(about_text)

    logger.info("Bot commands, description, and about text successfully registered.")

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is missing!")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE | filters.Document.VIDEO, handle_video))

    logger.info("Bot started and listening for incoming messages...")
    app.run_polling()

if __name__ == "__main__":
    main()
