"""
UploaderXTX Bot
Developer: Ahmed Younis (@A_KOJO / AKRO)
Description: Multi-host Telegram uploader bot (GoFile, MediaFire, Pixeldrain, Catbox, Filebin)
"""

import os
import logging
import asyncio
import zipfile
import tempfile
import math
import hashlib
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait

# ========== CONFIG ==========
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
API_ID      = int(os.environ.get("API_ID", "0"))
API_HASH    = os.environ.get("API_HASH", "YOUR_API_HASH")
MF_EMAIL    = os.environ.get("MF_EMAIL", "")
MF_PASSWORD = os.environ.get("MF_PASSWORD", "")

START_VIDEO_FILE_ID = None
START_VIDEO_PATH    = "akro.mp4"
# ============================

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("uploaderxtx", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# pending uploads: message_id -> temp file info
pending = {}

CHUNK_SIZE = 4 * 1024 * 1024  # 4MB


# ═══════════════════════════════════════════
# UPLOADERS
# ═══════════════════════════════════════════

def upload_gofile(file_path: str, filename: str) -> str | None:
    try:
        r = requests.get("https://api.gofile.io/servers", timeout=10)
        server = r.json()["data"]["servers"][0]["name"]
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
        logger.error(f"GoFile error: {e}")
    return None


def upload_pixeldrain(file_path: str, filename: str) -> str | None:
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                f"https://pixeldrain.com/api/file/{filename}",
                files={"file": (filename, f)},
                timeout=600
            )
        data = r.json()
        if data.get("id"):
            return f"https://pixeldrain.com/u/{data['id']}"
    except Exception as e:
        logger.error(f"Pixeldrain error: {e}")
    return None


def upload_catbox(file_path: str, filename: str) -> str | None:
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                "https://litterbox.catbox.moe/resources/internals/api.php",
                data={"reqtype": "fileupload", "time": "72h"},
                files={"fileToUpload": (filename, f)},
                timeout=600
            )
        if r.status_code == 200 and r.text.startswith("https://"):
            return r.text.strip()
    except Exception as e:
        logger.error(f"Catbox error: {e}")
    return None


def upload_uploadersh(file_path: str, filename: str) -> str | None:
    """uploader.sh — 10GB max, one-time download, 3 days storage."""
    try:
        with open(file_path, "rb") as f:
            r = requests.put(
                f"https://uploader.sh/{filename}",
                data=f,
                headers={"Content-Type": "application/octet-stream"},
                timeout=600
            )
        if r.status_code == 200 and r.text.strip().startswith("https://"):
            return r.text.strip()
    except Exception as e:
        logger.error(f"uploader.sh error: {e}")
    return None


