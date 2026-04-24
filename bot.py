import os
import asyncio
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")

TRX_ADDRESS = os.getenv("TRX_ADDRESS", "TDy4vHiBx9o6zwqD3TaCtSh3iioC6DUW1H")

TRON_API = f"https://api.trongrid.io/v1/accounts/{TRX_ADDRESS}/transactions?limit=10"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

last_tx = None

# ================= TRX MONITOR =================

async def tron_listener(app):
    global last_tx

    await asyncio.sleep(5)

    while True:
        try:
            r = requests.get(TRON_API, timeout=10)
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
                        raw = tx["raw_data"]["contract"][0]
                        ctype = raw["type"]

                        # ================= TRX =================
                        if ctype == "TransferContract":
                            v = raw["parameter"]["value"]

                            amount = v["amount"] / 1_000_000
                            to_addr = v["to_address"]
                            from_addr = v["owner_address"]

                            chat_msg = None

                            if TRX_ADDRESS in to_addr:
                                chat_msg = f"""📥 TRX GELDİ
Miktar: {amount} TRX
💸 Rest gelsin paralar gelsin paralar

TxID:
https://tronscan.org/#/transaction/{txid}"""

                            elif TRX_ADDRESS in from_addr:
                                chat_msg = f"""📤 TRX GİTTİ
Miktar: {amount} TRX

TxID:
https://tronscan.org/#/transaction/{txid}"""

                            if chat_msg:
                                # tüm aktif chatlere gönder
                                for chat_id in list(app.chat_data.keys()):
                                    await app.bot.send_message(chat_id=chat_id, text=chat_msg)

                        # ================= USDT =================
                        elif ctype == "TriggerSmartContract":
                            v = raw["parameter"]["value"]
                            contract = v.get("contract_address")

                            if contract == USDT_CONTRACT:
                                data = v.get("data", "")

                                try:
                                    amount = int(data[-64:], 16) / 1_000_000
                                except:
                                    amount = 0

                                msg = f"""💵 USDT GELDİ
Miktar: {amount} USDT
💸 Rest gelsin paralar gelsin paralar

TxID:
https://tronscan.org/#/transaction/{txid}"""

                                for chat_id in list(app.chat_data.keys()):
                                    await app.bot.send_message(chat_id=chat_id, text=msg)

                    last_tx = latest

            await asyncio.sleep(8)

        except Exception as e:
            print("TRON ERROR:", e)
            await asyncio.sleep(5)

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # chat kaydet (grubu otomatik öğrenmek için)
    context.application.chat_data[chat_id] = True

    await update.message.reply_text(
        "🤖 Bot aktif\n📡 TRX + USDT takip başladı"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - botu aktif eder\n"
        "/help - yardım"
    )

# ================= INIT =================

async def post_init(app):
    app.create_task(tron_listener(app))

# ================= MAIN =================

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    app.run_polling()

if __name__ == "__main__":
    main()
