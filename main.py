import os
import asyncio
import re
import json
import signal
from datetime import datetime, timedelta

from telethon import TelegramClient, events, functions
from telethon.tl.types import (
    UserStatusOnline, UserStatusRecently,
    DocumentAttributeFilename, DocumentAttributeVideo
)

# ================== EDITABLE MESSAGES & CONFIG ==================
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

allowed_users = [int(x) for x in os.getenv("ALLOWED_USERS", "").split(",") if x]

save_channel = int(os.getenv("SAVE_CHANNEL"))

session = "self"
min_minutes = 1

# Customizable Messages
MESSAGES = {
    "auto_reply": (
        "**سلام عزیز! 👋**\n\n"
        "در حال حاضر آفلاینم.\n\n"
        "به محض آنلاین شدن، جوابت رو می‌دم! ✨"
    ),
    "set_usage": "**💡 • Usage:** `.set 30m` or `.set 2h`",
    "set_reply_needed": "**‼️ • Reply to a message to set as banner!**",
    "set_min_interval": f"**❌ • Minimum interval: {min_minutes} minute!**",
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
    "list_empty": "**❌ • No active banners right now.**",
    "list_title": "**Active Banners List 📃**\n",
    "list_item": "{i}. **{title}**\n   Interval: Every {mins} min\n   Next: {next_run}\n",
    "list_tip": "\n💡 • Stop one → use `.stop` in that chat\nStop all → `.stopall` in Saved Messages"
}
# ==================================================================

client = TelegramClient(session, api_id, api_hash)
schedules = {}
stop_event = asyncio.Event()

# Instant Ctrl+C
signal.signal(signal.SIGINT, lambda s, f: (print("\nInstant stop!"), stop_event.set()))
if os.name != "nt":
    signal.signal(signal.SIGTERM, lambda s, f: stop_event.set())

def load():
    if os.path.exists("banner_schedules.json"):
        try:
            with open("banner_schedules.json") as f:
                data = json.load(f)
                for k, v in data.items():
                    schedules[int(k)] = {**v, "next_run": datetime.fromisoformat(v["next_run"])}
            print(f"Loaded {len(schedules)} active banners")
        except Exception as e:
            print(f"Load error: {e}")

def save():
    try:
        with open("banner_schedules.json", "w") as f:
            json.dump({
                str(k): {**v, "next_run": v["next_run"].isoformat()}
                for k, v in schedules.items()
            }, f, indent=2)
    except Exception as e:
        print(f"Save error: {e}")

async def banner_scheduler():
    while not stop_event.is_set():
        now = datetime.now()
        for chat_id, info in list(schedules.items()):
            if info["next_run"] <= now:
                try:
                    await client.forward_messages(chat_id, info["msg_id"], info["from_chat"])
                    info["next_run"] = now + timedelta(minutes=info["minutes"])
                    save()
                    print(f"Banner sent to chat {chat_id} | Next: {info['next_run'].strftime('%H:%M')}")
                except Exception as e:
                    print(f"Banner failed (chat {chat_id}): {e}")
        await asyncio.sleep(15)

# UNIVERSAL SELF-DESTRUCT SAVER (unchanged)
async def save_self_destruct(message):
    if not getattr(message.media, "ttl_seconds", None):
        return

    try:
        sender = await message.get_sender()
        username = f"@{sender.username}" if sender and sender.username else "—"
        full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Deleted Account"
        user_id = sender.id if sender else "?"

        chat = await client.get_entity(message.chat_id)
        chat_title = getattr(chat, "title", "Private Chat")

        file_bytes = await client.download_media(message, bytes)
        if not file_bytes:
            return

        await asyncio.sleep(2.0 + (message.id % 25) / 10)

        attributes = []
        force_document = True
        if message.photo:
            ext = ".jpg"
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
            mime = message.media.document.mime_type or "application/octet-stream"
            if mime == "image/gif":
                ext = ".gif"
            elif mime.startswith("video/"):
                ext = ".mp4"
            else:
                fn_attr = next((a for a in message.media.document.attributes if isinstance(a, DocumentAttributeFilename)), None)
                ext = os.path.splitext(fn_attr.file_name)[1] if fn_attr else ".file"
            attributes = message.media.document.attributes
        else:
            head = file_bytes[:10]
            if head.startswith(b'\x89PNG'):
                ext = ".png"
            elif head.startswith(b'GIF8'):
                ext = ".gif"
            elif head.startswith(b'\xff\xd8\xff'):
                ext = ".jpg"
            else:
                ext = ".bin"
            force_document = ext != ".jpg"

        filename = f"selfdestruct_{datetime.now():%Y%m%d_%H%M%S}{ext}"

        caption = message.message or "**Saved Self-Destruct Media ✅**"
        full_caption = f"""
{caption}

🪪 • **Full Name:** {full_name}
👤 • **Username:** {username}
🆔 • **User ID:** `{user_id}`
💬 • **Chat:** {chat_title}
📅 • **Saved At:** {datetime.now():%Y-%m-%d %H:%M:%S}
        """.strip()

        file = await client.upload_file(file_bytes, file_name=filename)

        await client.send_message(
            save_channel,
            message=full_caption,
            file=file,
            attributes=attributes,
            force_document=force_document,
            silent=True
        )

        print(f"SAVED → {filename}")

    except Exception as e:
        print(f"Save failed: {e}")

