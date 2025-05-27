from config import Config
from .start import db
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
import os
import sys
import time
import asyncio
import datetime
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telethon.errors.rpcerrorlist import FloodWaitError

@Client.on_message(filters.command('users') & filters.user(Config.ADMIN))
async def list_users(bot, message):
    syd = await message.reply('Getting list of users...')
    users = await db.get_all_users()

    out = "Users Saved In DB Are:\n\n"
    user_count = 0

    async for user in users:
        user_count += 1
        user_id = user["_id"]
        name = user.get("name", "Unknown")
        enabled = user.get("enabled", False)
        accounts = user.get("accounts", [])
        group_limit = user.get("group_limit", "Default")
        account_limit = user.get("account_limit", "Default")
        can_use_interval = user.get("can_use_interval", False)

        out += f"<a href='tg://user?id={user_id}'>{name}</a>\n"
        out += f"  └ Enabled: {enabled}\n"
        out += f"  └ Accounts: {len(accounts)} (Limit: {account_limit})\n"
        out += f"  └ Group Limit: {group_limit}, Can Use Interval: {can_use_interval}\n"

        for index, account in enumerate(accounts):
            try:
                session = account["session"]
                async with TelegramClient(StringSession(session), Config.API_ID, Config.API_HASH) as userbot:
                    me = await userbot.get_me()
                    out += f"    └ Account {index+1}: {me.first_name} [<code>{me.id}</code>]\n"

                    group_data = await db.group.find_one({"_id": me.id})
                    groups = group_data.get("groups", []) if group_data else []
                    for g in groups:
                        group_id = g["id"]
                        topic_id = g.get("topic_id")
                        interval = g.get("interval")
                        last = g.get("last_sent")
                        out += f"        └ Group ID: <code>{group_id}</code>"
                        if topic_id:
                            out += f", Topic: {topic_id}"
                        if interval:
                            out += f", Interval: {interval}s"
                        if last:
                            out += f", Last Sent: {last}"
                        out += "\n"
            except Exception as e:
                out += f"    └ Account {index+1}: [Error: {e}]\n"

        out += "\n"

        # Update progress every 10 users
        if user_count % 10 == 0:
            try:
                await syd.edit_text(f"Processed {user_count} users...")
            except:
                pass

    with open('users.txt', 'w+', encoding="utf-8") as f:
        f.write(out)
    await message.reply_document("users.txt", caption="List Of Users & Accounts")
    await syd.delete()

@Client.on_message(filters.command(["stats", "status"]) & filters.user(Config.ADMIN))
async def get_stats(bot, message):
    total_users = await db.total_users_count()
    uptime = time.strftime("%Hh%Mm%Ss", time.gmtime(
        time.time() - Config.BOT_UPTIME))
    start_t = time.time()
    st = await message.reply('**Aᴄᴄᴇꜱꜱɪɴɢ Tʜᴇ Dᴇᴛᴀɪʟꜱ.....**')
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000
    await st.edit(text=f"**--Bᴏᴛ Sᴛᴀᴛᴜꜱ--** \n\n**⌚️ Bᴏᴛ Uᴩᴛɪᴍᴇ:** {uptime} \n**🐌 Cᴜʀʀᴇɴᴛ Pɪɴɢ:** `{time_taken_s:.3f} ᴍꜱ` \n**🎐 Tᴏᴛᴀʟ Uꜱᴇʀꜱ:** `{total_users}`")


# Restart to cancell all process
@Client.on_message(filters.private & filters.command("restart") & filters.user(Config.ADMIN))
async def restart_bot(b, m):
    await m.reply_text("🔄__Rᴇꜱᴛᴀʀᴛɪɴɢ.....__")
    os.execl(sys.executable, sys.executable, *sys.argv)


@Client.on_message(filters.command("broadcast") & filters.user(Config.ADMIN) & filters.reply)
async def broadcast_handler(bot: Client, m: Message):
    await bot.send_message(Config.LOG_CHANNEL, f"{m.from_user.mention} or {m.from_user.id} Iꜱ ꜱᴛᴀʀᴛᴇᴅ ᴛʜᴇ Bʀᴏᴀᴅᴄᴀꜱᴛ......")
    all_users = await db.get_all_users()
    broadcast_msg = m.reply_to_message
    sts_msg = await m.reply_text("Bʀᴏᴀᴅᴄᴀꜱᴛ Sᴛᴀʀᴛᴇᴅ..!")
    done = 0
    failed = 0
    success = 0
    start_time = time.time()
    total_users = await db.total_users_count()
    async for user in all_users:
        sts = await send_msg(user['_id'], broadcast_msg)
        if sts == 200:
            success += 1
        else:
            failed += 1
        if sts == 400:
            await db.delete_user(user['_id'])
        done += 1
        if not done % 20:
            await sts_msg.edit(f"Bʀᴏᴀᴅᴄᴀꜱᴛ Iɴ Pʀᴏɢʀᴇꜱꜱ: \nTᴏᴛᴀʟ Uꜱᴇʀꜱ {total_users} \nCᴏᴍᴩʟᴇᴛᴇᴅ: {done} / {total_users}\nSᴜᴄᴄᴇꜱꜱ: {success}\nFᴀɪʟᴇᴅ: {failed}")
    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts_msg.edit(f"Bʀᴏᴀᴅᴄᴀꜱᴛ Cᴏᴍᴩʟᴇᴛᴇᴅ: \nCᴏᴍᴩʟᴇᴛᴇᴅ Iɴ `{completed_in}`.\n\nTᴏᴛᴀʟ Uꜱᴇʀꜱ {total_users}\nCᴏᴍᴩʟᴇᴛᴇᴅ: {done} / {total_users}\nSᴜᴄᴄᴇꜱꜱ: {success}\nFᴀɪʟᴇᴅ: {failed}")


async def send_msg(user_id, message):
    try:
        await message.forward(chat_id=int(user_id))
        return 200
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return send_msg(user_id, message)
    except InputUserDeactivated:
        print(f"{user_id} : Dᴇᴀᴄᴛɪᴠᴀᴛᴇᴅ")
        return 400
    except UserIsBlocked:
        print(f"{user_id} : Bʟᴏᴄᴋᴇᴅ Tʜᴇ Bᴏᴛ")
        return 400
    except PeerIdInvalid:
        print(f"{user_id} : Uꜱᴇʀ Iᴅ Iɴᴠᴀʟɪᴅ")
        return 400
    except Exception as e:
        print(f"{user_id} : {e}")
        return 500
