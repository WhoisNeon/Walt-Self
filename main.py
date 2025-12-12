import os
import io
import re
import json
import time
import signal
import qrcode
import asyncio
import requests
import tempfile
import jdatetime
from flask import Flask, jsonify
from threading import Thread
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
from datetime import datetime, timedelta
from telethon import TelegramClient, events, functions, types
from telethon.tl.types import DocumentAttributeFilename, DocumentAttributeVideo

try:
    from moviepy.editor import VideoFileClip, vfx
except ImportError:
    print("WARNING: MoviePy not installed. GIF fallback will not work. Install with: pip install moviepy")
    VideoFileClip = None
    vfx = None

# ================== SECRETS (.env) ==================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
CHANNEL = int(os.getenv("CHANNEL"))

ALLOWED_USERS = [489391295]
MIN_MINUTES = 1
SESSION_NAME = "walt_self"

CARD_NUMBER = os.getenv("CARD_NUMBER", "مشخص نشده")
CARD_HOLDER = os.getenv("CARD_HOLDER", "مشخص نشده")

# ================== MESSAGES (customizable) ==================
MESSAGES = {
    "set_usage": "**💡 • Usage:** `.set 30m` or `.set 2h`",
    "set_reply_needed": "**‼️ • Reply to a message to set as banner!**",
    "set_min_interval": f"**❌ • Minimum interval: {MIN_MINUTES} minute(s)!**",
    "set_success": (
        "**Banner Activated ✅**\n\n"
        "**💬 • Group:** {chat_title}\n"
        "**🔁 • Interval:** Every {mins}\n"
        "**🔜 • Next Send:** {next_time}\n\n"
        "💡 • Stop → use `.stop`"
    ),
    "stop_success": "**Banner Stopped 🚫**\n\n**💬 • Group:** {chat_title}",
    "stop_nothing": "**❌ • No active banner in this group!**",
    "stopall_private": "**🗑 • All banners stopped globally!**\n\n🔢 • Total stopped: **{count}** banner{plural}",
    "stopall_one": "**🚫 • Banner stopped in this group only.**\n\n💡 • Use `.stopall` in Saved Messages to stop everything.",
    "stoppall_nothing": "**❌ • No active banners to stop!**",
    "list_empty": "**❌ • No active banners right now.**",
    "list_title": "<b>Active Banners List 📃</b>\n\n",
    "list_item": "<blockquote>🟰 {i}. <b>{title}</b>\n   Interval: Every {mins}\n   Next: {next_run}</blockquote>\n\n",
    "list_tip": "• Stop one → use <code>.stop</code> in that group\n• Stop all → <code>.stopall</code> in Saved Messages",
    "ping_success": "**• Ping:** `{ping}ms`",
    "ping_error": "**❌ • Ping failed!**",
    "date_tehran": "**🇮🇷 • Tehran:**\n • Time: `{tehran_time}`\n • Date: `{persian_date}`\n\n",
    "date_london": "**🇬🇧 • London:**\n • Time: `{london_time}`\n • Date: `{london_date}`\n\n",
    "date_california": "**🇺🇸 • California:**\n • Time: `{california_time}`\n • Date: `{california_date}`",
    "card_template": "💳 • شماره کارت: `{card_number}`\n👤 • دارنده کارت: **{card_holder}**",
    "help_message": (
        "<b>Available Commands 📜</b>\n\n"
        "<blockquote>• <code>.help</code> → Show this help message.</blockquote>\n"
        "<blockquote>• <code>.card</code> → Show card information.</blockquote>\n"
        "<blockquote>• <code>.ping</code> / <code>.test</code> → Check bot responsiveness.</blockquote>\n"
        "<blockquote>• <code>.date</code> / <code>.time</code> → Show current date & time.</blockquote>\n"
        "<blockquote>• <code>.set</code> → Set banner & interval.</blockquote>\n"
        "<blockquote>• <code>.list</code> → List all active banners.</blockquote>\n"
        "<blockquote>• <code>.stop</code> → Stop banner in current group.</blockquote>\n"
        "<blockquote>• <code>.stopall</code> → Stop all banners globally.</blockquote>\n"
        "<blockquote>• <code>.alias [cmd] [text]</code> → Create a text shortcut.</blockquote>\n"
        "<blockquote>• <code>.qr [text/url]</code> → Generate a QR code.</blockquote>\n"
        "<blockquote>• <code>.trans [lang]</code> → Translate text (Reply or Inline).</blockquote>\n"
        "<blockquote>• <code>.calc [expression]</code> → Calculate math expression.</blockquote>\n"
        "<blockquote>• <code>.short [url] [slug] [hours]</code> → Shorten a URL.</blockquote>\n"
        "<blockquote>• <code>.gif [text] [flags]</code> → Create GIF. Flags: <code>-w</code> (wide), <code>-2x</code> (speed).</blockquote>\n",
    ),
    "custom_message": "<b>👋 • درود، موجوده عزیز!\n\n✨ • ۱۸ لوکیشن و ۱۰ تانل نیم بها.\n⚡️ • فیلیمو، فیلم نت، نماوا رایگان.\n\n🎁 • تست رایگان: <a href=\"https://t.me/WaltVpnBot?start=fromself\">WaltVpnBot@</a></b>",
    "saver_title": "**Saved Self-Destruct Media ✅**",
    "saver_caption": """
{caption}

🪪 • **Full Name:** {full_name}
👤 • **Username:** {username}
🆔 • **User ID:** `{user_id}`
💬 • **Chat:** {chat_title}
🇮🇷 • **Iran:** `{persian_date}, {tehran_time}`
🇬🇧 • **UTC:** `{utc_date}, {utc_time}`
""".strip(),
    "alias_usage": "**💡 • Usage:** `.alias [cmd_name] [Your text here]`\nor `.alias del [cmd_name]`",
    "alias_success": "**Alias Set ✅**\n\n**• Command:** `{cmd}`\n**• Text:** `{text_preview}`",
    "alias_deleted": "**Alias Deleted 🗑️**\n\n**• Command:** `{cmd}`",
    "alias_not_found": "**❌ • Alias not found:** `{cmd}`",
    "qr_usage": "**💡 • Usage:** `.qr [Your text or URL here]`",
    "qr_error": "**❌ • Failed to generate QR code!**",
    "translate_usage": "**💡 • Usage:** `.trans en [Your text here]`\nor Reply to a message.",
    "translate_error": "**❌ • Translation failed! Check your language code and text.**",
    "calc_error": "**❌ • Invalid expression or calculation failed!**",
    "calc_success": "**🧮 • Result:** `{result}`",
    "short_usage": "**💡 • Usage:** `.short https://target.com [optional_slug] [optional_expire_hours]`",
    "short_invalid_url": "**❌ • Invalid URL provided!**",
    "short_api_error": "**❌ • Shortener API failed:** `{error}`",
    "short_success": "**🔗 • Short URL:** `{short_url}`\n\n**🎯 • Target:** `{target_url}`",
    "short_slug_error": "**❌ • Slug already in use!** Please choose another one.",
    "gif_usage": "**‼️ • Reply to media!**\nUsage: `.gif [text] [-w] [-2x]`\nExample: `.gif Hello -w -1.5x`",
    "gif_invalid_media": "**❌ • Reply must be to a photo, video, or sticker!**",
    "gif_processing": "**⚙️ • Processing GIF...**\n",
    "gif_download_failed": "**❌ • Failed to download media!**",
    "gif_conversion_failed": "**❌ • GIF conversion failed!**",
    "gif_fallback_text": "**⚠️ • FFmpeg failed. Attempting MoviePy fallback (no custom filters)...**\n"
}

