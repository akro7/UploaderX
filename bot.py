"""
UploaderXTX Bot
Developer: Ahmed Younis (@A_KOJO / AKRO)
Description: Telegram bot that uploads files to GoFile (up to 10GB+)
             with ZIP compression support.
"""

import os
import logging
import asyncio
import zipfile
import tempfile
import requests
import hashlib
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

# ========== CONFIG ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
API_ID    = int(os.environ.get("API_ID", "0"))
API_HASH  = os.environ.get("API_HASH", "YOUR_API_HASH")

START_VIDEO_FILE_ID = None
START_VIDEO_PATH    = "akro.mp4"
# ============================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Client(
    "uploaderxtx",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ─────────────────────────────────────────────
# GoFile upload (no login needed)
# ─────────────────────────────────────────────
def gofile_get_server() -> str:
    """Get best available GoFile server."""
    r = requests.get("https://api.gofile.io/servers", timeout=10)
    data = r.json()
    if data["status"] == "ok":
        return data["data"]["servers"][0]["name"]
    return "store1"


def gofile_upload(file_path: str, filename: str) -> str | None:
    """Upload file to GoFile and return download link."""
    try:
        server = gofile_get_server()
        with open(file_path, "rb") as f:
            r = requests.post(
                f"https://{server}.gofile.io/contents/uploadfile",
                files={"file": (filename, f)},
                timeout=600
            )
        data = r.json()
        if data["status"] == "ok":
            return data["data"]["downloadPage"]
    except Exception as e:
        logger.error(f"GoFile upload error: {e}")
    return None


# ─────────────────────────────────────────────
# ZIP helper
# ─────────────────────────────────────────────
def zip_file(input_path: str, output_path: str, arcname: str):
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(input_path, arcname)


# ─────────────────────────────────────────────
# Progress bar
# ─────────────────────────────────────────────
def make_progress(status_msg, label: str):
    last = {"pct": -1}

    async def progress(current, total):
        pct = int(current * 100 / total)
        if pct != last["pct"] and pct % 10 == 0:
            last["pct"] = pct
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            try:
                await status_msg.edit_text(
                    f"{label}\n[{bar}] {pct}%\n"
                    f"{_fmt(current)} / {_fmt(total)}"
                )
            except Exception:
                pass

    return progress


def _fmt(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


# ─────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    global START_VIDEO_FILE_ID

    caption = (
        "**UploaderXTX** 🚀\n\n"
        "ابعتلي أي ملف أو فوروردلي أي ملف من تليجرام\n"
        "وهرفعه على GoFile فوراً 📤\n\n"
        "_by Ahmed Younis_"
    )

    try:
        if START_VIDEO_FILE_ID:
            await client.send_video(
                message.chat.id,
                video=START_VIDEO_FILE_ID,
                caption=caption
            )
        elif os.path.exists(START_VIDEO_PATH):
            sent = await client.send_video(
                message.chat.id,
                video=START_VIDEO_PATH,
                caption=caption
            )
            START_VIDEO_FILE_ID = sent.video.file_id
            logger.info(f"Cached video file_id: {START_VIDEO_FILE_ID}")
        else:
            await message.reply_text(caption)
    except Exception as e:
        logger.error(f"Start error: {e}")
        await message.reply_text(caption)


# ─────────────────────────────────────────────
# File handler
# ─────────────────────────────────────────────
@app.on_message(
    (filters.document | filters.video | filters.audio | filters.photo) & filters.private
)
async def file_handler(client: Client, message: Message):
    if message.document:
        file_obj = message.document
        filename = file_obj.file_name or f"file_{file_obj.file_id[:8]}"
    elif message.video:
        file_obj = message.video
        filename = f"video_{file_obj.file_id[:8]}.mp4"
    elif message.audio:
        file_obj = message.audio
        filename = message.audio.file_name or f"audio_{file_obj.file_id[:8]}.mp3"
    elif message.photo:
        file_obj = message.photo
        filename = f"photo_{file_obj.file_id[:8]}.jpg"
    else:
        return

    file_size = getattr(file_obj, "file_size", 0)
    size_str  = _fmt(file_size) if file_size else "غير معروف"

    status = await message.reply_text(
        f"📥 جاري التحميل من تليجرام...\n"
        f"📄 `{filename}` ({size_str})"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        dl_path  = os.path.join(tmpdir, filename)
        zip_path = os.path.join(tmpdir, filename + ".zip")

        # Download
        try:
            progress = make_progress(status, "📥 جاري التحميل...")
            await client.download_media(
                message,
                file_name=dl_path,
                progress=progress
            )
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
        except Exception as e:
            await status.edit_text(f"❌ فشل التحميل: {e}")
            return

        # ZIP
        await status.edit_text("🗜️ جاري الضغط في ZIP...")
        try:
            zip_file(dl_path, zip_path, filename)
            zip_size = _fmt(os.path.getsize(zip_path))
        except Exception as e:
            await status.edit_text(f"❌ فشل الضغط: {e}")
            return

        # Upload to GoFile
        zip_name = filename + ".zip"
        await status.edit_text(
            f"☁️ جاري الرفع على GoFile...\n"
            f"📦 {zip_name} ({zip_size})"
        )
        link = gofile_upload(zip_path, zip_name)

        if link:
            await status.edit_text(
                f"✅ **تم الرفع بنجاح!**\n\n"
                f"📄 `{zip_name}`\n"
                f"📦 {zip_size}\n\n"
                f"_by Ahmed Younis_"
            )
            await message.reply_text(
                f"🔗 **لينك التحميل:**\n{link}",
                quote=False
            )
        else:
            await status.edit_text("❌ فشل الرفع!")


if __name__ == "__main__":
    logger.info("UploaderXTX Bot starting...")
    app.run()
