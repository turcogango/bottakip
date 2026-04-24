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

# ================= TRON LISTENER =================

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

                    for tx in txs:
                        if tx["txID"] == last_tx:
                            break

                        txid = tx["txID"]

                        for chat_id in list(app.chat_data.keys()):
                            await app.bot.send_message(
                                chat_id=chat_id,
                                text=f"""📡 YENİ İŞLEM
https://tronscan.org/#/transaction/{txid}"""
                            )

                    last_tx = latest

            await asyncio.sleep(8)

        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(5)

# ================= POST INIT (FIX HERE) =================

async def post_init(app):
    # 🔥 FIX: warning giderildi
    asyncio.create_task(tron_listener(app))

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # grup kaydı
    context.application.chat_data[chat_id] = True

    await update.message.reply_text("🤖 Bot aktif")

# ================= MAIN =================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN eksik (Railway Variables kontrol et)")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))

    app.run_polling()

if __name__ == "__main__":
    main()