# ================== GLOBALS ==================
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
schedules = {}
aliases = {}
stop_event = asyncio.Event()

last_activity_time = datetime.now() 

signal.signal(signal.SIGINT, lambda s, f: stop_event.set())
if os.name != "nt":
    signal.signal(signal.SIGTERM, lambda s, f: stop_event.set())

# NEW: Flask app setup
flask_app = Flask(__name__)

# ================== HELPERS ==================
def get_tehran_time():
    global last_activity_time
    last_activity_time = datetime.now()
    return datetime.now(ZoneInfo("Asia/Tehran"))

def format_interval(minutes: int) -> str:
    if minutes >= 60:
        h = minutes // 60
        m = minutes % 60
        return f"{h}h {m}m" if m else f"{h} hour{'s' if h > 1 else ''}"
    return f"{minutes} minute{'s' if minutes != 1 else ''}"

def format_persian_date(dt):
    return jdatetime.datetime.fromgregorian(datetime=dt).strftime("%Y/%m/%d")

def is_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def ensure_fa_font():
    font_path = "Vazirmatn-Bold.ttf"
    if not os.path.exists(font_path):
        print("• Downloading Vazirmatn font for GIF overlays...")
        try:
            url = "https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Bold.ttf"
            r = requests.get(url, allow_redirects=True)
            with open(font_path, 'wb') as f:
                f.write(r.content)
            print("• Font downloaded successfully.")
        except Exception as e:
            print(f"• Failed to download font: {e}")
            return None
    return font_path

