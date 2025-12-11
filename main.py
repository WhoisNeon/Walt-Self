import os
import asyncio
import re
import json
import signal
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
TIMEZONE = ZoneInfo("Asia/Tehran")  # Tehran timezone (UTC+3:30)

# ================== MESSAGES (fully customizable) ==================
MESSAGES = {
    "auto_reply": (
        "**سلام عزیز! 👋**\n\n"
        "در حال حاضر آفلاینم.\n\n"
        "به محض آنلاین شدن، جوابت رو می‌دم! ✨"
    ),
    "set_usage": "**💡 • Usage:** `.set 30m` or `.set 2h`",
    "set_reply_needed": "**‼️ • Reply to a message to set as banner!**",
    "set_min_interval": f"**❌ • Minimum interval: {MIN_MINUTES} minute!**",
    "set_success": (
        "**Banner Activated ✅**\n\n"
        "**💬 • Chat:** {chat_title}\n"
        "**🔁 • Interval:** Every {mins} minute{plural}\n"
        "**🔜 • Next Send:** {next_time}"
    ),
    "stop_success": "**Banner Stopped 🚫**\n\n**💬 • Chat:** {chat_title}",
    "stop_nothing": "**❌ • No active banner in this chat!**",
    "stopall_private": "**🗑️ • All banners stopped globally!**\n\n🔢 • Total stopped: **{count}** banner{plural}",
    "stopall_one": "**🚫 • Banner stopped in this chat only.**\n\n💡 • Use `.stopall` in Saved Messages to stop everything.",
    "stoppall_nothing": "**❌ • No active banners to stop!**",
    "list_empty": "**❌ • No active banners right now.**",
    "list_title": "**Active Banners List 📃**\n",
    "list_item": "{i}. **{title}**\n   Interval: Every {mins} min\n   Next: {next_run}",
    "list_tip": "\n💡 • Stop one → use `.stop` in that chat\nStop all → `.stopall` in Saved Messages",
    "ping_success": "**⚡ • Ping:** `{ping}ms`",
    "ping_error": "**❌ • Ping failed!**",
    "date_title": "**🕐 • Date & Time Info**\n\n",
    "date_tehran": "**🇮🇷 • Tehran Time:** `{tehran_time}`\n**🗓️ • Date:** `{persian_date}`\n",
    "date_utc": "**🌍 • UTC Time:** `{utc_time}`\n**📅 • Date:** `{utc_date}`\n",
    "date_server": "**🖥️ • Server Time:** `{server_time}`\n**📅 • Date:** `{server_date}`\n",
    "date_extra": "\n**ℹ️ • Server timezone: {server_tz}"
}

# ================== GLOBALS ==================
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
schedules = {}
stop_event = asyncio.Event()

# Graceful shutdown
signal.signal(signal.SIGINT, lambda s, f: stop_event.set())
if os.name != "nt":
    signal.signal(signal.SIGTERM, lambda s, f: stop_event.set())

# ================== TIMEZONE HELPER FUNCTIONS ==================
def get_tehran_time():
    """Get current time in Tehran timezone"""
    return datetime.now(TIMEZONE)

def get_server_time():
    """Get current server time (naive or aware)"""
    return datetime.now()

def format_persian_date(dt):
    """Simple Persian date formatting"""
    return dt.strftime("%Y/%m/%d")

# Add this small safe function
def get_server_timezone_name():
    """Safely get server timezone name"""
    try:
        tz = datetime.now().astimezone().tzinfo
        return tz.tzname(None) if tz else "UTC"
    except:
        return "UTC"

# ================== PERSISTENCE ==================
def load():
    if os.path.exists("banner_schedules.json"):
        try:
            with open("banner_schedules.json") as f:
                data = json.load(f)
                for k, v in data.items():
                    # Convert stored times to Tehran timezone
                    stored_next_run = datetime.fromisoformat(v["next_run"])
                    tehran_next_run = stored_next_run.replace(tzinfo=TIMEZONE)
                    schedules[int(k)] = {
                        **v,
                        "next_run": tehran_next_run
                    }
            print(f"Loaded {len(schedules)} active banner(s)")
        except Exception as e:
            print(f"Load error: {e}")

