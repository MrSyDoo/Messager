import motor.motor_asyncio
from config import Config, Txt
import random, asyncio
from datetime import datetime, timedelta
from telethon.tl.functions.account import UpdateProfileRequest
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest


sessions = {}
API_HASH = Config.API_HASH
API_ID = Config.API_ID

class temp(object):
    ME = None
    U_NAME = None
    B_NAME = None
    
class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.used
        self.group = self.db.grp # <- new group collection for session-user group storage

    async def get_user(self, user_id):
        return await self.col.find_one({"_id": user_id})

    async def update_user(self, user_id, update: dict):
        await self.col.update_one({"_id": user_id}, {"$set": update}, upsert=True)
    
    async def get_all_users(self):
        return self.col.find({})  # returns an async cursor

    async def delete_user(self, user_id):
        await self.col.delete_one({"_id": user_id})

    async def del_user(self, user_id):
        await self.group.delete_one({"_id": user_id})

    async def total_users_count(self):
        return await self.col.count_documents({})

db = Database(Config.DB_URL, Config.DB_NAME)



async def start_forwarding(client, user_id):
    #Don't Use Directly
    user = await db.get_user(user_id)
    usr = await client.get_users(user_id)
    user_nam = f"For @{usr.username}" if usr.username else ""
    if not user or not user.get("accounts"):
        await client.send_message(user_id, "No userbot account found. Use /add_account first.")
        return
        
    syd = await client.send_message(user_id, "Starting...")

    is_premium = user.get("is_premium", False)

    clients = []
    user_groups = []

    for acc in user["accounts"]:
        session = StringSession(acc["session"])
        tele_client = TelegramClient(session, Config.API_ID, Config.API_HASH)
        await tele_client.start()
        clients.append(tele_client)

        me = await tele_client.get_me()
        session_user_id = me.id
        
        group_data = await db.group.find_one({"_id": session_user_id}) or {"groups": []}
        groups = group_data["groups"]
        user_groups.append(groups)

    if not any(user_groups):
        await client.send_message(user_id, "No groups selected. Use /groups to add some.")
        return

    sessions[user_id] = clients
    await db.update_user(user_id, {"enabled": True})
    await syd.delete()
    await client.send_message(user_id, "Forwarding started.")

    for i, tele_client in enumerate(clients):
        if i > 0:
            await asyncio.sleep(600)  # 10 minute delay between userbots

        groups = user_groups[i]
        meme = await tele_client.get_me()

        while True:
            if not (await db.get_user(user_id)).get("enabled", False):
                await client.send_message(user_id, "Stopped!")
                break
            try:
                if not is_premium:
                    expected_name = f"Bot is run by @{temp.U_NAME} " + user_nam
                    current_last_name = meme.last_name or ""
                    current_bio = (await tele_client(GetFullUserRequest(meme.id))).about or ""
                    message_lines = ["WARNING: You Have Changed Account Info. [Never Repeat Again. To Remove Ad Get Premium]"]
                    if current_last_name != expected_name:
                         message_lines.append(f"\nLast name is '{current_last_name}', updating to '{expected_name}'.")
                         update_needed = True

                    if expected_name not in current_bio:
                        message_lines.append(f"\nBio is '{current_bio}', updating to '{expected_name}'.")
                        update_needed = True
                        bio_edit = expected_name
                    else:
                        update_needed = False
                        bio_edit = current_bio

                    if update_needed:
                        await tele_client(UpdateProfileRequest(
                            last_name=expected_name,
                            about=bio_edit
                        ))  
                        await client.send_message(user_id, "\n".join(message_lines))
            except Exception as e:
                print(f"Failed to check user data: {e}")
            try:
                last_msg = (await tele_client.get_messages("me", limit=1))[0]
            except Exception as e:
                print(f"Failed to fetch message: {e}")
                await asyncio.sleep(60)
                continue

            for grp in groups:
                gid = grp["id"]
                topic_id = grp.get("topic_id")
                interval = 7200 if not is_premium else user.get("interval", 300)
                last_sent = grp.get("last_sent", datetime.min)

                total_wait = interval - (datetime.now() - last_sent).total_seconds()
                if total_wait > 0:
                    for _ in range(int(total_wait)):
                        if not (await db.get_user(user_id)).get("enabled", False):
                            await client.send_message(user_id, "Stopped!")
                            return
                        await asyncio.sleep(1)

                try:
                    await tele_client.send_message(
                        gid,
                        last_msg,
                        reply_to=topic_id if topic_id else None
                    )
                    grp["last_sent"] = datetime.now()
                    me = await tele_client.get_me()
                    await db.group.update_one({"_id": me.id}, {"$set": {"groups": groups}})
                except Exception as e:
                    print(f"Error sending to {gid}: {e}")

