"""
UploaderXTX Bot
Developer: Ahmed Younis (@A_KOJO / AKRO)
Description: Telegram bot that uploads files to MediaFire (up to 10GB)
             with ZIP compression support.
"""

import os
import logging
import asyncio
import zipfile
import tempfile
import math
import requests
import hashlib
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

# ========== CONFIG ==========
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
API_ID      = int(os.environ.get("API_ID", "0"))
API_HASH    = os.environ.get("API_HASH", "YOUR_API_HASH")
MF_EMAIL    = os.environ.get("MF_EMAIL", "")
MF_PASSWORD = os.environ.get("MF_PASSWORD", "")

# Cache for start video
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
# MediaFire helpers
# ─────────────────────────────────────────────
MEDIAFIRE_API = "https://www.mediafire.com/api/1.5"
CHUNK_SIZE    = 4 * 1024 * 1024   # 4 MB per chunk


def mf_login() -> str | None:
    try:
        r = requests.post(f"{MEDIAFIRE_API}/user/get_session_token.php", data={
            "email": MF_EMAIL,
            "password": MF_PASSWORD,
            "application_id": "42511",
            "response_format": "json"
        }, timeout=30)
        data = r.json()["response"]
        if data["result"] == "Success":
            return data["session_token"]
    except Exception as e:
        logger.error(f"MF login error: {e}")
    return None


def mf_upload_chunked(session_token: str, file_path: str, filename: str) -> str | None:
    """Upload file to MediaFire using chunked resumable upload."""
    try:
        file_size  = os.path.getsize(file_path)
        num_units  = math.ceil(file_size / CHUNK_SIZE)
        file_hash  = _md5(file_path)
        upload_key = None

        with open(file_path, "rb") as f:
            for unit_id in range(num_units):
                chunk      = f.read(CHUNK_SIZE)
                chunk_hash = hashlib.md5(chunk).hexdigest()

                headers = {
                    "x-filename":  filename,
                    "x-filesize":  str(file_size),
                    "x-filehash":  file_hash,
                    "x-unit-id":   str(unit_id),
                    "x-unit-size": str(len(chunk)),
                    "x-unit-hash": chunk_hash,
                    "x-num-units": str(num_units),
                }

                r = requests.post(
                    f"{MEDIAFIRE_API}/upload/resumable.php",
                    params={"session_token": session_token, "response_format": "json"},
                    headers=headers,
                    data=chunk,
                    timeout=120
                )
                resp = r.json().get("response", {})
                if resp.get("result") != "Success":
                    logger.error(f"Chunk {unit_id} failed: {resp}")
                    return None

                doupload = resp.get("doupload", {})
                if doupload.get("key"):
                    upload_key = doupload["key"]

        if upload_key:
            return f"https://www.mediafire.com/file/{upload_key}"

    except Exception as e:
        logger.error(f"MF upload error: {e}")
    return None


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


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
        "وهرفعه على MediaFire فوراً 📤\n\n"
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

        # MediaFire login
        await status.edit_text("🔐 جاري الاتصال بـ MediaFire...")
        token = mf_login()
        if not token:
            await status.edit_text("❌ فشل تسجيل الدخول على MediaFire!")
            return

        # Upload
        zip_name = filename + ".zip"
        await status.edit_text(
            f"☁️ جاري الرفع على MediaFire...\n"
            f"📦 {zip_name} ({zip_size})"
        )
        link = mf_upload_chunked(token, zip_path, zip_name)

        if link:
            await status.edit_text(
                f"✅ **تم الرفع بنجاح!**\n\n"
                f"📄 `{zip_name}`\n"
                f"📦 {zip_size}\n\n"
                f"_by Ahmed Younis_"
            )
            # Send link as a separate clean message
            await message.reply_text(
                f"🔗 **لينك التحميل:**\n{link}",
                quote=False
            )
        else:
            await status.edit_text("❌ فشل الرفع على MediaFire!")


if __name__ == "__main__":
    logger.info("UploaderXTX Bot starting...")
    app.run()
