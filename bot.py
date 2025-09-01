import logging
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from openpyxl.utils import get_column_letter
from typing import List
from models import Message, Conversation
from bot_utils import export_conversations_to_excel
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import asyncio
from datetime import time as dtime
from zoneinfo import ZoneInfo

load_dotenv()  # load .env file

BOT_TOKEN = os.getenv("BOT_TOKEN")
dbPath = os.getenv("DB_PATH")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
MAIN_PHONE = os.getenv("MAIN_PHONE")



# === Logging Setup ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def daily_report(app: Application):
    while True:
        now = datetime.now(ZoneInfo("Asia/Almaty"))
        target_time = now.replace(hour=9, minute=5, second=0, microsecond=0)
        if now >= target_time:
            target_time += timedelta(days=1)
        await asyncio.sleep((target_time - now).total_seconds())

        yesterday_date = now - timedelta(days=1)
        yesterday_str = yesterday_date.strftime("%Y-%m-%d")
        messages = get_messages_between_dates(yesterday_str, yesterday_str)
        convs = build_conversations(messages, MAIN_PHONE)

        if not convs:
            logger.info("No messages for yesterday to send.")
            continue

        file_name_date = yesterday_date.strftime("%d-%m-%Y")
        file_path = export_conversations_to_excel(convs, file_name_date)

        caption_text = f"Отзывы за период {file_name_date}"
        try:
            with open(file_path, "rb") as f:
                await app.bot.send_document(
                    chat_id=ADMIN_CHAT_ID,
                    document=f,
                    filename=f"conversations-{file_name_date}.xlsx",
                    caption=caption_text
                )
                logger.info(f"Sent yesterday's report to admin {ADMIN_CHAT_ID}")
        finally:
            import os
            try:
                os.remove(file_path)
                logger.info(f"Deleted temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {file_path}: {e}")


# === Bot Commands ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    logger.info(f"/start called by {user.id} ({user.username})")
    await update.message.reply_text("Hello! I’m your bot 🤖")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today_str = datetime.now().strftime("%Y-%m-%d")
    last_messages = get_messages_between_dates(today_str, today_str)
    convs = build_conversations(last_messages, MAIN_PHONE)

    if not convs:
        await update.message.reply_text("No conversations found.")
        return
    

    # Export to Excel
    file_path = export_conversations_to_excel(convs, today_str)
    
    caption_text = f"Отзывы за период {today_str}"
    try:
        with open(file_path, "rb") as f:
            await update.message.reply_document(f, filename=f"conversations-{today_str}.xlsx", caption=caption_text)
    finally:
        import os
        try:
            os.remove(file_path)
            logger.info(f"Deleted temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete temporary file {file_path}: {e}")


async def yesterday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Compute yesterday's date
    yesterday_date = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday_date.strftime("%Y-%m-%d")
    
    # Fetch yesterday's messages
    last_messages = get_messages_between_dates(yesterday_str, yesterday_str)
    convs = build_conversations(last_messages, MAIN_PHONE)

    if not convs:
        await update.message.reply_text("No conversations found.")
        return
    
    # Format for Excel file
    file_name_date = yesterday_date.strftime("%d-%m-%Y")
    
    # Export to Excel
    file_path = export_conversations_to_excel(convs, file_name_date)
    caption_text = f"Отзывы за период {file_name_date}"

    # Send Excel file via Telegram and delete it afterwards
    try:
        with open(file_path, "rb") as f:
            await update.message.reply_document(f, filename=f"conversations-{file_name_date}.xlsx", caption=caption_text)
    finally:
        import os
        try:
            os.remove(file_path)
            logger.info(f"Deleted temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete temporary file {file_path}: {e}")


