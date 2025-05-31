import motor.motor_asyncio
from config import Config, Txt
import random, asyncio
from collections import defaultdict
import pytz
from datetime import datetime, timedelta
from telethon.tl.functions.account import UpdateProfileRequest
from pyrogram import Client, filters, enums
from telethon.tl.functions.channels import GetForumTopicsRequest
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
india = pytz.timezone("Asia/Kolkata")

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
        self.group = self.db.grp
        self.user_messages = self.db.messag

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

async def start_forwarding_process(client: Client, user_id: int, user: dict):
    syd = await client.send_message(user_id, "Sᴛᴀʀɪɴɢ....")
    is_premium = user.get("is_premium", False)
    can_use_interval = user.get("can_use_interval", False)

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
        await syd.delete()
        return await client.send_message(user_id, "Nᴏ ɢʀᴏᴜᴩꜱ ꜱᴇʟᴇᴄᴛᴇᴅ. Uꜱᴇ /groups ᴛᴏ ᴀᴅᴅ ꜱᴏᴍᴇ.")

    sessions[user_id] = clients
    await db.update_user(user_id, {"enabled": True})
    await syd.delete()
    await client.send_message(user_id, "Fᴏʀᴡᴀʀᴅɪɴɢ ꜱᴛᴀʀᴛᴇᴅ.")

    account_group_summary = ""

    for i, tele_client in enumerate(clients):
        groups = user_groups[i]
        mee = await tele_client.get_me()
        groupdata = await db.group.find_one({"_id": mee.id})
        if i != 0:
            wait_time = groupdata.get("interval", 300)
            await asyncio.sleep(wait_time)
        asyncio.create_task(
            start_forwarding_loop(tele_client, user_id, groups, is_premium, can_use_interval, client, i)
        )
        me = await tele_client.get_me()
        account_name = me.first_name or me.username or "Unknown"
        group_lines = []

        for group in groups:
            try:
                entity = await tele_client.get_entity(group["id"])
                group_title = entity.title if hasattr(entity, "title") else str(group["id"])

                if "topic_id" in group:
                    topics = await tele_client(GetForumTopicsRequest(
                        channel=entity,
                        offset_date=0,
                        offset_id=0,
                        offset_topic=0,
                        limit=100
                    ))
                    topic = next((t for t in topics.topics if t.id == group["topic_id"]), None)
                    if topic:
                        group_title += f" ({topic.title})"
                    else:
                        group_title += f" (Topic ID: {group['topic_id']})"

                group_lines.append(f"  - {group_title}")
            except Exception:
                group_lines.append(f"  - Failed to fetch group {group.get('id')}")

        account_group_summary += f"\n<b>{account_name}</b>:\n" + "\n".join(group_lines) + "\n"

    if account_group_summary.strip():
        await client.send_message(
            user_id,
            f"<b>Accounts and Groups For Forwarding:</b>\n{account_group_summary}\n\nSend /stop to stop the process",
            parse_mode=enums.ParseMode.HTML
        )
    try:
        usr = await client.get_users(user_id)
        await client.send_message(
            Config.LOG_CHANNEL,
            f"#Process \n🧊 Fᴏʀᴡᴀʀᴅɪɴɢ ꜱᴛᴀʀᴛᴇᴅ ʙʏ <a href='tg://user?id={user_id}'>{usr.first_name}</a> (User ID: <code>{user_id}</code>)\n\n{account_group_summary}",
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass


async def start_forwarding_loop(tele_client, user_id, groups, is_premium, can_use_interval, client, index):
    if index > 0:
        await client.send_message(user_id, f"Sᴛᴀʀɪɴɢ {index + 1}")
    usr = await client.get_users(user_id)
    user_nam = f"For @{usr.username}" if usr.username else ""

    while True:
        interval = 1
        total_slep = 20
        if not (await db.get_user(user_id)).get("enabled", False):
            break

        try:
            if not is_premium:
                meme = await tele_client.get_me()
                expected_name = f"Bot is run by @{temp.U_NAME} " + user_nam
                current_last_name = meme.last_name or ""
                full = await tele_client(GetFullUserRequest(meme.id))
                current_bio = full.full_user.about or ""
                message_lines = ["WARNING: You Have Changed Account Info. [Never Repeat Again. To Remove Ad Get Premium]"]
                update_needed = False
                bio_edit = current_bio

                if current_last_name != expected_name:
                    message_lines.append(f"\nLast name is '{current_last_name}', updating to '{expected_name}'.")
                    update_needed = True

                if current_bio != expected_name:
                    message_lines.append(f"\nBio is '{current_bio}', updating to '{expected_name}'.")
                    update_needed = True
                    bio_edit = expected_name

                if update_needed:
                    await tele_client(UpdateProfileRequest(
                        last_name=expected_name,
                        about=bio_edit
                    ))
                    await client.send_message(user_id, "\n".join(message_lines))
        except Exception as e:
            await client.send_message(user_id, f"Error in Getting Message: {e}")
            print(f"Failed to check user data: {e}")

        try:
            forward_entry = await db.get_user(user_id)
            use_forward = forward_entry.get("forward_message_id", None)
            if use_forward:
                msg_id = forward_entry.get("forward_message_id")
                last_msg = await tele_client.get_messages(entity=Config.MES_CHANNEL, ids=msg_id)
                #use_forward = True
            else:
                last_msg = (await tele_client.get_messages("me", limit=1))[0]
               # use_forward = False
        except Exception as e:
            print(f"Failed to fetch message: {e}")
            await client.send_message(user_id, f"Error in Getting Message: {e}")
            for _ in range(total_slep // interval):
                if not (await db.get_user(user_id)).get("enabled", False):
                    break
                await asyncio.sleep(interval)
            continue

        for grp in groups:
            gid = grp["id"]
            topic_id = grp.get("topic_id")
            interval = grp.get("interval", 300 if (is_premium or can_use_interval) else 7200)
            last_sent = grp.get("last_sent", datetime.min)
            total_wait = interval - (datetime.now() - last_sent).total_seconds()
            if total_wait > 0:
                # Wait total_wait seconds but check every 1 second if enabled
                for _ in range(int(total_wait)):
                    if not (await db.get_user(user_id)).get("enabled", False):
                        break
                    await asyncio.sleep(1)
            try:
                if use_forward:
                    await tele_client.forward_messages(
                        entity=gid,
                        messages=last_msg.id,
                        from_peer=Config.MES_CHANNEL
                     #   reply_to=topic_id if topic_id else None
                    )
                else:
                    await tele_client.send_message(
                        gid,
                        last_msg,
                        reply_to=topic_id if topic_id else None
                    )
                grp["last_sent"] = datetime.now()
                me = await tele_client.get_me()
                await db.group.update_one({"_id": me.id}, {"$set": {"groups": groups}})
                await db.user_messages.insert_one({
                    "user_id": user_id,
                    "group_id": gid,
                    "time": datetime.now(tz=india)
                    })
            except Exception as e:
                try:
                    if not (await db.get_user(user_id)).get("enabled", False):
                        break
                    entty = await tele_client.get_entity(gid)
                    grop_name = getattr(entity, "title", str(gid))
                except Exception:
                    grop_name = str(gid)
                print(f"Error sending to {grop_name}: {e}")
                await client.send_message(user_id, f"Error sending to {gid}:\n{e} \nSend This Message To The Admin, To Take Proper Action, Forwarding Won't Stop.[Never Let The Account Get Banned Due To Spam]")

        for _ in range(total_slep // interval):
            if not (await db.get_user(user_id)).get("enabled", False):
                break
            await asyncio.sleep(interval)

    await client.send_message(user_id, f"Sᴛᴏᴩᴩᴇᴅ..! {index+1}")
    await db.update_user(user_id, {"forward_message_id": None})
    if index > 0:
        return
    syd = await client.send_message(user_id, "Sᴇɴᴅɪɴɢ ꜰᴏʀᴡᴀʀᴅ ᴅᴀᴛᴀ...")

    entries = await db.user_messages.find({"user_id": user_id}).to_list(None)
    if not entries:
        return await syd.edit("No forwarding data found for this user.")

    grouped = defaultdict(list)
    for entry in entries:
        group_id = entry.get("group_id")
        timestamp = entry.get("time")
        if isinstance(timestamp, datetime):
            timestamp = timestamp.astimezone(india)
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S IST")
        else:
            timestamp_str = str(timestamp)
        grouped[group_id].append(timestamp_str)
    for group_id in grouped:
        grouped[group_id].sort()
    out = f"User ID: {user_id}\n"
    for group_id, times in grouped.items():
        out += f"  => Group ID: {group_id}\n"
        for t in times:
            out += f"    - {t}\n"
    with open("forward.txt", "w", encoding="utf-8") as f:
        f.write(out)

    await client.send_document(user_id, "forward.txt", caption=f"Fᴏʀᴡᴀʀᴅ ʟᴏɢꜱ: {index+1}")
    await db.user_messages.delete_many({"user_id": user_id})
    await syd.delete()



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
    can_use_interval = user.get("can_use_interval", False)
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
        groups = user_groups[i]
        mee = await tele_client.get_me()
        groupdata = await db.group.find_one({"_id": mee.id})
        if i != 0:
            wait_time = groupdata.get("interval", 300)
            await asyncio.sleep(wait_time)
        asyncio.create_task(
            start_forwarding_loop(tele_client, user_id, groups, is_premium, can_use_interval, client, i)
        )
        

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
            "name": used.first_name,
            "accounts": [],
            "enabled": False,
            "intervals": {},
        }
        await db.col.insert_one(user_data)
        try:
            await client.send_message(
                Config.LOG_CHANNEL,
                f"#New_User \nUser: <a href='tg://user?id={user_id}'>{used.first_name}</a> \n(User ID: <code>{user_id}</code>)",
                parse_mode=enums.ParseMode.HTML
            )
        except:
            pass
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
async def run_forwarding(client: Client, message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    usr = await client.get_users(user_id)
    user_nam = f"For @{usr.username}" if usr.username else ""
    if not user or not user.get("accounts"):
        return await message.reply("No userbot account found. Use /add_account first.")

    if user.get("enabled", False):
        return await message.reply("Fᴏʀᴡᴀʀᴅɪɴɢ ᴀʟʀᴇᴀᴅʏ ʀᴜɴɴɪɴɢ. Uꜱᴇ /stop ᴛᴏ ᴇɴᴅ ɪᴛ ʙᴇꜰᴏʀᴇ ꜱᴛᴀʀᴛɪɴɢ ᴀɢᴀɪɴ.")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Fᴏʀᴡᴀʀᴅ : Sᴀᴠᴇᴅ Mᴇꜱꜱᴀɢᴇ", callback_data="normal")
        ], [
            InlineKeyboardButton("Fᴏʀᴡᴀʀᴅ : Wɪᴛʜ Tᴀɢ", callback_data="forward")
        ]
    ])
    choose = await message.reply(
        "Hᴏᴡ ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ꜱᴇɴᴅ ᴛʜᴇ ᴍᴇꜱꜱᴀɢᴇ?\nCʟɪᴄᴋ ᴏɴ ꜱᴀᴠᴇᴅ ᴍᴇꜱꜱᴀɢᴇ ᴛᴏ ꜱᴇɴᴅ ʟᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ ꜱᴀᴠᴇᴅ ʙʏ ᴛʜᴇ ᴜꜱᴇʀ ʙᴏᴛ\nCʟɪᴄᴋ ᴏɴ ᴡɪᴛʜ ᴛᴀɢ ɪꜰ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ꜱᴇɴᴅ ᴍᴇꜱꜱᴀɢᴇ ᴡɪᴛʜ ᴛʜᴇ ꜰᴏʀᴡᴀʀᴅ ᴛᴀɢ [ʏᴏᴜ ʜᴀᴠᴇ ᴛᴏ ɢɪᴠᴇ ᴛʜᴇ ɪɴᴩᴜᴛ ꜰᴏʀ ᴛʜᴀᴛ] \nCʜᴏᴏꜱᴇ ᴀɴ ᴏᴩᴛɪᴏɴ ʙᴇʟᴏᴡ (timeout 60s):",
        reply_markup=keyboard
    )
    await asyncio.sleep(60)
    try:
        await choose.delete()
    except:
        pass
    return
   
