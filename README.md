📄 README (short version for submission)
Binance Futures Testnet Trading Bot

This project is a simplified trading bot built for the Binance Futures Testnet.
It demonstrates how to place market and limit orders programmatically using Binance’s API.

✅ Features

Connects to Binance Futures Testnet (https://testnet.binancefuture.com)

Supports:

Market orders (immediate execution)

Limit orders (placed on order book)

TWAP orders (time-weighted average price, optional strategy)

Accepts command-line arguments for flexibility (symbol, side, type, quantity, price, etc.)

Logs requests, responses, and errors for debugging and transparency

Includes a dry-run mode (no actual orders sent, for safe testing)

⚙️ Requirements

Python 3.8+

Dependencies: requests

Install requirements:

pip install requests

🚀 Usage

Run a market buy order (0.001 BTC):

python basic_bot.py --api-key YOUR_API_KEY --api-secret YOUR_API_SECRET \
  --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001


Run a limit sell order (0.001 BTC at $30,000):

python basic_bot.py --api-key YOUR_API_KEY --api-secret YOUR_API_SECRET \
  --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 30000


Dry-run (simulate without sending to Binance):

python basic_bot.py --dry-run --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001


TWAP order (split 0.01 BTC into 5 slices over 60 seconds):

python basic_bot.py --api-key ... --api-secret ... \
  --symbol BTCUSDT --side BUY --type TWAP --quantity 0.01 \
  --twap-duration 60 --twap-slices 5

📂 Logs

Two log files are created automatically:

bot.log — overall activity, INFO & DEBUG messages, errors

bot_requests.log — details of API requests & responses (no secrets stored)

📌 Notes

Uses Binance Futures Testnet, so trades are fake and risk-free.

API key/secret must be generated from Binance Futures Testnet
.

Optional enhancements: Stop-Limit, OCO, or UI can be added.