def upload_filebin(file_path: str, filename: str) -> str | None:
    try:
        import uuid
        bin_id = str(uuid.uuid4())[:8]
        with open(file_path, "rb") as f:
            r = requests.post(
                f"https://filebin.net/{bin_id}/{filename}",
                data=f.read(),
                headers={"Content-Type": "application/octet-stream"},
                timeout=600
            )
        if r.status_code in (200, 201):
            return f"https://filebin.net/{bin_id}/{filename}"
    except Exception as e:
        logger.error(f"Filebin error: {e}")
    return None


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_mediafire(file_path: str, filename: str) -> str | None:
    """MediaFire chunked resumable upload."""
    if not MF_EMAIL or not MF_PASSWORD:
        return None
    try:
        # Login
        r = requests.post("https://www.mediafire.com/api/1.5/user/get_session_token.php", data={
            "email": MF_EMAIL,
            "password": MF_PASSWORD,
            "application_id": "42511",
            "response_format": "json"
        }, timeout=30)
        resp = r.json()["response"]
        if resp["result"] != "Success":
            logger.error(f"MF login failed: {resp}")
            return None
        token = resp["session_token"]

        # Chunked upload
        file_size = os.path.getsize(file_path)
        num_units = math.ceil(file_size / CHUNK_SIZE)
        file_hash = _md5(file_path)
        upload_key = None

        with open(file_path, "rb") as f:
            for unit_id in range(num_units):
                chunk = f.read(CHUNK_SIZE)
                chunk_hash = hashlib.md5(chunk).hexdigest()
                r = requests.post(
                    "https://www.mediafire.com/api/1.5/upload/resumable.php",
                    params={"session_token": token, "response_format": "json"},
                    headers={
                        "x-filename": filename,
                        "x-filesize": str(file_size),
                        "x-filehash": file_hash,
                        "x-unit-id": str(unit_id),
                        "x-unit-size": str(len(chunk)),
                        "x-unit-hash": chunk_hash,
                        "x-num-units": str(num_units),
                    },
                    data=chunk,
                    timeout=120
                )
                res = r.json().get("response", {})
                if res.get("result") != "Success":
                    logger.error(f"MF chunk {unit_id} failed: {res}")
                    return None
                doupload = res.get("doupload", {})
                if doupload.get("key"):
                    upload_key = doupload["key"]

        if upload_key:
            return f"https://www.mediafire.com/file/{upload_key}"
    except Exception as e:
        logger.error(f"MediaFire error: {e}")
    return None


HOSTS = {
    "gofile":     ("GoFile ☁️",     upload_gofile),
    "pixeldrain": ("Pixeldrain 💧", upload_pixeldrain),
    "catbox":     ("Catbox 🐱",     upload_catbox),
    "filebin":    ("Filebin 🗃️",    upload_filebin),
    "mediafire":  ("MediaFire 🔥",  upload_mediafire),
    "uploadersh":  ("Uploader.sh 🖥️",  upload_uploadersh),
}


# ═══════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════

