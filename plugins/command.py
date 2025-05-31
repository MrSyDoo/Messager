from pyrogram import Client, filters
from pyromod.exceptions import ListenerTimeout
from config import Txt, Config
from .start import db
from telethon import TelegramClient
from telethon.sessions import StringSession

from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio

FREE_ACCOUNT = Config.FREE_ACCOUNT
API_HASH = Config.API_HASH
API_ID = Config.API_ID


@Client.on_message(filters.command("settings") & filters.private)
async def settings_handler(client, message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return await message.reply("❗ You are not registered. Click On /start")

    accounts = user.get("accounts", [])
    if not accounts:
        return await message.reply("😶 No accounts found.")

    keyboard = []
    for i, acc in enumerate(accounts):
        session = StringSession(acc["session"])
        async with TelegramClient(session, Config.API_ID, Config.API_HASH) as tg_client:
            try:
                me = await tg_client.get_me()
                name = me.first_name or me.username or str(me.id)
                btn = InlineKeyboardButton(
                    f"{name} ({me.id})",
                    callback_data=f"everything_{i}"
                )
                keyboard.append([btn])
            except Exception:
                keyboard.append([InlineKeyboardButton(f"Account {i+1} (Invalid)", callback_data=f"choose_account_{i}")])

    await message.reply(
        "⚙️ Choose an account to manage settings:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@Client.on_message(filters.command("joingroup") & filters.private)
async def joingroup_accounts(client: Client, message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user or not user.get("accounts"):
        return await message.reply("❗ No accounts found. Add one using /add_account.")

    buttons = []
    for i, acc in enumerate(user["accounts"]):
        try:
            async with TelegramClient(StringSession(acc["session"]), Config.API_ID, Config.API_HASH) as userbot:
                me = await userbot.get_me()
                acc_name = me.first_name or me.username or f"Account {i+1}"
        except Exception:
            acc_name = f"Account {i+1} (invalid)"
        buttons.append([InlineKeyboardButton(acc_name, callback_data=f"join_group_account_{i}")])

    await message.reply("Cʜᴏᴏꜱᴇ ᴀɴ ᴀᴄᴄᴏᴜɴᴛ ᴛᴏ ᴊᴏɪɴ ᴀ ɢʀᴏᴜᴩ :", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_message(filters.command("text") & filters.private)
async def handle_text_command(client: Client, message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    accounts = user.get("accounts", [])

    if not accounts:
        return await message.reply("Yᴏᴜ ʜᴀᴠᴇ ɴᴏᴛ ᴀᴅᴅᴇᴅ ᴀɴʏ ᴀᴄᴄᴏᴜɴᴛ. Uꜱᴇ /add_account ꜰɪʀꜱᴛ.")

    # Select account with account name (if premium and has multiple accounts)
    
    buttons = []
    for i, acc in enumerate(accounts):
       try:
           async with TelegramClient(StringSession(acc["session"]), API_ID, API_HASH) as userbot:
               me = await userbot.get_me()
               name = me.username or f"{me.first_name} {me.last_name or ''}".strip()
       except Exception:
           name = f"Account {i+1}"
       buttons.append([InlineKeyboardButton(name, callback_data=f"text_acc_{i}")])

    await message.reply("Select the account to use:", reply_markup=InlineKeyboardMarkup(buttons))

    try:
        cb: CallbackQuery = await client.listen(user_id, timeout=60)
    except asyncio.exceptions.TimeoutError:
        return await message.reply("❌ Tɪᴍᴇ ᴏᴜᴛ. Pʟᴇᴀꜱᴇ ʀᴇꜱᴛᴀʀᴛ ᴡɪᴛʜ /text")

    if not cb.data.startswith("text_acc_"):
        return await cb.answer("Iɴᴠᴀʟɪᴅ ꜱᴇʟᴇᴄᴛɪᴏɴ ᴛᴏ ꜱᴀᴠᴇ ᴛᴇxᴛ.", show_alert=True)

    acc_index = int(cb.data.split("_")[-1])
    session = accounts[acc_index]["session"]
    await cb.message.delete()
  
    try:
        user_msg = await client.ask(
            chat_id=user_id,
            text="Send the message you want to save.\n\n**Don't add extra text — it will be treated as ad text.**",
            filters=filters.text | filters.caption,
            timeout=300
        )
    except ListenerTimeout:
        return await message.reply("❌ Timed out. Please start again using /text")

    text = user_msg.text or user_msg.caption or ""

    try:
        async with TelegramClient(StringSession(session), API_ID, API_HASH) as userbot:
            await userbot.send_message("me", text)
        await message.reply("Message saved to your Saved Messages.\n**Don't add other text — it will be treated as ad text.**")
    except Exception as e:
        await message.reply(f"Error while saving message: `{e}`")

@Client.on_message(filters.command("add_premium") & filters.user(Config.ADMIN))  # Replace with your admin ID
async def upgrade_user(client: Client, message: Message):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.reply("Usage: /add_premium user_id")
    
    target_id = int(parts[1])
    await db.update_user(target_id, {"is_premium": True})
    await message.reply(f"User `{target_id}` has been upgraded to Premium.")




@Client.on_message(filters.command("add_account") & filters.private)
async def add_account_handler(client: Client, message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if user and not user.get("is_premium", False) and len(user.get("accounts", [])) >= user.get("account_limit", int(FREE_ACCOUNT)):
        return await message.reply("Free users can only add one account. Upgrade to premium for more.")

    
    try:
        sessin = await client.ask(
            text="Please send your **Telethon StringSession**.\n\nTimeout in 30 seconds.",
            chat_id=user_id,
            filters=filters.text,
            timeout=30,
            disable_web_page_preview=True
        )
    except ListenerTimeout:
        return await message.reply_text(
            "⚠️ Error!!\n\n**Request timed out.**\nRestart by using /add_account",
            reply_to_message_id=message.id
        )

    try:
        usmsg = await client.ask(
            text="Send the message you want to save.\n\n**Don't add extra text — it will be treated as ad text.**",
            chat_id=user_id,
            filters=filters.text,
            timeout=60,
            disable_web_page_preview=True
        )
    except ListenerTimeout:
        return await message.reply_text(
            "⚠️ Error!!\n\n**Request timed out.**\nRestart by using /add_account",
            reply_to_message_id=message.id
        )

    string = sessin.text.strip()
    text = usmsg.text
    try:
        async with TelegramClient(StringSession(string), API_ID, API_HASH) as userbot:
            await userbot.send_message("me", text)
            me = await userbot.get_me()
        await message.reply("Message saved to your Saved Messages.\n**Don't add other text — it will be treated as ad text.**")
    except Exception as e:
        await message.reply(f"Invalid session string.\n\nError: `{e}`")
        await message.reply(f"Error while saving message: `{e}`")
        return

    existing_group = await db.group.find_one({"_id": me.id})
    if existing_group:
        return await message.reply("This account is already added.")
    
    if not user:
        user = {"_id": user_id, "accounts": []}

    user.setdefault("accounts", []).append({"session": string})
    await db.update_user(user_id, user)
    await message.reply("Account added successfully and validated.")
