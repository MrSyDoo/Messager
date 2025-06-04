import shutil
import time
import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from config import Config, Txt
from .start import db, temp, start_forwarding_loop, start_forwarding_process
import random
from pyromod.exceptions import ListenerTimeout
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.channels import GetForumTopicsRequest
import psutil
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import Channel, Chat
from urllib.parse import urlparse

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
             InlineKeyboardButton("Aᴅᴅ Aʟʟ Gʀᴏᴜᴘꜱ", callback_data=f"add_all_groups_{account_index}")
       ])
        buttons.append([
            InlineKeyboardButton("⇇ Gᴏ Bᴀᴄᴋ", callback_data=f"everything_{account_index}"),
            InlineKeyboardButton("↻ Rᴇꜱᴇᴛ ↻", callback_data=f"delete_all_{account_index}")
        ])
        await message.edit_text("Sᴇʟᴇᴄᴛ ʏᴏᴜʀ ɢʀᴏᴜᴩꜱ ᴛᴏ ꜰᴏʀᴡᴀʀᴅ:", reply_markup=InlineKeyboardMarkup(buttons))


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
    elif data.startswith("add_all_groups_"):
        account_index = int(data.split("_")[-1])

        user = await db.get_user(query.from_user.id)
        is_premium = user.get("is_premium", False)
        session_str = user["accounts"][account_index]["session"]

        async with TelegramClient(StringSession(session_str), Config.API_ID, Config.API_HASH) as tg_client:
            me = await tg_client.get_me()
            session_user_id = me.id
            group_data = await db.group.find_one({"_id": session_user_id}) or {"_id": session_user_id, "groups": []}
            existing_group_ids = {g["id"] for g in group_data.get("groups", [])}
            limit = user.get("group_limit", FREE_GROUP) if not is_premium else 1000

            dialogs = await tg_client.get_dialogs()
            added_count = 0

            for d in dialogs:
                if added_count + len(existing_group_ids) >= limit:
                    break

                if d.is_group or (d.is_channel and getattr(d.entity, "megagroup", False)):
                    if d.id in existing_group_ids:
                        continue  # Already added

                    new_group = {"id": d.id, "last_sent": datetime.min}
                    entity = await tg_client.get_entity(d.id)
                    if getattr(entity, "forum", False):
                        continue
                    if is_premium:
                        try:
                            input_channel = await tg_client.get_input_entity(d.entity)
                            full_chat = await tg_client(GetFullChannelRequest(input_channel))
                            slow_mode = getattr(full_chat.full_chat, "slowmode_seconds", 0)
                            new_group["interval"] = slow_mode + 5
                        except Exception as e:
                            print(f"Failed to fetch slow mode for {d.id}: {e}")  # Could not fetch slow mode

                    group_data["groups"].append(new_group)
                    added_count += 1

            await db.group.update_one({"_id": session_user_id}, {"$set": {"groups": group_data["groups"]}}, upsert=True)
            if is_premium:
                await query.answer(f"✅ {added_count} ɴᴇᴡ ɢʀᴏᴜᴘꜱ ᴀᴅᴅᴇᴅ. [ᴇxᴄʟᴜᴅᴇᴅ ɢʀᴏᴜᴩ ᴡɪᴛʜ ꜰᴏʀᴜᴍꜱ/ᴛᴏᴩɪᴄꜱ]", show_alert=True)
            else:
                await query.answer(f"✅ {added_count} ɴᴇᴡ ɢʀᴏᴜᴘꜱ ᴀᴅᴅᴇᴅ. [ᴇxᴄʟᴜᴅᴇᴅ ɢʀᴏᴜᴩ ᴡɪᴛʜ ꜰᴏʀᴜᴍꜱ/ᴛᴏᴩɪᴄꜱ] \n📜 ʟɪᴍɪᴛ ʀᴇᴀᴄʜᴇᴅ, ᴍᴀxɪᴍᴜᴍ ɢʀᴏᴜᴩ ꜰᴏʀ ᴩʀᴇᴍɪᴜᴍ ᴜꜱᴇʀꜱ ᴏɴʟʏ.", show_alert=True)
            await show_groups_for_account(client, query.message, query.from_user.id, account_index)


    elif query.data.startswith("everything_"):
        index = int(query.data.split("_")[-1])
        user = await db.get_user(query.from_user.id)
        accounts = user.get("accounts", [])
        if index >= len(accounts):
            return await query.answer("❗ Invalid account index. Click On /Settings", show_alert=True)

        buttons = [
            [InlineKeyboardButton("ꜱᴇᴛ ɢʀᴏᴜᴩ", callback_data=f"choose_account_{index}")],
            [InlineKeyboardButton("ᴊᴏɪɴ ᴀ ɢʀᴏᴜᴩ", callback_data=f"join_group_account_{index}"),
             InlineKeyboardButton("ꜱᴛᴀʀᴛ ᴅᴇʟᴀʏ", callback_data=f"set_interval_account_{index}")],
            [InlineKeyboardButton("ᴅᴇʟᴇᴛᴇ ᴀᴄᴄᴏᴜɴᴛ", callback_data=f"choose_delete_{index}")],
            [InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="get_every")]
        ]

        await query.message.edit_text(
            f"ꜱᴇᴛᴛɪɴɢꜱ ꜰᴏʀ ᴀᴄᴄᴏᴜɴᴛ {index+1}:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    elif query.data == "get_every":
        user_id = query.from_user.id
        user = await db.get_user(user_id)
        if not user:
            return await query.message.edit("❗ You are not registered.")

        accounts = user.get("accounts", [])
        if not accounts:
            keybord = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Aᴅᴅ Aᴄᴄᴏᴜɴᴛ", callback_data="add_account")]]
            )
            return await query.message.edit_text("No accounts found. 😑", reply_markup=keybord)

        keyboard = []
        for i, acc in enumerate(accounts):
            session = StringSession(acc["session"])
            async with TelegramClient(session, Config.API_ID, Config.API_HASH) as tg_client:
                try:
                    me = await tg_client.get_me()
                    name = me.first_name or me.username or str(me.id)
                    btn = InlineKeyboardButton(
                        f"{name} ({me.id})",
                        callback_data=f"choose_account_{i}"
                    )
                    keyboard.append([btn])
                except Exception:
                    keyboard.append([InlineKeyboardButton(
                        f"Account {i+1} (Invalid)",
                        callback_data=f"choose_account_{i}"
                    )])
        keyboard.append([InlineKeyboardButton('Aᴅᴅ Aᴄᴄᴏᴜɴᴛ', callback_data='add_account')])
        await query.message.edit(
            "Cʜᴏᴏꜱᴇ ᴀɴ ᴀᴄᴄᴏᴜɴᴛ ᴛᴏ ᴍᴀɴᴀɢᴇ ꜱᴇᴛᴛɪɴɢꜱ:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

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
                limit = user.get("group_limit", FREE_GROUP) if not is_premium else 1000
                if len(group_list) >= int(limit):
                    return await query.answer("Group limit reached.", show_alert=True)
                current_interval = None
                for g in group_list:
                    if g["id"] == group_id and "interval" in g:
                        current_interval = g["interval"]
                        break

                default_interval = 300 if (is_premium or can_use_interval) else 7200  # 5 min or 2 hrs
                slow_mode = 0
                try:
                    full_chat = await tg_client(GetFullChannelRequest(entity))
                    slow_mode = getattr(full_chat.full_chat, "slowmode_seconds", 0)
                except:
                    pass

                if not slow_mode:
                    slow_mode = 0
                prompt_text = (
                    "Pʟᴇᴀꜱᴇ Sᴇɴᴅ Iɴᴛᴇʀᴠᴀʟ (ɪɴ ꜱᴇᴄᴏɴᴅꜱ)[ᴩʀᴇᴍɪᴜᴍ] Oʀ Sᴇɴᴅ /add Tᴏ Aᴅᴅ Gʀᴏᴜᴩ Oɴʟʏ ᴏʀ Sᴇɴᴅ /delete Tᴏ Rᴇᴍᴏᴠᴇ Tʜɪꜱ Gʀᴏᴜᴩ.\n\nTɪᴍᴇᴏᴜᴛ ɪɴ 30 ꜱᴇᴄᴏɴᴅꜱ."
                    f"ꜱʟᴏᴡ ᴍᴏᴅᴇ ɪɴ ᴛʜɪꜱ ᴄʜᴀᴛ: {slow_mode} sec\n\n"
                    f"ᴄᴜʀʀᴇɴᴛ ɪɴᴛᴇʀᴠᴀʟ: {current_interval if current_interval is not None else default_interval} seconds\n"
                    
                )

                interval_value = None
                add_command = False
                try:
                    prompt = await query.message.reply(prompt_text)
                    response = await client.listen(
                        chat_id=query.from_user.id,
                        filters=filters.text,
                        timeout=30
                    )
                    text = response.text.strip().lower()

                    if text == "/delete":
                        group_list = [g for g in group_list if g["id"] != group_id]
                        await db.group.update_one({"_id": session_user_id}, {"$set": {"groups": group_list}})
                        await query.message.reply_text("ɢʀᴏᴜᴩ ᴅᴇʟᴇᴛᴇᴅ. ✅")
                        await prompt.delete()
                        return await show_groups_for_account(client, query.message, query.from_user.id, account_index)

                    if text == "/add":
                        add_command = True
                    else:
                        try:
                            interval = int(text)
                            if is_premium or can_use_interval:
                                if slow_mode >= interval:
                                    return await query.message.reply_text("ɪɴᴛᴇʀᴠᴀʟ ᴍᴜꜱᴛ ʙᴇ ɢʀᴇᴀᴛᴇʀ ᴛʜᴀɴ ꜱʟᴏᴡ ᴍᴏᴅᴇ")
                                interval_value = interval
                            else:
                                await prompt.delete()
                                return await query.message.reply_text("Interval only available to limited users.")
                        except ValueError:
                            await prompt.delete()
                            return await query.message.reply_text("⚠️ Invalid format. Interval should be a number or /add.")

                except ListenerTimeout:
                    await prompt.delete()
                    return await query.message.reply_text("⚠️ Error!!\n\n**Request timed out.**")

                updated = False
                for g in group_list:
                    if g["id"] == group_id:
                        if interval_value is not None:
                            g["interval"] = interval_value
                        elif add_command and not (is_premium or can_use_interval):
                            g.pop("interval", None)
                        updated = True
                        break

                if not updated:
                    new_group = {"id": group_id, "last_sent": datetime.min}
                    if interval_value is not None:
                        new_group["interval"] = interval_value
                    elif not (is_premium or can_use_interval) and add_command:
                        pass  # skip interval
                    group_list.append(new_group)

                await db.group.update_one({"_id": session_user_id}, {"$set": {"groups": group_list}}, upsert=True)
                await query.answer("Gʀᴏᴜᴩ ᴇɴᴀʙʟᴇᴅ/ᴜᴩᴅᴀᴛᴇᴅ ✅", show_alert=True)
                await prompt.delete()
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
            limit = user.get("group_limit", FREE_GROUP) if not is_premium else 1000
            if len(group_list) >= int(limit):
                return await query.answer("Group limit reached.", show_alert=True)

            # Get current interval if set for this group
            current_interval = None
            for g in group_list:
                if g["id"] == group_id and "interval" in g:
                    current_interval = g["interval"]
                    break

            # Default intervals depending on user type
            default_interval = 300 if (is_premium or can_use_interval) else 7200  # 5 min or 2 hrs

            # Try to get slow mode of the group/topic
            slow_mode = 0
            try:
                entity = await tg_client.get_entity(group_id)
                full_chat = await tg_client(GetFullChannelRequest(entity))
                slow_mode = getattr(full_chat.full_chat, "slowmode_seconds", 0)
            except:
                pass

            if not slow_mode:
                slow_mode = 0

            prompt_text = (
                "Pʟᴇᴀꜱᴇ Sᴇɴᴅ Iɴᴛᴇʀᴠᴀʟ (ɪɴ ꜱᴇᴄᴏɴᴅꜱ)[ᴩʀᴇᴍɪᴜᴍ] ᴏʀ Sᴇɴᴅ /add Tᴏ Sᴋɪᴩ (ᴏɴʟʏ ᴀᴅᴅ ᴛʜᴇ ɢʀᴏᴜᴩ) ᴏʀ /delete Tᴏ Rᴇᴍᴏᴠᴇ Tʜɪꜱ Gʀᴏᴜᴩ.\n\nTɪᴍᴇᴏᴜᴛ ɪɴ 30 ꜱᴇᴄᴏɴᴅꜱ."
               f"ꜱʟᴏᴡ ᴍᴏᴅᴇ ɪɴ ᴛʜɪꜱ ᴄʜᴀᴛ: {slow_mode} sec\n\n"
               f"ᴄᴜʀʀᴇɴᴛ ɪɴᴛᴇʀᴠᴀʟ: {current_interval if current_interval is not None else default_interval} seconds\n"
                    
            )

            interval_value = None
            add_command = False
            try:
                prompt = await query.message.reply(prompt_text)
                response = await client.listen(
                    chat_id=query.from_user.id,
                    filters=filters.text,
                    timeout=30
                )
                text = response.text.strip().lower()

                await prompt.delete()

                if text == "/delete":
                    group_list = [g for g in group_list if g["id"] != group_id]
                    await db.group.update_one({"_id": session_user_id}, {"$set": {"groups": group_list}})
                    await query.message.reply_text("✅ Group deleted.")
                    return await show_groups_for_account(client, query.message, query.from_user.id, account_index)

                if text == "/add":
                    add_command = True
                else:
                    try:
                        interval = int(text)
                        if is_premium or can_use_interval:
                            if slow_mode >= interval:
                                return await query.message.reply_text("ɪɴᴛᴇʀᴠᴀʟ ᴍᴜꜱᴛ ʙᴇ ɢʀᴇᴀᴛᴇʀ ᴛʜᴀɴ ꜱʟᴏᴡ ᴍᴏᴅᴇ")
                            interval_value = interval
                        else:
                            return await query.message.reply_text("Interval only available to limited users.")
                    except ValueError:
                        return await query.message.reply_text("⚠️ Invalid format. Interval should be a number or /add.")

            except ListenerTimeout:
                return await query.message.reply_text("⚠️ Error!!\n\n**Request timed out.**")

            updated = False
            for g in group_list:
                if g["id"] == group_id:
                    g["topic_id"] = topic_id
                    if interval_value is not None:
                        g["interval"] = interval_value
                    elif add_command and not (is_premium or can_use_interval):
                        g.pop("interval", None)
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
        await show_groups_for_account(client, query.message, query.from_user.id, account_index)

    elif query.data.startswith("join_group_account_"):
        user_id = query.from_user.id
        user = await db.get_user(user_id)
        if not user:
            return await query.answer("❗ ᴜꜱᴇʀ ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)

        index = int(query.data.split("_")[-1])
        accounts = user.get("accounts", [])
        if index >= len(accounts):
            return await query.answer("❗ ɪɴᴠᴀʟɪᴅ ᴀᴄᴄᴏᴜɴᴛ ꜱᴇʟᴇᴄᴛᴇᴅ.", show_alert=True)

        prompt = await query.message.reply(
            "🔗 ꜱᴇɴᴅ ᴛʜᴇ **ɢʀᴏᴜᴘ** ʟɪɴᴋ(ꜱ) ʏᴏᴜ ᴡᴀɴᴛ ᴛʜɪꜱ ᴀᴄᴄᴏᴜɴᴛ ᴛᴏ ᴊᴏɪɴ.\n\nʏᴏᴜ ᴄᴀɴ ꜱᴇɴᴅ **ᴍᴜʟᴛɪᴘʟᴇ ʟɪɴᴋꜱ** ꜱᴇᴘᴀʀᴀᴛᴇᴅ ʙʏ ꜱᴘᴀᴄᴇ ᴏʀ ɴᴇᴡ ʟɪɴᴇꜱ.\nᴏɴʟʏ ɢʀᴏᴜᴘꜱ ᴀʀᴇ ꜱᴜᴘᴘᴏʀᴛᴇᴅ.\n\nᴏʀ ꜱᴇɴᴅ /cancel ᴛᴏ ᴀʙᴏʀᴛ.",
            parse_mode=enums.ParseMode.MARKDOWN
        )

        try:
            response = await client.listen(
                chat_id=user_id,
                filters=filters.text,
                timeout=60
            )
            text = response.text.strip()

            if text.lower() == "/cancel":
                await prompt.delete()
                return await query.message.reply("❌ ᴄᴀɴᴄᴇʟʟᴇᴅ.")

            links = [l.strip() for l in text.split() if l.strip()]

            session = StringSession(accounts[index]["session"])
            async with TelegramClient(session, Config.API_ID, Config.API_HASH) as userbot:
                results = []

                for link in links:
                    try:
                        parsed = urlparse(link)
                        path = parsed.path.strip("/")

                        if path.startswith("joinchat/"):
                            invite_hash = path.split("joinchat/")[-1]
                            updates = await userbot(ImportChatInviteRequest(invite_hash))
                            entity = updates.chats[0]
                        elif path.startswith("+"):
                            invite_hash = path[1:]
                            updates = await userbot(ImportChatInviteRequest(invite_hash))
                            entity = updates.chats[0]
                        else:
                            entity = await userbot.get_entity(link)
                            await userbot(JoinChannelRequest(entity))

                        if isinstance(entity, Channel) and entity.megagroup:
                            results.append(f"✅ ᴊᴏɪɴᴇᴅ: `{link}`")
                        elif isinstance(entity, Chat):
                            results.append(f"✅ ᴊᴏɪɴᴇᴅ: `{link}`")
                        else:
                            results.append(f"⚠️ ɴᴏᴛ ᴀ ɢʀᴏᴜᴘ: `{link}`")

                    except Exception as e:
                        results.append(f"❌ ꜰᴀɪʟᴇᴅ: `{link}`\n`{e}`")

                await prompt.delete()
                await query.message.reply(
                    "\n\n".join(results),
                    parse_mode=enums.ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )

        except ListenerTimeout:
            await prompt.delete()
            await query.message.reply("⏱️ ᴛɪᴍᴇᴏᴜᴛ. ᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴀɢᴀɪɴ.")


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
           # await query.message.delete()
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

    elif data == "normal":
        user = await db.get_user(user_id)
        await query.answer()
        await query.message.delete()
        await start_forwarding_process(client, user_id, user)

    elif data == "forward":
        user = await db.get_user(user_id)
        await query.answer()
        await query.message.delete()
        try:
            await query.message.reply_text("Send the message you want to save.\n\n**With Tag. Timeout in 5min**")
            user_msg = await client.listen(user_id, timeout=300)
            try:
                msg = await user_msg.forward(chat_id=Config.MES_CHANNEL)
            except PeerIdInvalid:
                error_text = "❌ Unable to forward message. `MES_CHANNEL` is invalid or bot is not a member."
                await client.send_message(user_id, error_text)

                for admin_id in Config.ADMIN:
                    await client.send_message(
                        admin_id,
                        f"⚠️ PeerIdInvalid error for user `{user_id}` while trying to forward to `{Config.MES_CHANNEL}`.\n"
                        f"Make sure the bot is added and has permission in the channel."
                    )
                return
            await db.update_user(user_id, {"forward_message_id": msg.id})
            await user_msg.delete()
            await client.send_message(user_id, "Message saved with tag. Starting forwarding...")
            await start_forwarding_process(client, user_id, user)
        except asyncio.exceptions.TimeoutError:
            await client.send_message(user_id, "❌ Timed out. Please start again using /run.")
        except Exception as e:
            await client.send_message(user_id, f"❌ Unexpected error occurred:\n`{str(e)}`")
            for admin_id in Config.ADMIN:
                await client.send_message(
                    admin_id,
                    f"🚨 Unexpected error for user `{user_id}`:\n`{str(e)}`"
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

    elif query.data.startswith("set_interval_account_"):
        user_id = query.from_user.id
        user = await db.get_user(user_id)
        if not user:
            return await query.answer("Uꜱᴇʀ ɴᴏᴛ ꜰᴏᴜɴᴅ...!", show_alert=True)

        index = int(query.data.split("_")[-1])
        if index == 0:
            return await query.answer("ɪɴᴛᴇʀᴠᴀʟ ɪꜱ ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ ꜰᴏʀ ꜰɪʀꜱᴛ ᴀᴄᴄᴏᴜɴᴛ.", show_alert=True)

        accounts = user.get("accounts", [])
        if index >= len(accounts):
            return await query.answer("ɪɴᴠᴀʟɪᴅ ᴀᴄᴄᴏᴜɴᴛ ꜱᴇʟᴇᴄᴛᴇᴅ...!", show_alert=True)

        session = StringSession(accounts[index]["session"])
        async with TelegramClient(session, Config.API_ID, Config.API_HASH) as userbot:
            me = await userbot.get_me()
            group_data = await db.group.find_one({"_id": me.id}) or {}
            default_interval = group_data.get("interval")
            current = f"`{default_interval}` seconds" if default_interval else "not set"

        prompt = await query.message.reply(
            f"🕒 Send a default interval in seconds for this account.\n\nCurrent: {current}\n\nOr send /cancel to skip."
        )

        try:
            response = await client.listen(
                chat_id=query.from_user.id,
                filters=filters.text,
                timeout=30
            )
            text = response.text.strip()

            if text.lower() == "/cancel":
                await prompt.delete()
                return await query.message.reply("❌ Cancelled.")

            interval = int(text)
            if 59 >= interval:
                return await query.message.reply_text("ɪɴᴛᴇʀᴠᴀʟ ᴍᴜꜱᴛ ʙᴇ ɢʀᴇᴀᴛᴇʀ ᴛʜᴀɴ 60ꜱ")
                               
            # Save only to db.group using account ID
            session = StringSession(accounts[index]["session"])
            async with TelegramClient(session, Config.API_ID, Config.API_HASH) as userbot:
                me = await userbot.get_me()
                await db.group.update_one(
                    {"_id": me.id},
                    {"$set": {"interval": interval}},
                    upsert=True
                )

            await prompt.delete()
            await query.message.reply(f"✅ Interval updated to `{interval}` seconds.")

        except ListenerTimeout:
            await prompt.delete()
            await query.message.reply("⏱️ Timeout! Try again.")
        except ValueError:
            await prompt.delete()
            await query.message.reply("⚠️ Invalid input. Please enter a number.")


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
    
    
