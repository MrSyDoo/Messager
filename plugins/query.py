import shutil
import time
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from config import Config, Txt
from .start import db, temp
import random
from pyromod.exceptions import ListenerTimeout
from telethon.tl.functions.channels import GetForumTopicsRequest
import psutil
from telethon.sessions import StringSession
from telethon import TelegramClient
from datetime import datetime

FREE_ACCOUNT = Config.FREE_ACCOUNT
FREE_GROUP = Config.FREE_GROUP


async def toggle_group_directly(tg_client, user, group_id, session_user_id, query, account_index):
    from datetime import datetime
    group_data = await db.group.find_one({"_id": session_user_id}) or {"_id": session_user_id, "groups": []}
    group_list = group_data["groups"]
    exists = next((g for g in group_list if g["id"] == group_id), None)
    if exists:
        group_list.remove(exists)
        status = "❌"
        message = "Group removed"
    else:
        is_premium = user.get("is_premium", False)
        limit = FREE_GROUP if not is_premium else 1000
        if len(group_list) >= limit:
            return await query.answer("Group limit reached.", show_alert=True)
        group_list.append({"id": group_id, "last_sent": datetime.min})
        status = "✅"
        message = "Group added"

    await db.group.update_one({"_id": session_user_id}, {"$set": {"groups": group_list}}, upsert=True)
    await query.answer(message + " " + status, show_alert=False)
    await query.message.delete()
    await show_groups_for_account(tg_client, query.message, query.from_user.id, account_index)

