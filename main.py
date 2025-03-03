import telebot
from binance.client import Client
import time
import websocket, threading, json, os
from dotenv import load_dotenv

load_dotenv('.env')
API_KEY = os.environ["API_KEY"]
API_SECRET = os.environ["API_SECRET"]
BOT_API_KEY = os.environ["BOT_API_KEY"]
CHAT_ID = os.environ["CHAT_ID"]

client = Client(API_KEY, API_SECRET)
bot = telebot.TeleBot(token=BOT_API_KEY)

# Dictionary to store the most recent status for each orderId
order_statuses = {}

def process_execution_report(message):
    global order_statuses
    symbol = message["s"]
    order_id = message["i"]
    current_status = message["X"]

    # Extract quantity (q) and price (p) from the event
    # These are strings in the message; convert them to float to calculate notional value.
    quantity_str = message.get("q", "0")
    price_str = message.get("p", "0")
    quantity = float(quantity_str)
    price = float(price_str)
    # Compute "order value" (notional) if it's a limit order (price != 0)
    order_value = quantity * price

    # If this is the first time we see this order
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

def on_message(ws, message):
    data = json.loads(message)
    # Check if this event is an executionReport (order update)
    if "e" in data and data["e"] == "executionReport":
        process_execution_report(data)

def on_error(ws, error):
    print(f"WebSocket помилка: {error}")

def on_close(ws):
    print("WebSocket з'єднання закрито.")

def on_open(ws):
    print("WebSocket з'єднання відкрите. Слухаємо оновлення ордерів...")

def keepalive_listen_key(listen_key, interval=30 * 60):
    while True:
        try:
            client.stream_keepalive(listen_key)
        except Exception as e:
            print(f"Помилка при подовженні listen key: {e}")
        time.sleep(interval)

def main():
    # 1) Get the listen key for the user data stream
    listen_key = client.stream_get_listen_key()

    # 2) Start a thread to keep the listen key alive
    t = threading.Thread(target=keepalive_listen_key, args=(listen_key,), daemon=True)
    t.start()

    # 3) Connect to the user data stream websocket
    ws = websocket.WebSocketApp(
        f"wss://stream.binance.com:9443/ws/{listen_key}",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    # 4) Start listening (this call blocks the main thread)
    ws.run_forever()

if __name__ == "__main__":
    main()