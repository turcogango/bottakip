import asyncio
import requests
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")

TRX_ADDRESS = "TDy4vHiBx9o6zwqD3TaCtSh3iioC6DUW1H"
API = f"https://api.trongrid.io/v1/accounts/{TRX_ADDRESS}/transactions?limit=10"

last_tx = None

# 🔥 FIX: chat listesi (mappingproxy hatası yerine)
ACTIVE_CHATS = set()

# ================= FORMAT =================

def format_msg(direction, amount, symbol, txid):
    return f"""
💸 {direction} İŞLEM

Miktar: {amount} {symbol}

💸 Rest gelsin paralar gelsin paralar

TxID:
https://tronscan.org/#/transaction/{txid}
"""

# ================= LISTENER =================

async def tron_listener(app):
    global last_tx

    await asyncio.sleep(3)

    while True:
        try:
            r = requests.get(API, timeout=10)
            txs = r.json().get("data", [])

            if txs:
                latest = txs[0]["txID"]

                if last_tx is None:
                    last_tx = latest

                elif latest != last_tx:

                    new_txs = []

                    for tx in txs:
                        if tx["txID"] == last_tx:
                            break
                        new_txs.append(tx)

                    for tx in reversed(new_txs):
                        txid = tx["txID"]

                        msg = format_msg("TX", "Bilinmiyor", "", txid)

                        for chat_id in ACTIVE_CHATS:
                            await app.bot.send_message(chat_id=chat_id, text=msg)

                    last_tx = latest

            await asyncio.sleep(6)

        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(5)

# ================= POST INIT =================

async def post_init(app):
    asyncio.create_task(tron_listener(app))

# ================= COMMAND =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # 🔥 FIX: artık chat_data yok
    ACTIVE_CHATS.add(chat_id)

    await update.message.reply_text("🤖 Bot aktif")

# ================= MAIN =================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN eksik")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