async def show_groups_for_account(client, message, user_id, account_index):
    user = await db.get_user(user_id)
    session_str = user["accounts"][account_index]["session"]
    async with TelegramClient(StringSession(session_str), Config.API_ID, Config.API_HASH) as tg_client:
        me = await tg_client.get_me()
        
        session_user_id = me.id
        group_data = await db.group.find_one({"_id": session_user_id}) or {}
       
        enabled_ids = {g["id"] for g in group_data.get("groups", [])}
        dialogs = await tg_client.get_dialogs()
        buttons = []

        for d in dialogs:
            if d.is_group or (d.is_channel and getattr(d.entity, "megagroup", False)):
                is_enabled = "✅" if d.id in enabled_ids else " "
                title = f"{d.name} {is_enabled}"
                buttons.append([
                    InlineKeyboardButton(title, callback_data=f"group_{d.id}_{account_index}")
                ])

        buttons.append([
            InlineKeyboardButton("⇇ Gᴏ Bᴀᴄᴋ", callback_data="back_to_accounts"),
            InlineKeyboardButton("↻ Rᴇꜱᴇᴛ ↻", callback_data=f"delete_all_{account_index}")
        ])
        await message.reply("Sᴇʟᴇᴄᴛ ʏᴏᴜʀ ɢʀᴏᴜᴩꜱ ᴛᴏ ꜰᴏʀᴡᴀʀᴅ:", reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    if data == "start":
        await query.message.edit_media(
            InputMediaPhoto(
                random.choice(Config.PICS),
                Txt.START_TXT.format(query.from_user.mention, temp.U_NAME, temp.B_NAME),

            ),

            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton('Gᴜɪᴅᴇ', callback_data='guide'),
                InlineKeyboardButton('Tɪᴇʀ', callback_data='tier')
            ], [
                InlineKeyboardButton('Iɴᴄʀᴇᴀꜱᴇ Lɪᴍɪᴛ', url='https://t.me/vizean'),
                InlineKeyboardButton('Gᴇɴᴇʀᴀᴛᴇ Sᴛʀɪɴɢ', url='https://t.me/snowstringgenbot')
            ], [
                InlineKeyboardButton('Aᴅᴅ Aᴄᴄᴏᴜɴᴛ', callback_data='add_account')
            ]])
        )

    elif data.startswith("choose_account_"):
        index = int(data.split("_")[-1])
        await query.message.delete()
        await show_groups_for_account(client, query.message, user_id, index)

    # === Go Back ===
    elif data == "back_to_accounts":
        user = await db.get_user(query.from_user.id)
        accounts = user.get("accounts", [])
        buttons = []

        for i, acc in enumerate(accounts):
            try:
                async with TelegramClient(StringSession(acc["session"]), Config.API_ID, Config.API_HASH) as userbot:
                    me = await userbot.get_me()
                    acc_name = me.first_name or me.username or f"Account {i+1}"
            except Exception:
                acc_name = f"Account {i+1} (invalid)"

            buttons.append([InlineKeyboardButton(acc_name, callback_data=f"choose_account_{i}")])

        await query.message.edit_text(
            "Choose an account:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # === Group Selection ===
    elif data.startswith("group_"):
        parts = data.split("_")
        group_id = int(parts[1])
        account_index = int(parts[2])

        user = await db.get_user(query.from_user.id)
        is_premium = user.get("is_premium", False)
        can_use_interval = user.get("can_use_interval", False)
        session_str = user["accounts"][account_index]["session"]

        async with TelegramClient(StringSession(session_str), Config.API_ID, Config.API_HASH) as tg_client:
            me = await tg_client.get_me()
            session_user_id = me.id

            entity = await tg_client.get_entity(group_id)

            if not getattr(entity, "forum", False):
                group_data = await db.group.find_one({"_id": session_user_id}) or {"_id": session_user_id, "groups": []}
                group_list = group_data["groups"]
                limit = FREE_GROUP if not is_premium else 1000
                if len(group_list) >= int(limit):
                    return await query.answer("Group limit reached.", show_alert=True)

                interval_value = None
                try:
                    await query.message.reply(
                        "Pʟᴇᴀꜱᴇ Sᴇɴᴅ Iɴᴛᴇʀᴠᴀʟ (ɪɴ ꜱᴇᴄᴏɴᴅꜱ) or type /delete to remove this group.\n\nTɪᴍᴇᴏᴜᴛ ɪɴ 30 ꜱᴇᴄᴏɴᴅꜱ."
                    )
                    response = await client.listen(
                        chat_id=query.from_user.id,
                        filters=filters.text,
                        timeout=30
                    )
                    text = response.text.strip().lower()

                    if text == "/delete":
                        group_list = [g for g in group_list if g["id"] != group_id]
                        await db.group.update_one({"_id": session_user_id}, {"$set": {"groups": group_list}})
                        await query.message.reply_text("✅ Group deleted.")
                        return await show_groups_for_account(client, query.message, query.from_user.id, account_index)

                    if is_premium or can_use_interval:
                        interval_value = int(text)
                    else:
                        return await query.message.reply_text("Interval Only For Limited Users.")
                        

                except ListenerTimeout:
                    return await query.message.reply_text("⚠️ Error!!\n\n**Request timed out.**")
                except ValueError:
                    return await query.message.reply_text("⚠️ Error!!\n\n**Invalid number format.**")

                updated = False
                for g in group_list:
                    if g["id"] == group_id:
                        if interval_value is not None:
                            g["interval"] = interval_value
                        updated = True
                        break

                if not updated:
                    new_group = {"id": group_id, "last_sent": datetime.min}
                    if interval_value is not None:
                        new_group["interval"] = interval_value
                    group_list.append(new_group)

                await db.group.update_one({"_id": session_user_id}, {"$set": {"groups": group_list}}, upsert=True)
                await query.answer("Gʀᴏᴜᴩ ᴇɴᴀʙʟᴇᴅ ✅", show_alert=True)
                await query.message.delete()
                await show_groups_for_account(client, query.message, query.from_user.id, account_index)

            else:
                try:
                    topics = await tg_client(GetForumTopicsRequest(
                        channel=entity,
                        offset_date=0,
                        offset_id=0,
                        offset_topic=0,
                        limit=100
                    ))

                    group_data = await db.group.find_one({"_id": session_user_id}) or {"_id": session_user_id, "groups": []}
                    group_list = group_data["groups"]
                    selected_topic = next((g.get("topic_id") for g in group_list if g["id"] == group_id), None)

                    topic_buttons = []
                    for topic in topics.topics:
                        selected = " ✅" if topic.id == selected_topic else ""
                        topic_buttons.append([
                            InlineKeyboardButton(
                                topic.title + selected,
                                callback_data=f"topic_{group_id}_{account_index}_{topic.id}"
                            )
                        ])
                    topic_buttons.append([
                        InlineKeyboardButton("⇇ Gᴏ Bᴀᴄᴋ", callback_data=f"choose_account_{account_index}")
                    ])
                    await query.message.edit_text("Select a topic:", reply_markup=InlineKeyboardMarkup(topic_buttons))

                except Exception as e:
                    print(f"Failed to fetch topics: {e}")
                    await query.answer("Failed to fetch topics.", show_alert=True)


    elif data.startswith("topic_"):
        parts = data.split("_")
        group_id = int(parts[1])
        account_index = int(parts[2])
        topic_id = int(parts[3])

        user = await db.get_user(query.from_user.id)
        is_premium = user.get("is_premium", False)
        can_use_interval = user.get("can_use_interval", False)
        session_str = user["accounts"][account_index]["session"]

        async with TelegramClient(StringSession(session_str), Config.API_ID, Config.API_HASH) as tg_client:
            me = await tg_client.get_me()
            session_user_id = me.id

            group_data = await db.group.find_one({"_id": session_user_id}) or {"_id": session_user_id, "groups": []}
            group_list = group_data["groups"]
            limit = FREE_GROUP if not is_premium else 1000
            if len(group_list) >= int(limit):
                return await query.answer("Group limit reached.", show_alert=True)

            interval_value = None
            try:
                await query.message.reply(
                    "Pʟᴇᴀꜱᴇ Sᴇɴᴅ Iɴᴛᴇʀᴠᴀʟ (ɪɴ ꜱᴇᴄᴏɴᴅꜱ) or type /delete to remove this group.\n\nTɪᴍᴇᴏᴜᴛ ɪɴ 30 ꜱᴇᴄᴏɴᴅꜱ."
                )
                response = await client.listen(
                    chat_id=query.from_user.id,
                    filters=filters.text,
                    timeout=30
                )
                text = response.text.strip().lower()

                if text == "delete":
                    group_list = [g for g in group_list if g["id"] != group_id]
                    await db.group.update_one({"_id": session_user_id}, {"$set": {"groups": group_list}})
                    await query.message.reply_text("✅ Group deleted.")
                    return await show_groups_for_account(client, query.message, query.from_user.id, account_index)

                if is_premium or can_use_interval:
                    interval_value = int(text)
                else:
                    return await query.message.reply_text("Interval Only For Limited Users.")
                        

            except ListenerTimeout:
                return await query.message.reply_text("⚠️ Error!!\n\n**Request timed out.**")
            except ValueError:
                return await query.message.reply_text("⚠️ Error!!\n\n**Invalid number format.**")

            updated = False
            for g in group_list:
                if g["id"] == group_id:
                    g["topic_id"] = topic_id
                    if interval_value is not None:
                        g["interval"] = interval_value
                    updated = True
                    await query.answer("Tᴏᴩɪᴄ ᴜᴩᴅᴀᴛᴇᴅ ✅", show_alert=True)
                    break

            if not updated:
                new_group = {
                    "id": group_id,
                    "topic_id": topic_id,
                    "last_sent": datetime.min
                }
                if interval_value is not None:
                    new_group["interval"] = interval_value
                group_list.append(new_group)
                await query.answer("Gʀᴏᴜᴩ ᴡɪᴛʜ ᴛᴏᴩɪᴄ ᴀᴅᴅᴇᴅ ✅", show_alert=True)

            await db.group.update_one({"_id": session_user_id}, {"$set": {"groups": group_list}}, upsert=True)

        await query.message.delete()
        await show_groups_for_account(client, query.message, query.from_user.id, account_index)


    elif data.startswith("delete_all_"):
        account_index = int(data.split("_")[2])
        user = await db.get_user(query.from_user.id)
        session_str = user["accounts"][account_index]["session"]

        async with TelegramClient(StringSession(session_str), Config.API_ID, Config.API_HASH) as tg_client:
            me = await tg_client.get_me()
            session_user_id = me.id

            # Clear all groups for this session user
            await db.group.update_one({"_id": session_user_id}, {"$set": {"groups": []}}, upsert=True)
            await query.answer("All group data deleted.", show_alert=True)
            await query.message.delete()
            await show_groups_for_account(client, query.message, query.from_user.id, account_index)

    elif data == "help":

        await query.message.edit_media(
            InputMediaPhoto(
                random.choice(Config.PICS),
                Txt.HELP_TXT

            ),

            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("ᐊ ʙᴀᴄᴋ", callback_data="start"),
                InlineKeyboardButton("✘ ᴄʟᴏsᴇ", callback_data="close")
                
            ]])
        )

   

    elif data == "add_account":
        user_id = query.from_user.id
        user = await db.get_user(user_id)

        if user and not user.get("is_premium", False) and len(user.get("accounts", [])) >= user.get("account_limit", int(FREE_ACCOUNT)):
            return await query.message.reply("Free users can only add one account. Upgrade to premium for more.")

        try:
            await query.message.reply("Please send your **Telethon StringSession**.\n\nTimeout in 30 seconds.")
            sessin = await client.listen(
                chat_id=user_id,
                filters=filters.text,
                timeout=30
            )
        except ListenerTimeout:
            return await query.message.reply_text(
                "⚠️ Error!!\n\n**Request timed out.**\nRestart by using 'Add Account' again."
            )

        try:
            await query.message.reply("Send the message you want to save.\n\n**Don't add extra text — it will be treated as ad text.**")
            usmsg = await client.listen(
                chat_id=user_id,
                filters=filters.text,
                timeout=60
            )
        except ListenerTimeout:
            return await query.message.reply_text(
                "⚠️ Error!!\n\n**Request timed out.**\nRestart by using 'Add Account' again."
            )

        string = sessin.text.strip()
        text = usmsg.text

        try:
            async with TelegramClient(StringSession(string), Config.API_ID, Config.API_HASH) as userbot:
                await userbot.send_message("me", text)
                me = await userbot.get_me()
        except Exception as e:
            await query.message.reply(f"Invalid session string.\n\nError: `{e}`")
            return

        existing_group = await db.group.find_one({"_id": me.id})
        if existing_group:
            await query.message.reply(f"This account is already added.\n\n{existing_group}")
            return

        if not user:
            user = {"_id": user_id, "accounts": []}

        user.setdefault("accounts", []).append({"session": string})
        await db.update_user(user_id, user)
        await query.message.reply("Account added successfully and validated.")

    elif data == "tier":
        user = await db.get_user(query.from_user.id)
        is_premium = user.get("is_premium", False)
        if is_premium:
            await query.answer("Tier: Premium", show_alert=True)
        else:
            await query.answer("Tier: Free", show_alert=True)
        await query.message.edit_media(
            InputMediaPhoto(
                random.choice(Config.PICS),
                Txt.HELP_TXT,
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("ᐊ ʙᴀᴄᴋ", callback_data="start"),
                InlineKeyboardButton("✘ ᴄʟᴏsᴇ", callback_data="close")
                
            ]])
        )

    elif data == "guide":
        await query.message.edit_media(
            InputMediaPhoto(
                random.choice(Config.PICS),
                Txt.GUIDE_TXT,

            ),

            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("ᐊ ʙᴀᴄᴋ", callback_data="start"),
                InlineKeyboardButton("✘ ᴄʟᴏsᴇ", callback_data="close")
                
            ]])
        )

   
    elif data.startswith("choose_delete_"):
        index = int(data.split("_")[-1])
        user_id = query.from_user.id
        user = await db.get_user(user_id)

        if not user or index >= len(user.get("accounts", [])):
            return await query.answer("Invalid selection.", show_alert=True)
        account = user["accounts"].pop(index)
        try:
            async with TelegramClient(StringSession(account["session"]), Config.API_ID, Config.API_HASH) as tg_client:
                me = await tg_client.get_me()
                await db.del_user(me.id)
        except Exception as e:
            await query.edit_message_text(f"Error {e}.")
            return

        
        await db.col.update_one({"_id": user_id}, {"$set": {"accounts": user["accounts"]}})
        await query.edit_message_text("Account and its groups have been deleted.")

    elif data == "close":
        try:
            await query.message.delete()
            await query.message.reply_to_message.delete()
            await query.message.continue_propagation()
        except:
            await query.message.delete()
            await query.message.continue_propagation()
    
    