@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):
    if message.from_user.id in Config.BANNED_USERS:
        await message.reply_text("Sorry, You are banned.")
        return

    used = message.from_user
    user = await db.col.find_one({"_id": used.id})

    if not user:
        user_data = {
            "_id": used.id,
            "is_premium": False,
            "accounts": [],
            "enabled": False,
            "intervals": {},
        }
        await db.col.insert_one(user_data)
    button=InlineKeyboardMarkup([[
                InlineKeyboardButton('Gᴜɪᴅᴇ', callback_data='guide'),
                InlineKeyboardButton('Tɪᴇʀ', callback_data='tier')
            ], [
                InlineKeyboardButton('Iɴᴄʀᴇᴀꜱᴇ Lɪᴍɪᴛ', url='https://t.me/vizean'),
                InlineKeyboardButton('Gᴇɴᴇʀᴀᴛᴇ Sᴛʀɪɴɢ', url='https://t.me/snowstringgenbot')
            ], [
                InlineKeyboardButton('Aᴅᴅ Aᴄᴄᴏᴜɴᴛ', callback_data='add_account')
          ]])
    if Config.PICS:
        await message.reply_photo(random.choice(Config.PICS), caption=Txt.START_TXT.format(used.mention, temp.U_NAME, temp.B_NAME), reply_markup=button, parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply_text(text=Txt.START_TXT.format(used.mention, temp.U_NAME, temp.B_NAME), reply_markup=button, disable_web_page_preview=True)




@Client.on_message(filters.command("stop") & filters.private)
async def stop_forwarding(client, message):
    user_id = message.from_user.id
    await db.update_user(user_id, {"enabled": False})

    if user_id in sessions:
        for tele_client in sessions[user_id]:
            await tele_client.disconnect()
        sessions.pop(user_id)

    await message.reply("Trying To Stop.")
    
@Client.on_message(filters.command("run") & filters.private)
async def run_forarding(client, message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    usr = await client.get_users(user_id)
    user_nam = f"For @{usr.username}" if usr.username else ""
    if not user or not user.get("accounts"):
        return await message.reply("No userbot account found. Use /add_account first.")

    if user.get("enabled", False):
        return await message.reply("Forwarding already running. Use /stop to end it before starting again.")

    syd = await message.reply("Starting...")

    is_premium = user.get("is_premium", False)
    
    clients = []
    user_groups = []

    for acc in user["accounts"]:
        session = StringSession(acc["session"])
        tele_client = TelegramClient(session, Config.API_ID, Config.API_HASH)
        await tele_client.start()
        clients.append(tele_client)

        # Get the account's own user ID to fetch groups from group collection
        me = await tele_client.get_me()
        session_user_id = me.id
        username = f"For @{message.from_user.username}" if message.from_user.username else " "
        
        group_data = await db.group.find_one({"_id": session_user_id}) or {"groups": []}
        groups = group_data["groups"]
        user_groups.append(groups)

    if not any(user_groups):
        return await message.reply("No groups selected. Use /groups to add some.")

    sessions[user_id] = clients
    await db.update_user(user_id, {"enabled": True})
    await syd.delete()
    await message.reply("Forwarding started.")

    for i, tele_client in enumerate(clients):
        if i > 0:
            await asyncio.sleep(600)  # 10 minute delay between userbots
        groups = user_groups[i]
        meme = await tele_client.get_me()
        while True:
            interval = 1
            total_slep = 60
            if not (await db.get_user(user_id)).get("enabled", False):
                await message.reply("Stopped!")
                break  # stop if disabled
            try:
                if not is_premium:
                    expected_name = f"Bot is run by @{temp.U_NAME} " + user_nam
                    current_last_name = meme.last_name or ""
                    full = await tele_client(GetFullUserRequest(meme.id))
                    current_bio = full.full_user.about or ""
                    message_lines = ["WARNING: You Have Changed Account Info. [Never Repeat Again. To Remove Ad Get Premium]"]
                    if current_last_name != expected_name:
                         message_lines.append(f"\nLast name is '{current_last_name}', updating to '{expected_name}'.")
                         update_needed = True

                    if expected_name not in current_bio:
                        message_lines.append(f"\nBio is '{current_bio}', updating to '{expected_name}'.")
                        update_needed = True
                        bio_edit = expected_name
                    else:
                        update_needed = False
                        bio_edit = current_bio

                    if update_needed:
                        await tele_client(UpdateProfileRequest(
                            last_name=expected_name,
                            about=bio_edit
                        ))  
                        await message.reply("\n".join(message_lines))
            except Exception as e:
                await message.reply(f"Error in Getting Message: {e} ")
                print(f"Failed to check user data: {e}")
            try:
                last_msg = (await tele_client.get_messages("me", limit=1))[0]
            except Exception as e:
                print(f"Failed to fetch message: {e}")
                await message.reply(f"Error in Getting Message: {e} ")
                for _ in range(total_slep // interval):
                    if not (await db.get_user(user_id)).get("enabled", False):
                        await message.reply("Stopped!")
                        break
                    await asyncio.sleep(interval)
                
                continue

            for grp in groups:
                gid = grp["id"]
                topic_id = grp.get("topic_id")
                interval = 10 if not is_premium else user.get("interval", 300)
                last_sent = grp.get("last_sent", datetime.min)
                total_wait = interval - (datetime.now() - last_sent).total_seconds()
                if total_wait > 0:
                    # Wait total_wait seconds but check every 1 second if enabled
                    for _ in range(int(total_wait)):
                        if not (await db.get_user(user_id)).get("enabled", False):
                            await client.send_message(user_id, "Stopped!")
                            return
                        await asyncio.sleep(1)
                try:
                    await tele_client.send_message(
                        gid,
                        last_msg,
                        reply_to=topic_id if topic_id else None
                    )
                    grp["last_sent"] = datetime.now()
                    me = await tele_client.get_me()
                    await db.group.update_one({"_id": me.id}, {"$set": {"groups": groups}})
                except Exception as e:
                    print(f"Error sending to {gid}: {e}")
                    await message.reply(f"Error sending to {gid}:\n{e} \nSend This Message To The Admin, To Take Proper Action, Forwarding Won't Stop.[Never Let The Account Get Banned Due To Spam]")
            for _ in range(total_slep // interval):
                if not (await db.get_user(user_id)).get("enabled", False):
                    await message.reply("Stopped!")
                    break
                await asyncio.sleep(interval)



@Client.on_message(filters.command("groups") & filters.private)
async def show_accounts(client: Client, message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user or not user.get("accounts"):
        return await message.reply("Please add an account first using /add_account")
    accounts = user["accounts"]
    buttons = []
    for i, acc in enumerate(accounts):
        try:
            async with TelegramClient(StringSession(acc["session"]), Config.API_ID, Config.API_HASH) as userbot:
                me = await userbot.get_me()
                acc_name = me.first_name or me.username or f"Account {i+1}"
        except Exception:
            acc_name = f"Account {i+1} (invalid)"
        buttons.append([
            InlineKeyboardButton(acc_name, callback_data=f"choose_account_{i}")
        ])
    await message.reply(
        "Choose an account to manage groups:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_message(filters.command("set_interval") & filters.private)
async def set_interval(client, message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user or not user.get("is_premium", False):
        return await message.reply("Only premium users can set custom intervals.")
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply("Usage: /setinterval <seconds>")
    try:
        seconds = int(parts[1])
    except ValueError:
        return await message.reply("Interval must be a number in seconds.")

    await db.col.update_one({"_id": user_id}, {"$set": {"interval": seconds}})
    await message.reply(f"Custom interval set to {seconds} seconds for all groups.")



@Client.on_message(filters.command("remove_premium") & filters.user(Config.ADMIN))
async def remove_premium(client, message):
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply("Usage: /remove_premium <user_id>")
    try:
        user_id = int(parts[1])
    except:
        return await message.reply("Invalid user ID.")

    await db.col.update_one({"_id": user_id}, {"$set": {"is_premium": False}})
    await message.reply(f"Premium removed from user `{user_id}`", parse_mode="markdown")


@Client.on_message(filters.command("interval") & filters.private)
async def view_interval(client, message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        return await message.reply("User not found.")

    if user.get("is_premium", False):
        interval = user.get("interval", "Not set")
        return await message.reply(f"Your custom interval is: `{interval}` seconds", parse_mode="markdown")
    else:
        return await message.reply("You are a free user. Default interval is 2 hours.")

@Client.on_message(filters.command("delete_account") & filters.private)
async def delete_account_handler(client, message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user or not user.get("accounts"):
        return await message.reply("Please add an account first using /add_account")
    accounts = user["accounts"]
    buttons = []
    for i, acc in enumerate(accounts):
        try:
            async with TelegramClient(StringSession(acc["session"]), Config.API_ID, Config.API_HASH) as userbot:
                me = await userbot.get_me()
                acc_name = me.first_name or me.username or f"Account {i+1}"
        except Exception:
            acc_name = f"Account {i+1} (invalid)"

        buttons.append([
            InlineKeyboardButton(f"Delete {acc_name}", callback_data=f"choose_delete_{i}")
        ])

    await message.reply(
        "Select the account you want to delete:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
