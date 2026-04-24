import asyncio
import requests
from telegram import Bot

# ================= CONFIG =================

BOT_TOKEN = "BOT_TOKEN"
ADMIN_ID = 123456789  # Telegram user id

ADDRESS = "TDy4vHiBx9o6zwqD3TaCtSh3iioC6DUW1H"

TRON_API = f"https://api.trongrid.io/v1/accounts/{ADDRESS}/transactions?limit=10"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

bot = Bot(token=BOT_TOKEN)

last_tx = None

# ================= LOOP =================

async def run():
    global last_tx

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

                            # GELEN
                            if ADDRESS in to_addr:
                                await bot.send_message(
                                    ADMIN_ID,
                                    f"""📥 TRX GELDİ
Miktar: {amount} TRX
💸 Rest gelsin paralar gelsin paralar

TxID: {txid}
https://tronscan.org/#/transaction/{txid}"""
                                )

                            # GİDEN
                            elif ADDRESS in from_addr:
                                await bot.send_message(
                                    ADMIN_ID,
                                    f"""📤 TRX GİTTİ
Miktar: {amount} TRX

TxID: {txid}
https://tronscan.org/#/transaction/{txid}"""
                                )

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

                                await bot.send_message(
                                    ADMIN_ID,
                                    f"""💵 USDT GELDİ
Miktar: {amount} USDT
💸 Rest gelsin paralar gelsin paralar

TxID: {txid}
https://tronscan.org/#/transaction/{txid}"""
                                )

                    last_tx = latest

            await asyncio.sleep(8)

        except Exception as e:
            print("Hata:", e)
            await asyncio.sleep(5)

# ================= START =================

if __name__ == "__main__":
    asyncio.run(run())
