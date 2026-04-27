import asyncio
import time
import requests
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADDRESS = "TDy4vHiBx9o6zwqD3TaCtSh3iioC6DUW1H"

TRC20_API = f"https://api.trongrid.io/v1/accounts/{ADDRESS}/transactions/trc20?limit=30"
TRX_API = f"https://api.trongrid.io/v1/accounts/{ADDRESS}/transactions?limit=30&only_confirmed=true"
TX_INFO_API = "https://api.trongrid.io/wallet/gettransactioninfobyid"
PRICE_API = "https://api.coingecko.com/api/v3/simple/price?ids=tron,tether&vs_currencies=try"

ACTIVE_CHATS = set()
seen_tx = set()
start_ts_ms = int(time.time() * 1000)

# fiyat cache
_price_cache = {"ts": 0, "trx": 0.0, "usdt": 0.0}

# ================= PRICE =================

def get_prices():
    now = time.time()
    if now - _price_cache["ts"] < 60 and _price_cache["trx"]:
        return _price_cache["trx"], _price_cache["usdt"]
    try:
        r = requests.get(PRICE_API, timeout=10).json()
        _price_cache["trx"] = float(r["tron"]["try"])
        _price_cache["usdt"] = float(r["tether"]["try"])
        _price_cache["ts"] = now
    except Exception as e:
        print("PRICE ERROR:", e)
    return _price_cache["trx"], _price_cache["usdt"]

def to_try(symbol, amount):
    trx_try, usdt_try = get_prices()
    if symbol == "TRX":
        return amount * trx_try
    if symbol == "USDT":
        return amount * usdt_try
    return 0.0

def fmt_try(v):
    return f"{v:,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

# ================= FEE =================

def get_fee(txid):
    try:
        r = requests.post(TX_INFO_API, json={"value": txid}, timeout=10).json()
        fee_sun = r.get("fee", 0)
        return fee_sun / 1_000_000
    except Exception as e:
        print("FEE ERROR:", e)
        return 0.0

# ================= FETCH =================

def fetch_trc20():
    """TRC20 transfer eventlerini döner: list of (txid, ts, symbol, amount, from, to)"""
    out = []
    try:
        data = requests.get(TRC20_API, timeout=10).json().get("data", [])
        for ev in data:
            try:
                info = ev.get("token_info", {})
                symbol = info.get("symbol", "?")
                decimals = int(info.get("decimals", 6))
                amount = int(ev["value"]) / (10 ** decimals)
                out.append({
                    "txid": ev["transaction_id"],
                    "ts": ev["block_timestamp"],
                    "symbol": symbol,
                    "amount": amount,
                    "from": ev["from"],
                    "to": ev["to"],
                    "kind": "trc20",
                })
            except Exception:
                continue
    except Exception as e:
        print("TRC20 ERROR:", e)
    return out

def fetch_trx():
    """Native TRX transferleri."""
    out = []
    try:
        data = requests.get(TRX_API, timeout=10).json().get("data", [])
        for tx in data:
            try:
                c = tx["raw_data"]["contract"][0]
                if c["type"] != "TransferContract":
                    continue
                v = c["parameter"]["value"]
                amount = v.get("amount", 0) / 1_000_000
                if amount <= 0:
                    continue
                out.append({
                    "txid": tx["txID"],
                    "ts": tx.get("block_timestamp", 0),
                    "symbol": "TRX",
                    "amount": amount,
                    "from": v.get("owner_address_base58") or v.get("owner_address", ""),
                    "to": v.get("to_address_base58") or v.get("to_address", ""),
                    "kind": "trx",
                })
            except Exception:
                continue
    except Exception as e:
        print("TRX ERROR:", e)
    return out

# ================= GROUP & CLASSIFY =================

def group_by_tx(events):
    groups = {}
    for e in events:
        groups.setdefault(e["txid"], []).append(e)
    return groups