def save():
    try:
        # Store times in Tehran timezone for consistency
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
                    # Schedule next run in Tehran time
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

        # Detect file type & attributes
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

        caption = message.message or "**Saved Self-Destruct Media ✅**"
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

    # Security check
    if ALLOWED_USERS and event.sender_id not in ALLOWED_USERS:
        return

    chat_id = event.chat_id

    if text.startswith(".set"):
        if not event.is_reply:
            await event.edit(MESSAGES["set_reply_needed"])
            return

        replied = await event.get_reply_message()
        try:
            interval = text.split("set", 1)[1].strip()
        except IndexError:
            await event.edit(MESSAGES["set_usage"])
            return

        mins = sum(int(n) * (60 if u == "h" else 1) for n, u in re.findall(r"(\d+)\s*(h|m)", interval + "m"))
        if mins < MIN_MINUTES:
            await event.edit(MESSAGES["set_min_interval"])
            return

        chat = await event.get_input_chat()
        chat_title = getattr(chat, "title", None) or "Saved Messages"

        # Use Tehran timezone for scheduling
        now_tehran = get_tehran_time()
        schedules[chat_id] = {
            "from_chat": replied.chat_id,
            "msg_id": replied.id,
            "minutes": mins,
            "next_run": now_tehran + timedelta(minutes=mins),
            "chat_title": chat_title
        }
        save()

        plural = "" if mins == 1 else "s"
        next_time = schedules[chat_id]["next_run"].strftime("%H:%M:%S")

        await event.edit(MESSAGES["set_success"].format(
            chat_title=chat_title, mins=mins, plural=plural, next_time=next_time
        ))

    elif text in (".stop", ".stopall"):
        is_saved = event.is_private and event.chat_id == me.id

        if text == ".stopall" and is_saved:
            if schedules:
                count = len(schedules)
                plural = "" if count == 1 else "s"
                schedules.clear()
                save()
                await event.edit(MESSAGES["stopall_private"].format(count=count, plural=plural))
            else:
                await event.edit(MESSAGES["stoppall_nothing"])
            return

        if chat_id in schedules:
            title = schedules[chat_id]["chat_title"]
            del schedules[chat_id]
            save()
            await event.edit(
                MESSAGES["stopall_one"] if text == ".stopall" else
                MESSAGES["stop_success"].format(chat_title=title)
            )
        else:
            await event.edit(MESSAGES["stop_nothing"])

    elif text == ".list":
        if not schedules:
            await event.edit(MESSAGES["list_empty"])
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
                mins=info["minutes"],
                next_run=f"{info['next_run'].strftime('%H:%M:%S')} ({time_str})"
            ))
        await event.edit("".join(lines) + MESSAGES["list_tip"])

    elif text == ".date" or text == ".time":
        try:
            tehran_now = get_tehran_time()
            utc_now = datetime.now(ZoneInfo("UTC"))
            server_now = get_server_time()

            date_msg = MESSAGES["date_title"]
            date_msg += MESSAGES["date_tehran"].format(
                tehran_time=tehran_now.strftime("%H:%M:%S"),
                persian_date=format_persian_date(tehran_now)
            )
            date_msg += MESSAGES["date_utc"].format(
                utc_time=utc_now.strftime("%H:%M:%S"),
                utc_date=utc_now.strftime("%Y/%m/%d")
            )
            date_msg += MESSAGES["date_server"].format(
                server_time=server_now.strftime("%H:%M:%S"),
                server_date=server_now.strftime("%Y/%m/%d")
            )
            date_msg += MESSAGES["date_extra"].format(
                server_tz=get_server_timezone_name()
            )

            await event.edit(date_msg)
            
        except Exception as e:
            print(f"Date command error: {e}")
            await event.edit("**❌ • Date command failed!**")

    elif text == ".ping":
        try:
            start = datetime.now()
            await event.edit("**🏓 • Pinging...**")
            end = datetime.now()
            ping = int((end - start).total_seconds() * 1000)
            
            # Show ping with Tehran timestamp
            tehran_time = get_tehran_time().strftime("%H:%M:%S")
            await event.edit(f"{MESSAGES['ping_success'].format(ping=ping)}\n**⏰ Tehran:** {tehran_time}")
        except Exception as e:
            print(f"❌ • Ping command error: {e}")
            await event.edit(MESSAGES["ping_error"]) 

# ================== AUTO FEATURES ==================
@client.on(events.NewMessage(incoming=True))
async def auto_self_destruct(event):
    if getattr(event.message.media, "ttl_seconds", None):
        asyncio.create_task(save_self_destruct(event.message))

@client.on(events.NewMessage(incoming=True))
async def auto_reply(event):
    if event.is_private and event.sender_id != (await client.get_me()).id:
        me = await client.get_me()
        if not isinstance(me.status, (UserStatusOnline, UserStatusRecently)):
            await event.reply(MESSAGES["auto_reply"])

# ================== MAIN ==================
async def main():
    print("• Starting Walt Self-Bot (by @Nymaaa)...")
    print(f"• Server Timezone: {get_server_time().tzinfo}")
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