def _fmt(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


import time

def make_progress(status_msg, label: str):
    last = {"pct": -1, "t": time.time(), "speed": 0, "prev": 0}

    async def progress(current, total):
        pct = int(current * 100 / total)
        now = time.time()
        elapsed = now - last["t"]

        # Update speed every second
        if elapsed >= 1.0:
            last["speed"] = (current - last["prev"]) / elapsed
            last["prev"] = current
            last["t"] = now

        if pct == last["pct"]:
            return
        last["pct"] = pct

        # Animated progress bar — 20 chars
        filled = int(pct / 5)
        bar = "▓" * filled + "▒" + "░" * (19 - filled) if filled < 20 else "▓" * 20

        # ETA
        speed = last["speed"]
        if speed > 0:
            eta_sec = int((total - current) / speed)
            eta = f"{eta_sec//60}:{eta_sec%60:02d}"
        else:
            eta = "--:--"

        speed_str = _fmt(int(speed)) + "/s" if speed > 0 else "..."

        try:
            await status_msg.edit_text(
                f"{label}\n"
                f"\n"
                f"`[{bar}]`\n"
                f"⚡ **{pct}%** — {_fmt(current)} / {_fmt(total)}\n"
                f"🚀 السرعة: **{speed_str}**\n"
                f"⏱ الوقت المتبقي: **{eta}**"
            )
        except Exception:
            pass

    return progress


def host_keyboard():
    buttons = []
    row = []
    for key, (label, _) in HOSTS.items():
        row.append(InlineKeyboardButton(label, callback_data=f"host_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


# ═══════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    global START_VIDEO_FILE_ID
    caption = (
        "**UploaderXTX** 🚀\n\n"
        "ابعتلي أي ملف وهرفعه على الموقع اللي تختاره 📤\n\n"
        "_by Ahmed Younis_"
    )
    try:
        if START_VIDEO_FILE_ID:
            await client.send_video(message.chat.id, video=START_VIDEO_FILE_ID, caption=caption)
        elif os.path.exists(START_VIDEO_PATH):
            sent = await client.send_video(message.chat.id, video=START_VIDEO_PATH, caption=caption)
            START_VIDEO_FILE_ID = sent.video.file_id
        else:
            await message.reply_text(caption)
    except Exception as e:
        logger.error(f"Start error: {e}")
        await message.reply_text(caption)


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
    size_str  = _fmt(file_size) if file_size else "?"

    # Save message info for later
    pending[message.id] = {
        "message": message,
        "filename": filename,
        "size_str": size_str,
    }

    await message.reply_text(
        f"╔══ **UploaderXTX** ══╗\n"
        f"\n"
        f"📦 **{filename}**\n"
        f"⚖️ الحجم: **{size_str}**\n"
        f"\n"
        f"🌐 اختار موقع الرفع:",
        reply_markup=host_keyboard()
    )


@app.on_callback_query(filters.regex(r"^host_(.+)$"))
async def host_callback(client: Client, callback: CallbackQuery):
    host_key = callback.matches[0].group(1)
    host_label, uploader_fn = HOSTS.get(host_key, (None, None))
    if not uploader_fn:
        await callback.answer("موقع غير معروف!", show_alert=True)
        return

    # Find original file message
    orig_msg_id = callback.message.reply_to_message_id
    info = pending.get(orig_msg_id)
    if not info:
        await callback.answer("انتهت صلاحية الطلب، ابعت الملف تاني!", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        f"╔══ **UploaderXTX** ══╗\n"
        f"\n"
        f"📡 **جاري الاتصال بتليجرام...**\n"
        f"📄 `{info['filename']}` — {info['size_str']}\n"
        f"🌐 الوجهة: **{host_label}**"
    )

    status = callback.message
    message = info["message"]
    filename = info["filename"]

    with tempfile.TemporaryDirectory() as tmpdir:
        dl_path  = os.path.join(tmpdir, filename)
        zip_path = os.path.join(tmpdir, filename + ".zip")

        # Download
        try:
            progress = make_progress(status, "📥 **تحميل من تليجرام**")
            await client.download_media(message, file_name=dl_path, progress=progress)
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
        except Exception as e:
            await status.edit_text(f"❌ فشل التحميل: {e}")
            return

        # ZIP
        await status.edit_text(
            f"🗜️ **ضغط الملف...**\n"
            f"\n"
            f"`[▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓]`\n"
            f"✅ اكتمل التحميل — جاري الضغط في ZIP"
        )
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(dl_path, filename)
            zip_size = _fmt(os.path.getsize(zip_path))
        except Exception as e:
            await status.edit_text(f"❌ فشل الضغط: {e}")
            return

        # Upload
        zip_name = filename + ".zip"
        await status.edit_text(
            f"☁️ **رفع على {host_label}**\n"
            f"\n"
            f"`[░░░░░░░░░░░░░░░░░░░░]`\n"
            f"⚡ 0% — 📦 {zip_name} ({zip_size})\n"
            f"🚀 السرعة: جاري القياس..."
        )

        loop = asyncio.get_event_loop()
        link = await loop.run_in_executor(None, uploader_fn, zip_path, zip_name)

        if link:
            await status.edit_text(
                f"╔══ **UploaderXTX** ══╗\n"
                f"\n"
                f"`[▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓]` 100%\n"
                f"\n"
                f"✅ **تم الرفع بنجاح!**\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📄 `{zip_name}`\n"
                f"📦 الحجم: **{zip_size}**\n"
                f"🌐 المنصة: **{host_label}**\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"_by Ahmed Younis_ 🚀"
            )
            await message.reply_text(f"🔗 **لينك التحميل:**\n{link}", quote=False)
        else:
            await status.edit_text(
                f"❌ فشل الرفع على {host_label}!\n\nجرب موقع تاني:",
                reply_markup=host_keyboard()
            )

        # Cleanup pending
        pending.pop(orig_msg_id, None)


if __name__ == "__main__":
    logger.info("UploaderXTX Bot starting...")
    app.run()
