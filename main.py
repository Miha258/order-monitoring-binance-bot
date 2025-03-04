import os
import time
import json
import threading
import websocket
from dotenv import load_dotenv
from binance.client import Client
import telebot

load_dotenv('.env')

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
BOT_API_KEY = os.getenv("BOT_API_KEY")
PAIR = os.getenv("PAIR")
CHAT_ID = os.getenv("CHAT_ID")

client = Client(API_KEY, API_SECRET)
bot = telebot.TeleBot(token=BOT_API_KEY)


order_statuses = {}
last_price = {}
def process_execution_report(message):
    global order_statuses
    symbol = message["s"]
    order_id = message["i"]
    current_status = message["X"]
    quantity_str = message.get("q", "0")
    price_str = message.get("p", "0")
    quantity = float(quantity_str)
    price = float(price_str)
    order_value = quantity * price

    if order_id not in order_statuses:
        order_statuses[order_id] = current_status
        bot.send_message(
            CHAT_ID,
            f"[НОВИЙ ОРДЕР]\n"
            f"ID: {order_id}\n"
            f"Symbol: {symbol}\n"
            f"Статус: {current_status}\n"
            f"Qty: {quantity_str}\n"
            f"Price: {price_str}\n"
            f"Value: {order_value}"
        )
    else:
        previous_status = order_statuses[order_id]
        if previous_status != current_status:
            order_statuses[order_id] = current_status
            bot.send_message(
                CHAT_ID,
                f"[ЗМІНА СТАТУСУ]\n"
                f"Ордер: {order_id}, {symbol}\n"
                f"{previous_status} -> {current_status}\n"
                f"Qty: {quantity_str}\n"
                f"Price: {price_str}\n"
                f"Value: {order_value}"
            )

def on_message_user_data(ws, message):
    data = json.loads(message)
    # Якщо в події міститься "executionReport", це оновлення ордера
    if "e" in data and data["e"] == "executionReport":
        process_execution_report(data)

def on_error_user_data(ws, error):
    print(f"[UserDataStream] Помилка WebSocket: {error}")

def on_close_user_data(ws):
    print("[UserDataStream] З'єднання закрито.")

def on_open_user_data(ws):
    print("[UserDataStream] З'єднання відкрите. Слухаємо ордери...")

def keepalive_listen_key(listen_key, interval=30 * 60):
    while True:
        try:
            client.stream_keepalive(listen_key)
        except Exception as e:
            print(f"Помилка при подовженні listen key: {e}")
        time.sleep(interval)

def monitor_user_data_stream():
    listen_key = client.stream_get_listen_key()
    t = threading.Thread(target=keepalive_listen_key, args=(listen_key,), daemon=True)
    t.start()

    ws_user = websocket.WebSocketApp(
        f"wss://stream.binance.com:9443/ws/{listen_key}",
        on_open=on_open_user_data,
        on_message=on_message_user_data,
        on_error=on_error_user_data,
        on_close=on_close_user_data
    )
    ws_user.run_forever()

def on_message_ticker(ws, message):
    global last_price

    data = json.loads(message)
    symbol = data.get("s")
    current_price_str = data.get("c", "0")
    current_price = float(current_price_str)
    if symbol not in last_price:
        last_price[symbol] = current_price
        return

    previous_price = last_price[symbol]
    price_change_pct = abs((current_price - previous_price) / previous_price)
    print(price_change_pct, previous_price)
    if price_change_pct >= 0.02:
        bot.send_message(
            CHAT_ID,
            f"⚠️ Ціна {symbol} змінилася на {price_change_pct*100:.2f}%\n"
            f"Стара ціна: {previous_price}\n"
            f"Нова ціна: {current_price}"
        )
        last_price[symbol] = current_price

def on_error_ticker(ws, error):
    print(f"[TickerStream] Помилка WebSocket: {error}")

def on_close_ticker(ws):
    print("[TickerStream] З'єднання тикера закрито.")

def on_open_ticker(ws):
    print("[TickerStream] З'єднання тикера відкрите. Слухаємо зміну ціни...")

def monitor_symbol_price(symbol="BTCUSDT"):
    stream_url = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@ticker"
    ws_ticker = websocket.WebSocketApp(
        stream_url,
        on_open=on_open_ticker,
        on_message=on_message_ticker,
        on_error=on_error_ticker,
        on_close=on_close_ticker
    )
    ws_ticker.run_forever()

def main():
    t_orders = threading.Thread(target=monitor_user_data_stream, daemon=True)
    t_orders.start()
    t_price = threading.Thread(target=monitor_symbol_price, args=(PAIR,), daemon=True)
    t_price.start()

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