# ================== PERSISTENCE ==================
def load():
    if os.path.exists("banner_schedules.json"):
        try:
            with open("banner_schedules.json") as f:
                data = json.load(f)
                for k, v in data.items():
                    nr = datetime.fromisoformat(v["next_run"]).replace(tzinfo=ZoneInfo("Asia/Tehran"))
                    schedules[int(k)] = {
                        "from_chat": v["from_chat"],
                        "msg_id": v["msg_id"],
                        "topic_id": v.get("topic_id"),
                        "minutes": v["minutes"],
                        "next_run": nr,
                        "chat_title": v["chat_title"]
                    }
            print(f"Loaded {len(schedules)} banner(s)")
        except Exception as e:
            print(f"Load error (banners): {e}")

    if os.path.exists("aliases.json"):
        try:
            with open("aliases.json") as f:
                global aliases
                aliases = json.load(f)
            print(f"Loaded {len(aliases)} alias(es)")
        except Exception as e:
            print(f"Load error (aliases): {e}")

def save():
    try:
        data_to_save = {
            str(k): {
                "from_chat": v["from_chat"],
                "msg_id": v["msg_id"],
                "topic_id": v.get("topic_id"),
                "minutes": v["minutes"],
                "next_run": v["next_run"].isoformat(),
                "chat_title": v["chat_title"]
            }
            for k, v in schedules.items()
        }
        with open("banner_schedules.json", "w") as f:
            json.dump(data_to_save, f, indent=2)
    except Exception as e:
        print(f"Save error (banners): {e}")

    try:
        with open("aliases.json", "w") as f:
            json.dump(aliases, f, indent=2)
    except Exception as e:
        print(f"Save error (aliases): {e}")

# ================== FLASK ROUTES (NEW) ==================
@flask_app.route("/status")
def status_check_json():
    now = datetime.now()
    up_time = now - last_activity_time
    
    is_alive = up_time.total_seconds() < 600 

    return jsonify({
        "status": "UP" if is_alive else "DOWN",
        "last_activity_utc": last_activity_time.isoformat(),
        "bot_uptime_check_seconds": round(up_time.total_seconds(), 2),
        "active_banners": len(schedules)
    })

