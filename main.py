import os
import asyncio
import re
import json
import signal
import jdatetime
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telethon import TelegramClient, events, functions
from telethon.tl.types import (
    UserStatusOnline,
    UserStatusRecently,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
)

# ================== SECRETS FROM ENVIRONMENT (.env) ==================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")  # e.g. +989123456789
CHANNEL = int(os.getenv("CHANNEL"))  # e.g. -1001234567890

# Comma-separated user IDs allowed to use commands
ALLOWED_USERS = [
    int(x.strip())
    for x in os.getenv("ALLOWED_USERS", "").split(",")
    if x.strip()
]

MIN_MINUTES = 1
SESSION_NAME = "walt_self"

# ================== MESSAGES (fully customizable) ==================
MESSAGES = {
    "set_usage": "**💡 • Usage:** `.set 30m` or `.set 2h`",
    "set_reply_needed": "**‼️ • Reply to a message to set as banner!**",
    "set_min_interval": f"**❌ • Minimum interval: {MIN_MINUTES} minute(s)!**",
    "set_success": (
        "**Banner Activated ✅**\n\n"
        "**💬 • Group:** {chat_title}\n"
        "**🔁 • Interval:** Every {mins}\n"
        "**🔜 • Next Send:** {next_time}\n\n"
        "💡 • Stop → use .stop"
    ),
    "stop_success": "**Banner Stopped 🚫**\n\n**💬 • Group:** {chat_title}",
    "stop_nothing": "**❌ • No active banner in this group!**",
    "stopall_private": "**🗑️ • All banners stopped globally!**\n\n🔢 • Total stopped: **{count}** banner{plural}",
    "stopall_one": "**🚫 • Banner stopped in this group only.**\n\n💡 • Use `.stopall` in Saved Messages to stop everything.",
    "stoppall_nothing": "**❌ • No active banners to stop!**",
    "list_empty": "**❌ • No active banners right now.**",
    "list_title": "**Active Banners List 📃**\n\n",
    "list_item": "{i}. **{title}**\n   Interval: Every {mins}\n   Next: {next_run}\n\n",
    "list_tip": "• Stop one → use `.stop` in that group\n• Stop all → `.stopall` in Saved Messages",
    "ping_success": "**⚡ • Ping:** `{ping}ms`",
    "ping_error": "**❌ • Ping failed!**",
    "date_tehran": "**🇮🇷 • Tehran:**\n • Time: `{tehran_time}`\n • Date: `{persian_date}`\n\n",
    "date_london": "**🇬🇧 • London:**\n • Time: `{london_time}`\n • Date: `{london_date}`\n\n",
    "date_california": "**🇺🇸 • California:**\n • Time: `{california_time}`\n • Date: `{california_date}`",
}

# ================== GLOBALS ==================
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
schedules = {}
stop_event = asyncio.Event()

# Graceful shutdown
signal.signal(signal.SIGINT, lambda s, f: stop_event.set())
if os.name != "nt":
    signal.signal(signal.SIGTERM, lambda s, f: stop_event.set())

# ================== HELPER FUNCTIONS ==================
def get_tehran_time():
    return datetime.now(ZoneInfo("Asia/Tehran"))

def get_london_time():
    return datetime.now(ZoneInfo("Europe/London"))

def get_california_time():
    return datetime.now(ZoneInfo("America/Los_Angeles"))

def format_persian_date(dt):
    jalali = jdatetime.datetime.fromgregorian(datetime=dt)
    return jalali.strftime("%Y/%m/%d")

def format_interval(minutes: int) -> str:
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        if mins == 0:
            return f"{hours} hour{'s' if hours != 1 else ''}"
        return f"{hours}h {mins}m"
    return f"{minutes} minute{'s' if minutes != 1 else ''}"

# ================== PERSISTENCE ==================
def load():
    if os.path.exists("banner_schedules.json"):
        try:
            with open("banner_schedules.json") as f:
                data = json.load(f)
                for k, v in data.items():
                    stored_next_run = datetime.fromisoformat(v["next_run"])
                    tehran_next_run = stored_next_run.replace(tzinfo=ZoneInfo("Asia/Tehran"))
                    schedules[int(k)] = {**v, "next_run": tehran_next_run}
            print(f"Loaded {len(schedules)} active banner(s)")
        except Exception as e:
            print(f"Load error: {e}")

def save():
    try:
        data_to_save = {
            str(k): {**v, "next_run": v["next_run"].isoformat()}
            for k, v in schedules.items()
        }
        with open("banner_schedules.json", "w") as f:
            json.dump(data_to_save, f, indent=2)
    except Exception as e:
        print(f"Save error: {e}")