# COMMANDS — Instant Edit + .stopall + Configurable Messages
@client.on(events.NewMessage(outgoing=True))
async def commands(event):
    text = (event.message.message or "").strip().lower()
    me = await client.get_me()
    if allowed_users and event.sender_id != me.id:
        return

    chat_id = event.chat_id

    if text.startswith(".set"):
        if not event.is_reply:
            await event.edit(MESSAGES["set_reply_needed"])
            return

        replied = await event.get_reply_message()
        try:
            interval = text.split("set", 1)[1].strip()
        except:
            await event.edit(MESSAGES["set_usage"])
            return

        mins = sum(int(n) * (60 if u == "h" else 1) for n, u in re.findall(r"(\d+)\s*(h|m)", interval + "m"))
        if mins < min_minutes:
            await event.edit(MESSAGES["set_min_interval"])
            return

        chat = await event.get_input_chat()
        chat_title = getattr(chat, "title", "Saved Messages") if hasattr(chat, "title") else "Private"

        schedules[chat_id] = {
            "from_chat": replied.chat.id,
            "msg_id": replied.id,
            "minutes": mins,
            "next_run": datetime.now() + timedelta(minutes=mins),
            "chat_title": chat_title
        }
        save()

        plural = "" if mins == 1 else "s"
        next_time = schedules[chat_id]["next_run"].strftime('%H:%M:%S')

        msg = MESSAGES["set_success"].format(
            chat_title=chat_title,
            mins=mins,
            plural=plural,
            next_time=next_time
        )
        await event.edit(msg)

    elif text in (".stop", ".stopall"):
        me = await client.get_me()
        is_saved_messages = (event.is_private and event.chat_id == me.id)

        if text == ".stopall" and is_saved_messages:
            if schedules:
                count = len(schedules)
                plural = "" if count == 1 else "s"
                schedules.clear()
                save()
                await event.edit(MESSAGES["stopall_private"].format(count=count, plural=plural))
            else:
                await event.edit("**❌ • No active banners to stop.**")
            return

        if chat_id in schedules:
            title = schedules[chat_id].get("chat_title", "Unknown Chat")
            del schedules[chat_id]
            save()
            if text == ".stopall":
                await event.edit(MESSAGES["stopall_one"])
            else:
                await event.edit(MESSAGES["stop_success"].format(chat_title=title))
        else:
            await event.edit(MESSAGES["stop_nothing"])

    elif text == ".list":
        if not schedules:
            await event.edit(MESSAGES["list_empty"])
            return

        lines = [MESSAGES["list_title"]]
        for i, (cid, info) in enumerate(schedules.items(), 1):
            lines.append(MESSAGES["list_item"].format(
                i=i,
                title=info.get("chat_title", "Unknown"),
                mins=info["minutes"],
                next_run=info["next_run"].strftime("%H:%M:%S")
            ))
        full_msg = "\n".join(lines) + MESSAGES["list_tip"]
        await event.edit(full_msg)

# AUTO FEATURES
@client.on(events.NewMessage(incoming=True))
async def auto_handler(event):
    if getattr(event.message.media, "ttl_seconds", None):
        asyncio.create_task(save_self_destruct(event.message))

@client.on(events.NewMessage(incoming=True))
async def auto_reply(event):
    if event.is_private and event.sender_id != (await client.get_me()).id:
        me = await client.get_me()
        if not isinstance(me.status, (UserStatusOnline, UserStatusRecently)):
            await event.reply(MESSAGES["auto_reply"])

# MAIN
async def main():
    await client.start()
    print("• Walt-Self started successfully!")

    await client(functions.account.UpdateStatusRequest(offline=True))
    load()
    client.loop.create_task(banner_scheduler())
    await stop_event.wait()

    print("• Shutting down...")
    save()
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())