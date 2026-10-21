import json, os, time, random
# ADD YOUR DETAILS HERE
BOT_TOKEN = "8893273268:AAEMjiQa6_De7az_EUeGYFu3jsyjH9ttgGs"
ADMIN_ID = 8886499198  # ADD YOUR TELEGRAM ID from @userinfobot
CHANNEL_1 = "@mini_earing_bot"
CHANNEL_2 = "@earn_mini_pay"
ADMIN_WALLET = "0x52824938de138886fdf6f7a80262e5c0a173d92c"
ADSGRAM_ID = "55283"

DB_FILE = "/tmp/db.json" # Netlify එකේ /tmp එකේ තමයි write කරන්න පුළුවන්

def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "tasks": [], "withdraws": [], "task_payments": []}
    with open(DB_FILE, "r") as f:
        try: return json.load(f)
        except: return {"users": {}, "tasks": [], "withdraws": [], "task_payments": []}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f)

def get_user(db, uid):
    uid=str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"balance":0.0, "referrals":0, "referred_by":None, "ads_today":0, "last_day":"", "wallet":"", "completed":[]}
    return db["users"][uid]

# Netlify Function Handler
def handler(event, context):
    import telegram
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
    import asyncio
    
    async def main():
        bot = telegram.Bot(token=BOT_TOKEN)
        data = json.loads(event.get('body','{}'))
        update = Update.de_json(data, bot)
        if not update.message and not update.callback_query:
            return {"statusCode":200, "body":"ok"}
        
        db = load_db()
        uid = str(update.effective_user.id) if update.effective_user else "0"
        user = get_user(db, uid)

        # Check join
        async def is_joined(uid_int):
            try:
                m1 = await bot.get_chat_member(CHANNEL_1, uid_int)
                m2 = await bot.get_chat_member(CHANNEL_2, uid_int)
                return m1.status in ["member","administrator","creator"] and m2.status in ["member","administrator","creator"]
            except: return False

        if update.message and update.message.text == "/start":
            ref = update.message.text.split(" ")[1] if len(update.message.text.split(" "))>1 else None
            # For deep linking referral: /start <ref_id>
            # We get ref from update.message.text? Actually start payload is in update.message.text
            # Simplified: check args via Telegram
            start_param = None
            if hasattr(update.message, 'text') and ' ' in update.message.text:
                start_param = update.message.text.split(' ')[1]
                if start_param != uid and start_param in db["users"] and user["referred_by"] is None:
                    user["referred_by"] = start_param
                    db["users"][start_param]["referrals"] += 1
                    db["users"][start_param]["balance"] += 0.02 # $0.02 per referral

            if not await is_joined(update.effective_user.id):
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Join Channel 1", url=f"https://t.me/{CHANNEL_1.replace('@','')}")],
                    [InlineKeyboardButton("Join Channel 2", url=f"https://t.me/{CHANNEL_2.replace('@','')}")],
                    [InlineKeyboardButton("✅ I Joined", callback_data="check_join")]
                ])
                await bot.send_message(uid, "🔒 Join 2 channels to unlock full access.", reply_markup=kb)
            else:
                main_kb = ReplyKeyboardMarkup([["💰 Watch Ads & Earn","📋 Tasks"],["👥 Referral","👤 Profile"]], resize_keyboard=True)
                await bot.send_message(uid, f"👋 Welcome!\nBalance: ${user['balance']:.2f}\nReferrals: {user['referrals']}\n\nEarn $0.05/ad (30/day)", reply_markup=main_kb)
        
        # Handle web_app_data from Mini App
        if update.message and update.message.web_app_data:
            payload = json.loads(update.message.web_app_data.data)
            if payload.get("action") == "ad_watched":
                today = time.strftime("%Y-%m-%d")
                if user["last_day"] != today:
                    user["ads_today"] = 0
                    user["last_day"] = today
                if user["ads_today"] < 30:
                    user["ads_today"] += 1
                    user["balance"] += 0.05
                    await bot.send_message(uid, f"✅ Ad watched! +$0.05 | Balance: ${user['balance']:.2f} ({user['ads_today']}/30)")
            
            elif payload.get("action") == "add_task":
                pid = len(db["task_payments"])+1
                db["task_payments"].append({
                    "id":pid, "user_id":uid, "title":payload["title"], "link":payload["link"],
                    "members_needed":payload["members"], "txid":payload["txid"], "cost":payload["cost"], "status":"pending"
                })
                # Send to Admin Inbox
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve", callback_data=f"taskpay_approve_{pid}"), InlineKeyboardButton("❌ Reject", callback_data=f"taskpay_reject_{pid}")]])
                await bot.send_message(ADMIN_ID, f"🆕 NEW TASK PAYMENT\nUser: {uid}\nTitle: {payload['title']}\nLink: {payload['link']}\nMembers: {payload['members']}\nCost: ${payload['cost']}\nTxID: {payload['txid']}\nWallet: {ADMIN_WALLET}", reply_markup=kb)
                await bot.send_message(uid, "📤 Sent to Admin for approval. Wait 24h.")

            elif payload.get("action") == "withdraw":
                amt = float(payload.get("amount",0))
                if user["balance"] < 1 or user["referrals"] < 5:
                    await bot.send_message(uid, f"❌ Need Min $1 + 5 referrals. You have ${user['balance']:.2f} + {user['referrals']} refs")
                elif amt < 1:
                    await bot.send_message(uid, "❌ Min withdraw $1")
                elif amt > user["balance"]:
                    await bot.send_message(uid, "❌ Insufficient balance")
                else:
                    wid = len(db["withdraws"])+1
                    db["withdraws"].append({"id":wid, "user_id":uid, "amount":amt, "wallet":payload["wallet"], "status":"pending"})
                    user["balance"] -= amt
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Accept", callback_data=f"withdraw_approve_{wid}"), InlineKeyboardButton("❌ Reject", callback_data=f"withdraw_reject_{wid}")]])
                    await bot.send_message(ADMIN_ID, f"💸 WITHDRAW REQUEST\nID: {wid}\nUser: {uid}\nAmount: ${amt}\nReferrals: {user['referrals']}\nWallet (BEP20): {payload['wallet']}", reply_markup=kb)
                    await bot.send_message(uid, f"📤 Withdraw ${amt} requested. Waiting admin approval.")

            elif payload.get("action") == "admin_free_task":
                if int(uid) == ADMIN_ID:
                    db["tasks"].append({"id":len(db["tasks"])+1, "title":payload["title"], "link":payload["link"], "reward":0.01, "creator":"admin"})
                    await bot.send_message(uid, f"✅ Admin Free Task Added: {payload['title']}")

        if update.callback_query:
            cq = update.callback_query
            if cq.data == "check_join":
                if await is_joined(cq.from_user.id):
                    main_kb = ReplyKeyboardMarkup([["💰 Watch Ads & Earn","📋 Tasks"],["👥 Referral","👤 Profile"]], resize_keyboard=True)
                    await bot.send_message(uid, "✅ Joined! Full access unlocked.", reply_markup=main_kb)
                else:
                    await bot.send_message(uid, "❌ Still not joined both channels.")
            
            if cq.data.startswith("withdraw_") and cq.from_user.id == ADMIN_ID:
                action, wid = cq.data.split("_")[1], cq.data.split("_")[2]
                for w in db["withdraws"]:
                    if str(w["id"]) == wid:
                        if action == "approve":
                            w["status"]="approved"
                            await bot.send_message(int(w["user_id"]), f"✅ Withdraw ${w['amount']} Approved & Sent!")
                        else:
                            w["status"]="rejected"
                            db["users"][w["user_id"]]["balance"] += w["amount"]
                            await bot.send_message(int(w["user_id"]), f"❌ Withdraw ${w['amount']} Rejected.")
                await cq.edit_message_text(f"Withdraw {wid} {action}d")

            if cq.data.startswith("taskpay_") and cq.from_user.id == ADMIN_ID:
                action, pid = cq.data.split("_")[1], cq.data.split("_")[2]
                for p in db["task_payments"]:
                    if str(p["id"]) == pid:
                        if action == "approve":
                            p["status"]="approved"
                            db["tasks"].append({"id":len(db["tasks"])+1, "title":p["title"], "link":p["link"], "reward":0.01, "creator":p["user_id"], "members_needed":p["members_needed"]})
                            await bot.send_message(int(p["user_id"]), f"✅ Task '{p['title']}' Approved!")
                        else:
                            p["status"]="rejected"
                            await bot.send_message(int(p["user_id"]), f"❌ Task payment rejected.")
                await cq.edit_message_text(f"Task {pid} {action}d")

        save_db(db)
        return {"statusCode":200, "body":"ok"}

    asyncio.run(main())
    return {"statusCode":200, "body":"ok"}