# ================== BANNER SCHEDULER ==================
async def banner_scheduler():
    while not stop_event.is_set():
        now_tehran = get_tehran_time()
        for chat_id, info in list(schedules.items()):
            if info["next_run"] <= now_tehran:
                try:
                    await client.forward_messages(chat_id, info["msg_id"], info["from_chat"])
                    info["next_run"] = now_tehran + timedelta(minutes=info["minutes"])
                    save()
                    print(f"Banner sent → {info['chat_title']} | Next: {info['next_run'].strftime('%H:%M:%S')} Tehran")
                except Exception as e:
                    print(f"Banner failed (chat {chat_id}): {e}")
        await asyncio.sleep(15)

# ================== SELF-DESTRUCT MEDIA SAVER ==================
async def save_self_destruct(message):
    if not getattr(message.media, "ttl_seconds", None):
        return

    try:
        sender = await message.get_sender()
        username = f"@{sender.username}" if sender and sender.username else "—"
        full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Deleted Account"
        user_id = sender.id if sender else "Unknown"

        chat = await client.get_entity(message.chat_id)
        chat_title = getattr(chat, "title", None) or "Private Chat"

        file_bytes = await client.download_media(message, bytes)
        if not file_bytes:
            return

        await asyncio.sleep(2.0 + (message.id % 25) / 10)

        attributes = []
        force_document = True
        ext = ".file"

        if message.photo:
            ext = ".jpg"
            force_document = False
        elif message.video_note:
            ext = ".mp4"
            attributes = [DocumentAttributeVideo(duration=0, w=480, h=480, round_message=True, supports_streaming=True)]
        elif message.video:
            ext = ".mp4"
            attributes = message.media.document.attributes
        elif message.voice:
            ext = ".ogg"
            attributes = message.media.document.attributes
        elif message.document:
            mime = message.media.document.mime_type or ""
            if mime == "image/gif":
                ext = ".gif"
            elif mime.startswith("video/"):
                ext = ".mp4"
            else:
                fn_attr = next((a for a in message.media.document.attributes if isinstance(a, DocumentAttributeFilename)), None)
                ext = os.path.splitext(fn_attr.file_name)[1] if fn_attr else ".file"
            attributes = message.media.document.attributes
        else:
            head = file_bytes[:12]
            if head.startswith(b'\x89PNG'):
                ext = ".png"
            elif head.startswith(b'GIF8'):
                ext = ".gif"
            elif head.startswith(b'\xff\xd8\xff'):
                ext = ".jpg"
                force_document = False

        filename = f"selfdestruct_{get_tehran_time():%Y%m%d_%H%M%S}{ext}"

        caption = message.message or "**Saved Self-Destruct Media**"
        full_caption = f"""
{caption}

🪪 • **Full Name:** {full_name}
👤 • **Username:** {username}
🆔 • **User ID:** `{user_id}`
💬 • **Chat:** {chat_title}
📅 • **Saved At (Tehran):** {get_tehran_time():%Y-%m-%d %H:%M:%S}
""".strip()

        file = await client.upload_file(file_bytes, file_name=filename)

        await client.send_message(
            CHANNEL,
            message=full_caption,
            file=file,
            attributes=attributes,
            force_document=force_document,
            silent=True
        )
        print(f"SAVED self-destruct → {filename}")

    except Exception as e:
        print(f"Self-destruct save failed: {e}")