@Client.on_message(filters.command(["interval", "group_limit", "account_limit"]) & filters.user(Config.ADMIN))
async def admin_command(client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text(
            "Usage:\n"
            "/interval y/n user_id\n"
            "/group_limit <number> user_id\n"
            "/account_limit <number> user_id"
        )

    command = message.command[0].lower()
    value = message.command[1]
    try:
        user_id = int(message.command[2])
    except ValueError:
        return await message.reply_text("Invalid user_id. Please provide a valid number.")

    user = await db.col.find_one({"_id": user_id})
    if not user:
        return await message.reply_text("User not found in database.")

    update = {}

    if command == "interval":
        if value.lower() not in ["y", "n"]:
            return await message.reply_text("Value must be 'y' or 'n'.")
        update["can_use_interval"] = value.lower() == "y"

    elif command == "group_limit":
        if not value.isdigit():
            return await message.reply_text("Group limit must be a digit.")
        update["group_limit"] = int(value)

    elif command == "account_limit":
        if not value.isdigit():
            return await message.reply_text("Account limit must be a digit.")
        update["account_limit"] = int(value)

    await db.col.update_one({"_id": user_id}, {"$set": update})
    await message.reply_text(f"Updated `{command}` settings for user `{user_id}`.")


@Client.on_message(filters.command("account") & filters.private)
async def show_accounts_interval(client: Client, message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user or not user.get("accounts"):
        return await message.reply("❗ Please add an account first using /add_account")

    accounts = user["accounts"]

    if len(accounts) == 1:
        return await message.reply("⚠️ You only have one account. Interval applies only when multiple accounts are used.")

    buttons = []
    for i, acc in enumerate(accounts):
        try:
            async with TelegramClient(StringSession(acc["session"]), Config.API_ID, Config.API_HASH) as userbot:
                me = await userbot.get_me()
                acc_name = me.first_name or me.username or f"Account {i+1}"
        except Exception:
            acc_name = f"Account {i+1} (invalid)"
        buttons.append([
            InlineKeyboardButton(f"{acc_name}", callback_data=f"set_interval_account_{i}")
        ])

    await message.reply(
        "🕒 Choose an account to set the default interval:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


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

@Client.on_message(filters.command("remove_premium") & filters.user(Config.ADMIN))
async def remove_premium(client, message):
    parts = message.text.split()
    if len(parts) != 2:
        return await message.reply("Usage: /remove_premium user_id")
    try:
        user_id = int(parts[1])
    except:
        return await message.reply("Invalid user ID.")

    await db.col.update_one({"_id": user_id}, {"$set": {"is_premium": False}})
    await message.reply(f"Premium removed from user `{user_id}`", parse_mode=enums.ParseMode.HTML)



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