def classify(txid, events):
    """Bir tx içindeki tüm transferlerden yön ve swap durumunu çıkarır."""
    incoming = {}  # symbol -> amount
    outgoing = {}
    ts = 0
    for e in events:
        ts = max(ts, e["ts"])
        sym = e["symbol"]
        if e["to"] == ADDRESS:
            incoming[sym] = incoming.get(sym, 0) + e["amount"]
        elif e["from"] == ADDRESS:
            outgoing[sym] = outgoing.get(sym, 0) + e["amount"]

    if incoming and outgoing:
        return {"type": "SWAP", "in": incoming, "out": outgoing, "ts": ts}
    if incoming:
        sym, amt = next(iter(incoming.items()))
        return {"type": "IN", "symbol": sym, "amount": amt, "ts": ts}
    if outgoing:
        sym, amt = next(iter(outgoing.items()))
        return {"type": "OUT", "symbol": sym, "amount": amt, "ts": ts}
    return None

# ================= FORMAT =================

def fmt_amount(sym, amt):
    if sym == "TRX":
        return f"{amt:,.6f}".rstrip("0").rstrip(".")
    return f"{amt:,.2f}"

def build_message(txid, info):
    fee = get_fee(txid)
    fee_try = to_try("TRX", fee)
    link = f"https://tronscan.org/#/transaction/{txid}"

    if info["type"] == "SWAP":
        lines = ["🔄 SWAP", ""]
        lines.append("Gönderilen:")
        for sym, amt in info["out"].items():
            lines.append(f"  • {fmt_amount(sym, amt)} {sym}  ({fmt_try(to_try(sym, amt))})")
        lines.append("")
        lines.append("Alınan:")
        for sym, amt in info["in"].items():
            lines.append(f"  • {fmt_amount(sym, amt)} {sym}  ({fmt_try(to_try(sym, amt))})")
        lines.append("")
        lines.append(f"⛽ Kesinti: {fee:.6f} TRX  ({fmt_try(fee_try)})")
        lines.append("")
        lines.append(f"TxID:\n{link}")
        return "\n".join(lines)

    direction = "GELDİ" if info["type"] == "IN" else "GİTTİ"
    emoji = "📥" if info["type"] == "IN" else "📤"
    sym = info["symbol"]
    amt = info["amount"]
    try_val = to_try(sym, amt)

    lines = [
        f"{emoji} {sym} {direction}",
        "",
        f"Miktar: {fmt_amount(sym, amt)} {sym}",
        f"Karşılığı: {fmt_try(try_val)}",
        "",
        f"⛽ Kesinti: {fee:.6f} TRX  ({fmt_try(fee_try)})",
        "",
        f"TxID:\n{link}",
    ]
    return "\n".join(lines)

# ================= LISTENER =================

async def tron_listener(app):
    global seen_tx

    # ilk taramada mevcut tx'leri "görüldü" işaretle, sadece yenilerini bildir
    initial = fetch_trc20() + fetch_trx()
    for e in initial:
        seen_tx.add(e["txid"])
    print(f"Başlangıç: {len(seen_tx)} mevcut tx atlandı.")

    while True:
        try:
            events = fetch_trc20() + fetch_trx()
            # sadece başlangıçtan sonraki ve görülmemiş olanlar
            new_events = [
                e for e in events
                if e["txid"] not in seen_tx and e["ts"] >= start_ts_ms
            ]

            if new_events:
                groups = group_by_tx(new_events)
                # eski → yeni sırala
                ordered = sorted(groups.items(), key=lambda kv: max(x["ts"] for x in kv[1]))

                for txid, evs in ordered:
                    info = classify(txid, evs)
                    seen_tx.add(txid)
                    if not info:
                        continue
                    msg = build_message(txid, info)
                    for chat_id in ACTIVE_CHATS:
                        try:
                            await app.bot.send_message(chat_id=chat_id, text=msg, disable_web_page_preview=True)
                        except Exception as e:
                            print("SEND ERROR:", e)

            await asyncio.sleep(5)

        except Exception as e:
            print("LOOP ERROR:", e)
            await asyncio.sleep(5)

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ACTIVE_CHATS.add(update.effective_chat.id)
    trx_try, usdt_try = get_prices()
    await update.message.reply_text(
        "🤖 Pro TRX Tracker aktif\n"
        f"Adres: {ADDRESS}\n"
        f"TRX: {fmt_try(trx_try)}  |  USDT: {fmt_try(usdt_try)}"
    )

async def fiyat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trx_try, usdt_try = get_prices()
    await update.message.reply_text(
        f"TRX: {fmt_try(trx_try)}\nUSDT: {fmt_try(usdt_try)}"
    )

# ================= MAIN =================

async def post_init(app):
    asyncio.create_task(tron_listener(app))

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN eksik")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("fiyat", fiyat))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