@flask_app.route("/")
def status_check_html():
    now = datetime.now()
    up_time = now - last_activity_time
    
    is_alive = up_time.total_seconds() < 600

    status_color = "#4CAF50" if is_alive else "#F44336"
    status_text = "Operational" if is_alive else "Stale"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Walt Self-Bot Status</title>
        <style>
            body {{ font-family: sans-serif; text-align: center; padding: 50px; background-color: #f4f4f9; }}
            .container {{ background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); display: inline-block; }}
            .status-indicator {{ height: 20px; width: 20px; background-color: {status_color}; border-radius: 50%; display: inline-block; margin-right: 10px; }}
            h1 {{ color: #333; }}
            p {{ color: #666; }}
            .status {{ font-weight: bold; color: {status_color}; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Walt Self-Bot Status</h1>
            <p>
                <span class="status-indicator"></span> 
                Status: <span class="status">{status_text}</span>
            </p>
            <p>Last Activity: {last_activity_time.strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
            <p>Uptime Check Since Last Activity: {str(up_time).split('.')[0]}</p>
            <p>Active Banners: {len(schedules)}</p>
            <p>Using Flask thread to keep an eye on things.</p>
        </div>
    </body>
    </html>
    """
    return html

# ================== BANNER SCHEDULER ==================
async def banner_scheduler():
    while not stop_event.is_set():
        now = get_tehran_time()
        for key, info in list(schedules.items()):
            if info["next_run"] > now:
                continue

            try:
                chat = await client.get_entity(info["from_chat"])

                if info.get("topic_id") is not None:
                    messages = await client.get_messages(chat, ids=info["msg_id"], reply_to=info["topic_id"])
                else:
                    messages = await client.get_messages(chat, ids=info["msg_id"])

                if not messages:
                    msg = None
                elif isinstance(messages, list):
                    msg = messages[0]
                else:
                    msg = messages

                if not msg:
                    print(f"Banner deleted → removing banner: {info['chat_title']}")
                    del schedules[key]
                    save()
                    continue

                topic_id = info.get("topic_id")
                if topic_id:
                    await client(functions.messages.ForwardMessagesRequest(
                        from_peer=info["from_chat"],
                        id=[msg.id],
                        to_peer=info["from_chat"],
                        top_msg_id=topic_id,
                        random_id=[int.from_bytes(os.urandom(8), 'big', signed=True)]
                    ))
                else:
                    await client.forward_messages(
                        entity=info["from_chat"],
                        messages=msg
                    )

                info["next_run"] = now + timedelta(minutes=info["minutes"])
                save()
                print(f"Banner sent → {info['chat_title']} | Next: {info['next_run'].strftime('%H:%M:%S')}")

            except Exception as e:
                print(f"Banner failed: {e}")
                info["next_run"] = now + timedelta(minutes=info["minutes"])
                save()

        await asyncio.sleep(15)

# ================== COMMAND HANDLER ==================
@client.on(events.NewMessage(outgoing=True))
async def commands(event):
    text = (event.message.message or "").strip().lower()
    raw_text = event.message.message.strip()
    me = await client.get_me()
    if ALLOWED_USERS and event.sender_id not in ALLOWED_USERS:
        return

    current_chat_id = event.chat_id
    get_tehran_time()

    command_parts = raw_text.split(maxsplit=1)
    if command_parts and command_parts[0].startswith('.'):
        alias_cmd = command_parts[0][1:]
        if alias_cmd in aliases:
            await event.edit(aliases[alias_cmd], parse_mode='html')
            return

    # === .help ===
    if text == ".help":
        await event.edit(MESSAGES["help_message"], parse_mode='html')
        await asyncio.sleep(60); await event.delete()

    # === .set ===
    elif text.startswith(".set "):
        if not event.is_reply:
            await event.edit(MESSAGES["set_reply_needed"])
            await asyncio.sleep(5); await event.delete(); return

        replied = await event.get_reply_message()
        parts = raw_text.split()

        if len(parts) < 2:
            await event.edit(MESSAGES["set_usage"])
            await asyncio.sleep(5); await event.delete(); return

        interval_str = parts[1]
        user_topic_id = None
        if len(parts) >= 3 and parts[2].isdigit():
            user_topic_id = int(parts[2])

        mins = sum(int(n) * (60 if u == "h" else 1) for n, u in re.findall(r"(\d+)\s*(h|m)", interval_str + "m"))
        if mins < MIN_MINUTES:
            await event.edit(MESSAGES["set_min_interval"])
            await asyncio.sleep(5); await event.delete(); return

        schedule_key = user_topic_id if user_topic_id is not None else current_chat_id

        chat = await event.get_chat()
        chat_title = getattr(chat, "title", "Private Chat")
        if user_topic_id is not None:
            try:
                topic = await client(functions.messages.GetForumTopicRequest(peer=chat, topic_id=user_topic_id))
                chat_title = f"{chat_title} → {topic.topic.title}"
            except:
                chat_title = f"{chat_title} → Topic #{user_topic_id}"
        if event.is_private and event.chat_id == me.id:
            chat_title = "Saved Messages"

        now = get_tehran_time()
        schedules[schedule_key] = {
            "from_chat": replied.chat_id,
            "msg_id": replied.id,
            "topic_id": user_topic_id,
            "minutes": mins,
            "next_run": now + timedelta(minutes=mins),
            "chat_title": chat_title
        }
        save()

        await event.edit(MESSAGES["set_success"].format(
            chat_title=chat_title,
            mins=format_interval(mins),
            next_time=schedules[schedule_key]["next_run"].strftime("%H:%M:%S")
        ))
        await asyncio.sleep(8)
        await event.delete()

    # === .stop / .stopall ===
    elif raw_text.lstrip().startswith((".stop", ".stopall")):
        is_saved = event.is_private and event.chat_id == me.id

        if raw_text.strip() == ".stopall" and is_saved:
            count = len(schedules)
            schedules.clear()
            save()
            plural = "s" if count != 1 else ""
            await event.edit(MESSAGES["stopall_private"].format(count=count, plural=plural))
            await asyncio.sleep(6); await event.delete(); return

        parts = raw_text.split()
        target_topic_id = None
        if len(parts) >= 2 and parts[1].isdigit():
            target_topic_id = int(parts[1])

        key_to_stop = target_topic_id if target_topic_id is not None else current_chat_id

        if key_to_stop in schedules:
            title = schedules[key_to_stop]["chat_title"]
            del schedules[key_to_stop]
            save()
            await event.edit(MESSAGES["stop_success"].format(chat_title=title))
        else:
            await event.edit(MESSAGES["stop_nothing"])
        await asyncio.sleep(6)
        await event.delete()

    # === .list ===
    elif raw_text.lstrip().startswith(".list"):
        parts = raw_text.split()
        default_delay_seconds = 15
        delete_delay_seconds = default_delay_seconds

        if len(parts) > 1:
            interval_str = parts[1]
            try:
                parsed_minutes = sum(int(n) * (60 if u == "h" else 1) 
                                     for n, u in re.findall(r"(\d+)\s*(h|m)", interval_str + "m"))
                if parsed_minutes > 0:
                    delete_delay_seconds = parsed_minutes * 60
            except Exception:
                pass

        if not schedules:
            await event.edit(MESSAGES["list_empty"])
            await asyncio.sleep(delete_delay_seconds)
            await event.delete()
            return

        lines = [MESSAGES["list_title"]]
        now = get_tehran_time()
        for i, (k, V) in enumerate(sorted(schedules.items(), key=lambda x: x[1]["next_run"]), 1):
            left = int((V["next_run"] - now).total_seconds() / 60)
            status = f"{left}m left" if left > 0 else "now"
            lines.append(MESSAGES["list_item"].format(
                i=i, title=V["chat_title"], mins=format_interval(V["minutes"]),
                next_run=f"{V['next_run'].strftime('%H:%M:%S')} ({status})"
            ))
        lines.append(MESSAGES["list_tip"])
        await event.edit("".join(lines), parse_mode='html')
        await asyncio.sleep(delete_delay_seconds)
        await event.delete()

    # === .date / .time ===
    elif text in (".date", ".time"):
        t = get_tehran_time()
        l = datetime.now(ZoneInfo("Europe/London"))
        c = datetime.now(ZoneInfo("America/Los_Angeles"))
        msg = (
            MESSAGES["date_tehran"].format(tehran_time=t.strftime("%H:%M:%S"), persian_date=format_persian_date(t)) +
            MESSAGES["date_london"].format(london_time=l.strftime("%H:%M:%S"), london_date=l.strftime("%Y/%m/%d")) +
            MESSAGES["date_california"].format(california_time=c.strftime("%H:%M:%S"), california_date=c.strftime("%Y/%m/%d"))
        )
        await event.edit(msg)
        await asyncio.sleep(15); await event.delete()

    # === .ping ===
    elif text in (".ping", ".test", ".self"):
        start = datetime.now()
        e = await event.edit("**• Pinging...**")
        ping = int((datetime.now() - start).total_seconds() * 1000)
        await e.edit(MESSAGES["ping_success"].format(ping=ping))
        await asyncio.sleep(5); await event.delete()

    # === .card ===
    elif text == ".card":
        try:
            card_message = MESSAGES["card_template"].format(
                card_number=CARD_NUMBER,
                card_holder=CARD_HOLDER
            )
        except Exception:
            card_message = "**❌ • Card data or template is invalid!**"

        await event.edit(card_message)

    # === .av / .bot ===
    elif text in (".av", ".bot"):
        await event.edit(MESSAGES["custom_message"], parse_mode='html')

    # === .alias [cmd] [text] ===
    elif raw_text.lstrip().startswith(".alias"):
        parts = raw_text.split(maxsplit=2)

        if len(parts) < 2:
            await event.edit(MESSAGES["alias_usage"]); await asyncio.sleep(5); await event.delete(); return

        cmd_name = parts[1].strip().lower()

        if cmd_name == "del" and len(parts) == 3:
            target_cmd = parts[2].strip().lower()
            if target_cmd in aliases:
                del aliases[target_cmd]
                save()
                await event.edit(MESSAGES["alias_deleted"].format(cmd=target_cmd)); await asyncio.sleep(5); await event.delete(); return
            else:
                await event.edit(MESSAGES["alias_not_found"].format(cmd=target_cmd)); await asyncio.sleep(5); await event.delete(); return

        if len(parts) < 3:
            await event.edit(MESSAGES["alias_usage"]); await asyncio.sleep(5); await event.delete(); return

        alias_text = parts[2].strip()

        if alias_text:
            aliases[cmd_name] = alias_text
            save()
            preview = alias_text[:50] + "..." if len(alias_text) > 50 else alias_text
            await event.edit(MESSAGES["alias_success"].format(cmd=cmd_name, text_preview=preview), parse_mode='html')
        else:
            await event.edit(MESSAGES["alias_usage"])
        await asyncio.sleep(8); await event.delete()

    # === .qr [url/text] ===
    elif raw_text.lstrip().startswith(".qr") or raw_text.lstrip().startswith(".qrcode"):
        qr_data = raw_text.lstrip()[3:].strip()
        if not qr_data:
            await event.edit(MESSAGES["qr_usage"]); await asyncio.sleep(5); await event.delete(); return

        await event.edit("• Generating QR code...")

        try:
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            uploaded_file = await client.upload_file(
                img_bytes,
                file_name='waltself_qrcode.png'
            )

            await client.send_file(
                event.chat_id,
                uploaded_file,
                caption=f"**🖼 • QR Code Data:**\n → `{qr_data[:200]}`"
            )
            await event.delete()

        except Exception:
            await event.edit(MESSAGES["qr_error"]); await asyncio.sleep(5); await event.delete()

    # === .translate [lang_code] [text] / .trans [lang_code] [text] ===
    elif raw_text.lstrip().startswith(".translate") or raw_text.lstrip().startswith(".trans"):
        parts = raw_text.split(maxsplit=2)
        lang_code = ""
        text_to_translate = ""

        if len(parts) < 2:
            await event.edit(MESSAGES["translate_usage"]); await asyncio.sleep(5); await event.delete(); return

        lang_code = parts[1].strip()

        if len(parts) == 3:
            text_to_translate = parts[2].strip()
        elif event.is_reply:
            reply = await event.get_reply_message()
            text_to_translate = reply.message or reply.text

        if not text_to_translate:
            await event.edit(MESSAGES["translate_usage"]); await asyncio.sleep(5); await event.delete(); return

        await event.edit("• Translating...")

        try:
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang_code}&dt=t&q={requests.utils.quote(text_to_translate)}"
            r = requests.get(url, timeout=10)
            r.raise_for_status()

            translation_data = r.json()
            translated_text = translation_data[0][0][0]

            await event.edit(f"**🌐 • Translation ({lang_code.upper()}):**\n\n`{translated_text}`")

        except Exception:
            await event.edit(MESSAGES["translate_error"]); await asyncio.sleep(5); await event.delete()


    # === .calc [expression] ===
    elif raw_text.lstrip().startswith(".calc"):
        expression = raw_text.lstrip()[5:].strip()

        if not expression:
            await event.edit(MESSAGES["calc_error"]); await asyncio.sleep(5); await event.delete(); return

        allowed_chars = "0123456789+-*/(). "
        if not all(c in allowed_chars for c in expression):
            await event.edit(MESSAGES["calc_error"]); await asyncio.sleep(5); await event.delete(); return

        try:
            result = str(eval(expression))
            await event.edit(MESSAGES["calc_success"].format(result=result))
        except Exception:
            await event.edit(MESSAGES["calc_error"])
        await asyncio.sleep(8); await event.delete()


    # === .short [url] [slug] [expire hours] ===
    elif raw_text.lstrip().startswith(".short"):
        parts = raw_text.split()

        if len(parts) < 2:
            await event.edit(MESSAGES["short_usage"]); await asyncio.sleep(10); await event.delete(); return

        target_url = parts[1].strip()

        if not target_url.lower().startswith(('http://', 'https://')):
            target_url = 'https://' + target_url

        if not is_url(target_url):
            await event.edit(MESSAGES["short_invalid_url"]); await asyncio.sleep(10); await event.delete(); return

        slug = parts[2] if len(parts) > 2 and not parts[2].isdigit() else None
        expire_hours = 0

        if len(parts) > 2 and parts[2].isdigit():
            expire_hours = int(parts[2])
        elif len(parts) > 3 and parts[3].isdigit():
            expire_hours = int(parts[3])

        await event.edit("• Shortening URL...")

        payload = {
            "domain": "clc.cx",
            "target_url": target_url,
            "expired_hours": expire_hours
        }
        if slug:
            payload["slug"] = slug
        if expire_hours > 0:
            payload["expired_url"] = "https://google.com"

        headers = {
            "Content-Type": "application/json",
        }

        try:
            r = requests.post("https://clc.is/api/links", headers=headers, json=payload, timeout=15)

            response_data = r.json()

            if isinstance(response_data, dict) and response_data.get('error'):
                if response_data['error'] == "Slug already exists":
                    await event.edit(MESSAGES["short_slug_error"]); await asyncio.sleep(10); await event.delete(); return
                else:
                    await event.edit(MESSAGES["short_api_error"].format(error=response_data['error'])); await asyncio.sleep(10); await event.delete(); return

            if isinstance(response_data, list) and response_data:
                short_link_data = response_data[0]
            else:
                short_link_data = None 

            if not short_link_data or not isinstance(short_link_data, dict):
                error_message = f"Invalid API Response Structure: {json.dumps(response_data)}"
                await event.edit(MESSAGES["short_api_error"].format(error=error_message)); await asyncio.sleep(10); await event.delete(); return

            if short_link_data.get('is_generated') is False and slug:
                await event.edit(MESSAGES["short_slug_error"]); await asyncio.sleep(10); await event.delete(); return

            short_url = short_link_data.get('url')

            if not short_url:
                await event.edit(MESSAGES["short_api_error"].format(error="Missing 'url' in API response.")), await asyncio.sleep(10); await event.delete(); return

            expires_text = f"\n\n**⏰ • Expires in:** {expire_hours} hour(s)" if expire_hours > 0 else ""
            success_message = MESSAGES["short_success"].format(short_url=short_url, target_url=target_url) + expires_text

            await event.edit(success_message)

        except requests.exceptions.Timeout:
            await event.edit(MESSAGES["short_api_error"].format(error="Request timed out. API is slow or down.")); await asyncio.sleep(10); await event.delete()
        except requests.exceptions.RequestException as e:
            error_message = f"Connection error: {e.__class__.__name__}"
            await event.edit(MESSAGES["short_api_error"].format(error=error_message)); await asyncio.sleep(10); await event.delete()
        except Exception as e:
            await event.edit(MESSAGES["short_api_error"].format(error=f"Unknown Error: {e.__class__.__name__}")), await asyncio.sleep(10); await event.delete()

    # === .gif [text] [flags] ===
    elif raw_text.lstrip().startswith(".gif"):
        start_time = time.time()

        if not event.is_reply:
            await event.edit(MESSAGES["gif_usage"])
            await asyncio.sleep(5); await event.delete(); return

        reply_message = await event.get_reply_message()

        is_valid_media = reply_message.photo or reply_message.video or reply_message.sticker
        if not is_valid_media:
            await event.edit(MESSAGES["gif_invalid_media"])
            await asyncio.sleep(5); await event.delete(); return

        args_raw = raw_text.lstrip()[4:].strip()
        
        flag_pattern = r'(-[wW]|-[.0-9]+[xX])'
        
        flags_found = re.findall(flag_pattern, args_raw)
        
        caption_text = args_raw
        for flag in flags_found:
            caption_text = caption_text.replace(flag, ' ')
        
        caption_text = ' '.join(caption_text.split()).strip()

        is_wide = any(f.lower() == '-w' for f in flags_found)
        raw_speed = 1.0
        
        for f in flags_found:
            sm = re.match(r'(-?[\d\.]+)x', f.lower().strip())
            if sm:
                try:
                    raw_speed = float(sm.group(1))
                except:
                    pass
        
        speed = abs(raw_speed) if abs(raw_speed) > 0 else 1.0 

        await event.edit(MESSAGES["gif_processing"])

        input_path = None
        output_path = None

        try:
            font_file = ensure_fa_font()
            
            with tempfile.NamedTemporaryFile(delete=False) as tmp_input:
                input_path = tmp_input.name
                await client.download_media(reply_message, file=input_path)


            if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
                await event.edit(MESSAGES["gif_download_failed"]); await asyncio.sleep(5); await event.delete(); return

            ffmpeg_successful = False
            
            try:
                # --- FFmpeg Conversion (Primary attempt) ---
                vf_filters = []
                
                # Start with scaling
                vf_filters.append("scale=-2:512")
                
                # Speed filter
                if raw_speed < 0:
                    vf_filters.append("reverse")
                    vf_filters.append(f"setpts={1/speed}*PTS")
                elif raw_speed > 0 and speed != 1.0:
                    vf_filters.append(f"setpts={1/speed}*PTS")

                # Wide filter
                if is_wide:
                    vf_filters.append("scale=iw*2:ih")

                # Text filter
                if caption_text:
                    safe_text = caption_text.replace(":", "\\:").replace("'", "")
                    
                    font_cmd = f"fontfile='{font_file}':" if font_file else ""
                    
                    drawtext_cmd = (
                        f"drawtext={font_cmd}text='{safe_text}':"
                        "fontcolor=white:borderw=10:bordercolor=black:"
                        "fontsize=(w/10):x=(w-text_w)/2:y=h-th-25"
                    )
                    vf_filters.append(drawtext_cmd)

                filter_str = ",".join(vf_filters)

                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_output:
                    output_path = tmp_output.name

                    ffmpeg_command = [
                        'ffmpeg', '-y',
                        '-i', input_path,
                        '-vf', filter_str,
                        '-an',
                        '-c:v', 'libx264',
                        '-preset', 'ultrafast',
                        '-crf', '26',
                        '-pix_fmt', 'yuv420p',
                        '-t', '60',
                        '-f', 'mp4',
                        output_path
                    ]

                    process = await asyncio.create_subprocess_exec(
                        *ffmpeg_command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )

                    try:
                        stdout_data, stderr_data = await asyncio.wait_for(process.communicate(), timeout=90.0)
                    except asyncio.TimeoutError:
                        process.kill(); await process.wait()
                        raise TimeoutError("FFmpeg process timed out.")

                    if process.returncode != 0:
                        stderr = stderr_data.decode('utf-8', errors='ignore')
                        raise RuntimeError(f"FFmpeg failed: {stderr[-400:]}")

                ffmpeg_successful = True

            except Exception as e:
                print(f"FFmpeg failed: {e}. Attempting MoviePy fallback...")
                
                # --- MoviePy Fallback Logic (NEW) ---
                if VideoFileClip is None:
                    await event.edit(MESSAGES["gif_conversion_failed"] + "\n\n`MoviePy not installed for fallback.`")
                    raise Exception("MoviePy is not available.")
                
                try:
                    await event.edit(MESSAGES["gif_fallback_text"])
                    
                    # Create a new temp file for the GIF output
                    with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as tmp_gif_output:
                        output_path = tmp_gif_output.name 
                    
                    clip = VideoFileClip(input_path)
                    
                    # Apply speed
                    if speed != 1.0:
                        clip = clip.speedx(speed)
                        
                    # Reverse if needed
                    if raw_speed < 0 and vfx and hasattr(vfx, 'reverse'):
                        clip = clip.fx(vfx.reverse) 
                        
                    # Apply time constraint (max 60 seconds)
                    if clip.duration > 60:
                        clip = clip.subclip(0, 60)
                        
                    # Write the file as a GIF (using imageio)
                    clip.write_gif(output_path, program='imageio', verbose=False, logger=None)
                    
                    # Update file extension for proper captioning later
                    input_path = input_path.replace(os.path.splitext(input_path)[1], '.gif')
                    
                    ffmpeg_successful = True
                    
                except Exception as e_fallback:
                    print(f"MoviePy fallback failed: {e_fallback}")
                    raise e_fallback 

            if ffmpeg_successful:
                is_gif_output = output_path.endswith('.gif')
                
                # Upload the file
                uploaded_file = await client.upload_file(output_path, file_name=f'waltself_gif.{("gif" if is_gif_output else "mp4")}')

                stop_time = time.time()
                proccess_time_s = stop_time - start_time 

                caption_final = f"**✨ GIF Created in** `{proccess_time_s:.3f}s`\n\n"
                if caption_text: caption_final += f"📝 • Text: {caption_text[:50]}\n"
                if raw_speed != 1.0: caption_final += f"⏩ • Speed: {abs(raw_speed)}x\n"
                if is_wide: caption_final += f"↔️ • Widened: ✅\n"
                if is_gif_output and (caption_text or is_wide): 
                    caption_final += "**⚠️ • Note: Text/Wide effects applied ONLY to FFmpeg output, not MoviePy fallback.**"

                
                await client.send_file(
                    event.chat_id,
                    uploaded_file,
                    caption=caption_final.strip(),
                    reply_to=reply_message,
                    force_document=False,
                    attributes=[DocumentAttributeVideo(w=512, h=512, duration=0, supports_streaming=True)]
                )
                await event.delete()

        except Exception as e:
            print(f"GIF conversion failed: {e}")
            error_msg = str(e)
            if "FFmpeg" in error_msg: error_msg = "Processing Error (Check logs)"
            await event.edit(MESSAGES["gif_conversion_failed"] + f"\n\n`{error_msg}`")
            await asyncio.sleep(8); await event.delete()

        finally:
            if input_path and os.path.exists(input_path): os.remove(input_path)
            if output_path and os.path.exists(output_path): os.remove(output_path)

# ================== SELF-DESTRUCT SAVER ==================
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
        if not file_bytes: return

        attributes = []
        force_document = False
        ext = ".file"

        doc_attrs = getattr(message.media, 'document', None)
        if doc_attrs:
            attr_filename = next((a for a in doc_attrs.attributes if isinstance(a, DocumentAttributeFilename)), None)
            if attr_filename:
                filename_base = attr_filename.file_name
                ext = os.path.splitext(filename_base)[1]

            attr_video = next((a for a in doc_attrs.attributes if isinstance(a, DocumentAttributeVideo)), None)
            if attr_video:
                attributes = [a for a in doc_attrs.attributes if not isinstance(a, DocumentAttributeFilename)]
                if message.video_note:
                    ext = ".mp4"
                    attributes.append(DocumentAttributeVideo(duration=attr_video.duration, w=attr_video.w, h=attr_video.h, round_message=True, supports_streaming=True))
                elif message.video:
                    ext = ".mp4"

            elif message.voice or message.audio:
                attributes = doc_attrs.attributes
                ext = ".ogg" if message.voice else ".mp3"

            elif message.document:
                attributes = doc_attrs.attributes
                if not attr_filename:
                    mime = doc_attrs.mime_type or ""
                    if "gif" in mime: ext = ".gif"
                    elif "mp4" in mime or "video" in mime: ext = ".mp4"
                    elif "jpeg" in mime or "jpg" in mime: ext = ".jpg"
                    elif "png" in mime: ext = ".png"
                    force_document = True

            elif message.photo:
                ext = ".jpg"

        if message.photo:
            ext = ".jpg"
            force_document = False
        if message.video:
            ext = ".mp4"
            force_document = False

        iran = get_tehran_time()
        filename = f"waltself_{iran:%Y%m%d_%H%M%S}{ext}"
        caption = message.message or MESSAGES["saver_title"]

        full_caption = MESSAGES["saver_caption"].format(
            caption=caption,
            full_name=full_name,
            username=username,
            user_id=user_id,
            chat_title=chat_title,
            persian_date=format_persian_date(iran),
            tehran_time=iran.strftime("%H:%M:%S"),
            utc_date=datetime.now(ZoneInfo("UTC")).strftime("%Y/%m/%d"),
            utc_time=datetime.now(ZoneInfo("UTC")).strftime("%H:%M:%S")
        )

        file = await client.upload_file(file_bytes, file_name=filename)
        await client.send_message(CHANNEL, full_caption, file=file, attributes=attributes, force_document=force_document, silent=True)
        print(f"SAVED self-destruct → {filename}")
    except Exception as e:
        print(f"Self-destruct save failed: {e}")

@client.on(events.NewMessage(incoming=True))
async def auto_self_destruct(event):
    if getattr(event.message.media, "ttl_seconds", None):
        asyncio.create_task(save_self_destruct(event.message))

# ================== MAIN ==================
def run_flask():
    flask_app.run(host='0.0.0.0', port=os.getenv("PORT", 8080), debug=False, use_reloader=False)

async def main():
    # Start Flask Thread
    print("• Starting Flask web server...")
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
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