async def period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Command: /period <start_date> <end_date>
    Example: /period 01-08-2025 05-08-2025
    Dates must be in DD-MM-YYYY format
    """
    # Check if user provided two arguments
    if len(context.args) != 2:
        await update.message.reply_text("Пожалуйста, укажите период в формате: /period DD-MM-YYYY DD-MM-YYYY")
        return

    start_str, end_str = context.args

    # Convert input strings to date in YYYY-MM-DD format for SQL
    try:
        start_date = datetime.strptime(start_str, "%d-%m-%Y")
        end_date = datetime.strptime(end_str, "%d-%m-%Y")
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Используйте DD-MM-YYYY.")
        return

    start_sql = start_date.strftime("%Y-%m-%d")
    end_sql = end_date.strftime("%Y-%m-%d")

    # Fetch messages in that period
    last_messages: List[Message] = get_messages_between_dates(start_sql, end_sql)
    convs = build_conversations(last_messages, MAIN_PHONE)

    if not convs:
        await update.message.reply_text("Сообщения за указанный период не найдены.")
        return

    # File name based on period
    file_name_date = f"{start_date.strftime('%d-%m-%Y')}_to_{end_date.strftime('%d-%m-%Y')}"

    # Export to Excel
    file_path = export_conversations_to_excel(convs, file_name_date)

    caption_text = f"Отзывы за период {start_date.strftime('%d-%m-%Y')} — {end_date.strftime('%d-%m-%Y')}"

    try:
        with open(file_path, "rb") as f:
            await update.message.reply_document(
                f,
                filename=f"conversations-{file_name_date}.xlsx",
                caption=caption_text
            )
    finally:
        import os
        try:
            os.remove(file_path)
            logger.info(f"Deleted temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete temporary file {file_path}: {e}")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text
    logger.info(f"Echo message from {user.id}: {text}")
    await update.message.reply_text(f"You said: {text}")

@dataclass
class Message:
    ID: int
    message_id: str
    language: str
    address_id: str
    from_phone: str
    to_phone: str
    msgGoodOrBad: str
    message_type: str
    text: str
    date_time: str

# === DB Functions ===
def get_todays_messages() -> List[Message]:
    try:
        conn = sqlite3.connect(dbPath)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, message_id, language, address_id, from_phone, to_phone, msgGoodOrBad, message_type, text, date_time
            FROM messages
            WHERE date(date_time) = date('now')
            ORDER BY id ASC
        """)
        rows = cursor.fetchall()
        conn.close()

        messages: List[Message] = []
        for row in rows:
            messages.append(Message(
                ID=row[0],
                message_id=row[1],
                language=row[2],
                address_id=row[3],
                from_phone=row[4],
                to_phone=row[5],
                msgGoodOrBad=row[6],
                message_type=row[7],
                text=row[8],
                date_time=row[9],
            ))

        return messages
    except Exception as e:
        logger.error(f"Error fetching today's messages: {e}", exc_info=True)
        return []


def get_messages_between_dates(start_date: str, end_date: str) -> List[Message]:
    """
    Fetch messages where date_time is between start_date and end_date.
    Dates should be in 'YYYY-MM-DD' format.
    """
    try:
        conn = sqlite3.connect(dbPath)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, message_id, language, address_id, from_phone, to_phone, msgGoodOrBad, message_type, text, date_time
            FROM messages
            WHERE date(date_time) BETWEEN ? AND ?
            ORDER BY id ASC
        """, (start_date, end_date))
        rows = cursor.fetchall()
        conn.close()

        messages: List[Message] = []
        for row in rows:
            messages.append(Message(
                ID=row[0],
                message_id=row[1],
                language=row[2],
                address_id=row[3],
                from_phone=row[4],
                to_phone=row[5],
                msgGoodOrBad=row[6],
                message_type=row[7],
                text=row[8],
                date_time=row[9],
            ))

        return messages
    except Exception as e:
        logger.error(f"Error fetching messages between {start_date} and {end_date}: {e}", exc_info=True)
        return []
    

# === Main ===
async def main():
    logger.info("Starting bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("echo", echo))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("yesterday", yesterday))
    app.add_handler(CommandHandler("period", period))

    # Background task for daily report
    async def on_startup(app: Application):
        asyncio.create_task(daily_report(app))

    app.post_init = on_startup

    logger.info("Bot is running. Waiting for updates...")
    await app.run_polling()

@dataclass
class Conversation:
    client_phone: str
    messages: List[Message]



def build_conversations(messages: List[Message], bot_phone: str) -> List[Conversation]:
    conversations: Dict[str, List[Message]] = {}

    for msg in messages:
        # Identify the client: if the message is from bot, client is to_phone; else from_phone
        if msg.from_phone == bot_phone:
            client_phone = msg.to_phone
        else:
            client_phone = msg.from_phone

        if client_phone not in conversations:
            conversations[client_phone] = []

        conversations[client_phone].append(msg)

    # Sort messages inside each conversation by ID
    result: List[Conversation] = []
    for client_phone, msgs in conversations.items():
        sorted_msgs = sorted(msgs, key=lambda m: m.ID)
        result.append(Conversation(client_phone=client_phone, messages=sorted_msgs))

    return result
  

if __name__ == "__main__":
    import asyncio
    import nest_asyncio

    # Fix for "event loop already running" errors
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
