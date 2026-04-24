import asyncio
import requests
import os
from telegram.ext import Application, CommandHandler, ContextTypes

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADDRESS = "TDy4vHiBx9o6zwqD3TaCtSh3iioC6DUW1H"

API = f"https://api.trongrid.io/v1/accounts/{ADDRESS}/transactions?limit=10"

last_tx = None

# ================= FORMAT =================

def send_format(direction, amount, symbol, txid):
    return f"""
💸 {direction.upper()} İŞLEM

Miktar: {amount} {symbol}

💸 Rest gelsin paralar gelsin paralar

TxID:
https://tronscan.org/#/transaction/{txid}
"""

# ================= DETECT TYPE =================

def parse_tx(tx):
    """
    TRX mi USDT mi ayıklar (basit sürüm)
    """
    try:
        contract = tx["raw_data"]["contract"][0]
        ctype = contract["type"]

        # ================= TRX =================
        if ctype == "TransferContract":
            v = contract["parameter"]["value"]

            amount = v["amount"] / 1_000_000

            from_addr = v["owner_address"]
            to_addr = v["to_address"]

            if ADDRESS in to_addr:
                direction = "GELDİ"
            else:
                direction = "GİTTİ"

            return direction, amount, "TRX", tx["txID"]

        # ================= USDT (basit placeholder) =================
        if ctype == "TriggerSmartContract":
            return "TRANSFER", 0, "USDT", tx["txID"]

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
                        parsed = parse_tx(tx)

                        if not parsed:
                            continue

                        direction, amount, symbol, txid = parsed

                        msg = send_format(direction, amount, symbol, txid)

                        for chat_id in list(app.chat_data.keys()):
                            await app.bot.send_message(chat_id=chat_id, text=msg)

                    last_tx = latest

            await asyncio.sleep(6)  # ⚡ hızlı kontrol

        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(5)

# ================= POST INIT =================

async def post_init(app):
    asyncio.create_task(tron_listener(app))

# ================= COMMAND =================

async def start(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    context.application.chat_data[chat_id] = True

    await update.message.reply_text("🤖 Real-time tracker aktif")

# ================= MAIN =================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN eksik")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))

    app.run_polling()

if __name__ == "__main__":
    main()