# ================== COMMAND HANDLER ==================
@client.on(events.NewMessage(outgoing=True))
async def commands(event):
    text = (event.message.message or "").strip().lower()
    me = await client.get_me()

    # Security: only allowed users can use commands
    if ALLOWED_USERS and event.sender_id not in ALLOWED_USERS:
        return

    chat_id = event.chat_id

    if text.startswith(".set"):
        if not event.is_reply:
            await event.edit(MESSAGES["set_reply_needed"])
            await asyncio.sleep(5)
            await event.delete()
            return

        replied = await event.get_reply_message()
        try:
            interval = text.split("set", 1)[1].strip()
        except IndexError:
            await event.edit(MESSAGES["set_usage"])
            await asyncio.sleep(5)
            await event.delete()
            return

        # Parse interval like 30m, 2h, 1h30m, etc.
        mins = sum(int(n) * (60 if u == "h" else 1) for n, u in re.findall(r"(\d+)\s*(h|m)", interval + "m"))
        if mins < MIN_MINUTES:
            await event.edit(MESSAGES["set_min_interval"])
            await asyncio.sleep(5)
            await event.delete()
            return

        entity = await client.get_entity(chat_id)
        if hasattr(entity, "title") and entity.title:
            chat_title = entity.title
        elif event.is_private and chat_id == me.id:
            chat_title = "Saved Messages"
        elif hasattr(entity, "first_name"):
            chat_title = f"{entity.first_name or ''} {entity.last_name or ''}".strip() or "Deleted Account"
        else:
            chat_title = "Unknown Chat"

        now_tehran = get_tehran_time()
        schedules[chat_id] = {
            "from_chat": replied.chat_id,
            "msg_id": replied.id,
            "minutes": mins,
            "next_run": now_tehran + timedelta(minutes=mins),
            "chat_title": chat_title
        }
        save()

        next_time = schedules[chat_id]["next_run"].strftime("%H:%M:%S")
        await event.edit(MESSAGES["set_success"].format(
            chat_title=chat_title,
            mins=format_interval(mins),
            next_time=next_time
        ))
        await asyncio.sleep(6)
        await event.delete()

    elif text in (".stop", ".stopall"):
        is_saved = event.is_private and chat_id == me.id

        if text == ".stopall" and is_saved:
            if schedules:
                count = len(schedules)
                plural = "" if count == 1 else "s"
                schedules.clear()
                save()
                await event.edit(MESSAGES["stopall_private"].format(count=count, plural=plural))
            else:
                await event.edit(MESSAGES["stoppall_nothing"])
            await asyncio.sleep(5)
            await event.delete()
            return

        if chat_id in schedules:
            title = schedules[chat_id]["chat_title"]
            del schedules[chat_id]
            save()
            await event.edit(
                MESSAGES["stopall_one"] if text == ".stopall" else MESSAGES["stop_success"].format(chat_title=title)
            )
        else:
            await event.edit(MESSAGES["stop_nothing"])
        await asyncio.sleep(5)
        await event.delete()

    elif text == ".list":
        if not schedules:
            await event.edit(MESSAGES["list_empty"])
            await asyncio.sleep(5)
            await event.delete()
            return

        lines = [MESSAGES["list_title"]]
        now_tehran = get_tehran_time()
        for i, (cid, info) in enumerate(schedules.items(), 1):
            time_left = info["next_run"] - now_tehran
            if time_left.total_seconds() > 0:
                mins_left = int(time_left.total_seconds() / 60)
                time_str = f"{mins_left}m left"
            else:
                time_str = "Overdue!"
            lines.append(MESSAGES["list_item"].format(
                i=i,
                title=info["chat_title"],
                mins=format_interval(info["minutes"]),
                next_run=f"{info['next_run'].strftime('%H:%M:%S')} ({time_str})"
            ))
        lines.append(MESSAGES["list_tip"])
        await event.edit("".join(lines))
        await asyncio.sleep(20)
        await event.delete()

    elif text in (".date", ".time"):
        tehran_now = get_tehran_time()
        london_now = get_london_time()
        cali_now = get_california_time()

        msg = MESSAGES["date_tehran"].format(
            tehran_time=tehran_now.strftime("%H:%M:%S"),
            persian_date=format_persian_date(tehran_now)
        ) + MESSAGES["date_london"].format(
            london_time=london_now.strftime("%H:%M:%S"),
            london_date=london_now.strftime("%Y/%m/%d")
        ) + MESSAGES["date_california"].format(
            california_time=cali_now.strftime("%H:%M:%S"),
            california_date=cali_now.strftime("%Y/%m/%d")
        )

        await event.edit(msg)
        await asyncio.sleep(15)
        await event.delete()

    elif text in (".ping", ".test", ".self"):
        start = datetime.now()
        await event.edit("**Pinging...**")
        end = datetime.now()
        ping = int((end - start).total_seconds() * 1000)
        await event.edit(MESSAGES["ping_success"].format(ping=ping))
        await asyncio.sleep(5)
        await event.delete()

# ================== SELF-DESTRUCT SAVER ==================
@client.on(events.NewMessage(incoming=True))
async def auto_self_destruct(event):
    if getattr(event.message.media, "ttl_seconds", None):
        asyncio.create_task(save_self_destruct(event.message))

# ================== MAIN ==================
async def main():
    print("• Starting Walt Self-Bot...")
    await client.start(phone=PHONE)
    me = await client.get_me()
    print(f"Logged in as {me.first_name} (@{me.username or 'no username'})")

    await client(functions.account.UpdateStatusRequest(offline=False))
    load()
    client.loop.create_task(banner_scheduler())

    print("• Bot is running... Press Ctrl+C to stop.")
    await stop_event.wait()

    print("• Shutting down...")
    save()
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
