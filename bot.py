import os
import asyncio
import aiohttp
from datetime import datetime
from telegram import Bot
from telegram.ext import Application, CommandHandler

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SYMBOLS = ["DOGEUSDT", "BTCUSDT", "ETHUSDT"]

auto_task = None

async def get_candles(symbol: str, interval: str = "5m", limit: int = 50):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
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

async def analyze_with_claude(symbol: str, candles: list):
    recent = candles[-20:]
    current_price = recent[-1]["close"]
    
    candle_text = ""
    for c in recent:
        candle_text += f"{c['time']} O:{c['open']} H:{c['high']} L:{c['low']} C:{c['close']} V:{c['volume']:.0f}\n"
    
    prompt = f"""Ты опытный скальп трейдер. Анализируй {symbol} фьючерсы.

Последние 20 свечей (5 минут):
{candle_text}

Текущая цена: {current_price}

Дай краткий анализ:
1. BIAS: ЛОНГ или ШОРТ или НЕЙТРАЛЬНО
2. Ключевые уровни поддержки и сопротивления
3. Точка входа
4. Стоп-лосс
5. Тейк-профит
6. Что делать прямо сейчас

Отвечай коротко и чётко."""

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
        async with session.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body
        ) as resp:
            data = await resp.json()
            return data["content"][0]["text"]

async def send_analysis(symbol: str):
    try:
        candles = await get_candles(symbol)
        analysis = await analyze_with_claude(symbol, candles)
        current_price = candles[-1]["close"]
        time_now = datetime.now().strftime("%H:%M")
        message = f"📊 *{symbol}* | {time_now}\n💰 Цена: {current_price}\n\n{analysis}\n\n---"
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        print(f"Ошибка {symbol}: {e}")

async def analyze_command(update, context):
    await update.message.reply_text("🔍 Анализирую рынок...")
    for symbol in SYMBOLS:
        await send_analysis(symbol)
        await asyncio.sleep(2)

async def start_command(update, context):
    await update.message.reply_text(
        "👋 Привет! Я торговый бот.\n\n"
        "Команды:\n"
        "/analyze — анализ прямо сейчас\n"
        "/auto — автоанализ каждые 5 минут\n"
        "/stop — остановить автоанализ"
    )

async def auto_command(update, context):
    global auto_task
    await update.message.reply_text("✅ Автоанализ запущен! Каждые 5 минут.")
    async def loop():
        while True:
            for symbol in SYMBOLS:
                await send_analysis(symbol)
                await asyncio.sleep(2)
            await asyncio.sleep(300)
    auto_task = asyncio.create_task(loop())

async def stop_command(update, context):
    global auto_task
    if auto_task:
        auto_task.cancel()
        auto_task = None
    await update.message.reply_text("⛔ Автоанализ остановлен.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("analyze", analyze_command))
    app.add_handler(CommandHandler("auto", auto_command))
    app.add_handler(CommandHandler("stop", stop_command))
    print("Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
