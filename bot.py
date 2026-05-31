import os
import asyncio
import aiohttp
from datetime import datetime

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SYMBOLS = ["DOGEUSDT", "BTCUSDT", "ETHUSDT"]

async def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"})

async def get_candles(symbol):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": "5m", "limit": 20}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            candles = []
            for c in data:
                candles.append({
                    "time": datetime.fromtimestamp(c[0]/1000).strftime("%H:%M"),
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5])
                })
            return candles

async def analyze(symbol, candles):
    current = candles[-1]["close"]
    candle_text = "\n".join([f"{c['time']} O:{c['open']} H:{c['high']} L:{c['low']} C:{c['close']}" for c in candles])
    
    prompt = f"""Ты опытный скальп трейдер. Анализируй {symbol}.

Свечи 5м:
{candle_text}

Цена: {current}

Дай анализ:
1. BIAS: ЛОНГ/ШОРТ/НЕЙТРАЛЬНО
2. Поддержка и сопротивление
3. Вход, стоп, тейк
4. Что делать сейчас

Коротко и чётко."""

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    body = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}]
    }
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.anthropic.com/v1/messages", headers=headers, json=body) as resp:
            data = await resp.json()
            return data["content"][0]["text"]

async def process_update(update):
    message = update.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    
    if not text or not chat_id:
        return
    
    if text == "/start":
        await send_telegram("👋 Привет! Я торговый бот.\n\n/analyze — анализ рынка\n/auto — каждые 5 минут\n/stop — остановить")
    
    elif text == "/analyze":
        await send_telegram("🔍 Анализирую...")
        for symbol in SYMBOLS:
            candles = await get_candles(symbol)
            analysis = await analyze(symbol, candles)
            current = candles[-1]["close"]
            time_now = datetime.now().strftime("%H:%M")
            await send_telegram(f"📊 *{symbol}* | {time_now}\n💰 {current}\n\n{analysis}")
            await asyncio.sleep(2)

auto_running = False

async def auto_loop():
    global auto_running
    while auto_running:
        for symbol in SYMBOLS:
            if not auto_running:
                break
            candles = await get_candles(symbol)
            analysis = await analyze(symbol, candles)
            current = candles[-1]["close"]
            time_now = datetime.now().strftime("%H:%M")
            await send_telegram(f"📊 *{symbol}* | {time_now}\n💰 {current}\n\n{analysis}")
            await asyncio.sleep(2)
        await asyncio.sleep(300)

async def main():
    global auto_running
    offset = 0
    print("Бот запущен!")
    await send_telegram("🤖 Бот запущен и готов к работе!")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={"offset": offset, "timeout": 30}) as resp:
                    data = await resp.json()
                    updates = data.get("result", [])
                    
                    for update in updates:
                        offset = update["update_id"] + 1
                        message = update.get("message", {})
                        text = message.get("text", "")
                        
                        if text == "/auto" and not auto_running:
                            auto_running = True
                            await send_telegram("✅ Автоанализ запущен! Каждые 5 минут.")
                            asyncio.create_task(auto_loop())
                        elif text == "/stop":
                            auto_running = False
                            await send_telegram("⛔ Автоанализ остановлен.")
                        else:
                            await process_update(update)
        except Exception as e:
            print(f"Ошибка: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
