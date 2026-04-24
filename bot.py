import asyncio
import requests
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADDRESS = "TDy4vHiBx9o6zwqD3TaCtSh3iioC6DUW1H"

API = f"https://api.trongrid.io/v1/accounts/{ADDRESS}/transactions?limit=20"

last_tx = None
ACTIVE_CHATS = set()

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

# ================= FORMAT =================

def format_msg(direction, amount, symbol, txid):
    return f"""
💸 {symbol} {direction}

Miktar: {amount}

💸 Rest gelsin paralar gelsin paralar

TxID:
https://tronscan.org/#/transaction/{txid}
"""

# ================= PARSE TRX =================

def parse_trx(tx):
    try:
        c = tx["raw_data"]["contract"][0]
        v = c["parameter"]["value"]

        from_addr = v.get("owner_address", "")
        to_addr = v.get("to_address", "")
        amount = v.get("amount", 0) / 1_000_000

        direction = "GELDİ" if ADDRESS in to_addr else "GİTTİ"

        return direction, round(amount, 6), "TRX", tx["txID"]
    except:
        return None

# ================= PARSE USDT =================

def parse_usdt(tx):
    try:
        c = tx["raw_data"]["contract"][0]

        if c["type"] != "TriggerSmartContract":
            return None

        contract = c["parameter"]["value"].get("contract_address")

        if contract != USDT_CONTRACT:
            return None

        data = c["parameter"]["value"].get("data", "")

        # basit decode (transfer amount)
        if data:
            amount_hex = data[-64:]
            amount = int(amount_hex, 16) / 1_000_000

            return "GELDİ", round(amount, 2), "USDT", tx["txID"]

    except:
        pass

    return None

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

                        result = parse_trx(tx) or parse_usdt(tx)

                        if not result:
                            continue

                        direction, amount, symbol, txid = result

                        msg = format_msg(direction, amount, symbol, txid)

                        for chat_id in ACTIVE_CHATS:
                            await app.bot.send_message(chat_id=chat_id, text=msg)

                    last_tx = latest

            await asyncio.sleep(5)

        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(5)

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ACTIVE_CHATS.add(chat_id)

    await update.message.reply_text("🤖 Pro TRX Tracker aktif")

# ================= POST INIT =================

async def post_init(app):
    asyncio.create_task(tron_listener(app))

# ================= MAIN =================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN eksik")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
