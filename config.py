import re
import os
import time

id_pattern = re.compile(r'^.\d+$')


class Config(object):
    # pyro client config
    API_ID = os.environ.get("API_ID", "")  # ⚠️ Required
    API_HASH = os.environ.get("API_HASH", "")  # ⚠️ Required
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")  # ⚠️ Required

    # database config
    DB_NAME = os.environ.get("DB_NAME", "cluster0")
    DB_URL = os.environ.get("DB_URL", "")  # ⚠️ Required

    FREE_ACCOUNT = os.environ.get("FREE_ACCOUNT", "2")
    FREE_GROUP = os.environ.get("FREE_GROUP", "4")
    
    # other configs
    BOT_UPTIME = time.time()
    PICS = os.environ.get("PICS", 'https://envs.sh/s3r.jpg https://envs.sh/s33.jpg').split()
    ADMIN = [int(admin) if id_pattern.search(
        admin) else admin for admin in os.environ.get('ADMIN', '').split()]  # ⚠️ Required

    LOG_CHANNEL = os.environ.get("LOG_CHANNEL", "")
    FORCE_SUB = os.environ.get("FORCE_SUB", "") # ⚠️ Required Username without @
    FLOOD = int(os.environ.get("FLOOD", '10'))
    BANNED_USERS = set(int(x) for x in os.environ.get(
        "BANNED_USERS", "1234567890").split())

    # wes response configuration
    WEBHOOK = bool(os.environ.get("WEBHOOK", False))
    PORT = int(os.environ.get("PORT", "8080"))


class Txt(object):
    # part of text configuration
    START_TXT = """<b>Hᴇʏ {} 👋, ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ <a href=https://t.me/{}>{}</a> ᴡᴏʀʟᴅ'ꜱ ꜰɪʀꜱᴛ ꜰʀᴇᴇ ʙᴀɴ-ꜱᴩᴀᴍ ʙᴏᴛ

ʙʏ ᴜꜱɪɴɢ ᴛʜɪꜱ ʙᴏᴛ, ʏᴏᴜ ᴀɢʀᴇᴇ ᴛᴏ ᴀʟʟ ᴛᴇʀᴍꜱ ᴀɴᴅ ꜱᴇʀᴠɪᴄᴇ ᴄᴏɴᴅɪᴛɪᴏɴꜱ ᴍᴇɴᴛɪᴏɴᴇᴅ ɪɴ @VeeADTnS

ꜱᴛᴀʀᴛ ʏᴏᴜʀ ᴀᴜᴛᴏᴍᴀᴛᴇᴅ ᴛʜɪɴɢꜱ ᴜꜱɪɴɢ /add_account</b>"""


    HELP_TXT = """
<b>Tɪᴇʀ : Fʀᴇᴇ</b>
<b>• ᴀᴄᴄᴏᴜɴᴛ : 1</b> 
<b>• ɢʀᴏᴜᴩꜱ : 3</b> 
<b>• ᴄᴜꜱᴛᴏᴍ ʙɪᴏ ᴄʜᴀɴɢᴇ : ʏᴇꜱ</b> 
<b>• ᴛɪᴍᴇ ɪɴᴛᴇʀᴠᴀʟ : 2ʜʀꜱ </b> 

<b>Tɪᴇʀ : Pʀᴇᴍɪᴜᴍ</b>
<b>• ᴀᴄᴄᴏᴜɴᴛ : ᴜɴʟɪᴍɪᴛᴇᴅ</b> 
<b>• ɢʀᴏᴜᴩꜱ : ᴜɴʟɪᴍɪᴛᴇᴅ</b> 
<b>• ᴄᴜꜱᴛᴏᴍ ʙɪᴏ ᴄʜᴀɴɢᴇ : ɴᴏ</b> 
<b>• ᴛɪᴍᴇ ɪɴᴛᴇʀᴠᴀʟ : ᴄᴜꜱᴛᴏᴍ </b>
"""

    
    GUIDE_TXT = """#######TEXT GOES HERE##########"""

    
