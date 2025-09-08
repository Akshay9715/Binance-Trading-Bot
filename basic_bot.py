#!/usr/bin/env python3
"""
basic_bot.py

Simplified Binance Futures (USDT-M) Trading Bot for Testnet.

Usage examples:
  # Dry-run a market buy
  python basic_bot.py --api-key YOUR_KEY --api-secret YOUR_SECRET --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --dry-run

  # Place a limit sell
  python_basic_bot.py --api-key YOUR_KEY --api-secret YOUR_SECRET --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 62000

  # TWAP: place 5 market slices over 60 seconds
  python_basic_bot.py --api-key YOUR_KEY --api-secret YOUR_SECRET --symbol BTCUSDT --side BUY --type TWAP --quantity 0.005 --twap-slices 5 --twap-duration 60

Notes:
 - Testnet base URL used: https://testnet.binancefuture.com
 - This script implements signed REST requests required by Binance Futures.
"""

import argparse
import hashlib
import hmac
import logging
import time
import urllib.parse
import requests
import sys
from typing import Optional

# CONFIG
TESTNET_BASE = "https://testnet.binancefuture.com"
# OR if it still fails, try the global base:
# TESTNET_BASE = "https://fapi.binance.com"

ORDER_PATH = "/fapi/v1/order"
RECV_WINDOW = 15000  # optional

# Logging setup
logger = logging.getLogger("BasicBot")
logger.setLevel(logging.DEBUG)
fmt = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")

# Console handler (INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(fmt)
logger.addHandler(ch)

# File handlers
fh = logging.FileHandler("bot.log")
fh.setLevel(logging.DEBUG)
fh.setFormatter(fmt)
logger.addHandler(fh)

# Detailed requests/responses log (sensitive data excluded from printed logs; keys not logged)
req_fh = logging.FileHandler("bot_requests.log")
req_fh.setLevel(logging.DEBUG)
req_fh.setFormatter(fmt)
logger.addHandler(req_fh)




class BinanceAPIError(Exception):
    pass


class BasicBot:
    def __init__(self, api_key: str, api_secret: str, base_url: str = TESTNET_BASE, dry_run: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})
        self.dry_run = dry_run
        logger.debug("Initialized BasicBot (dry_run=%s) with base_url=%s", dry_run, self.base_url)

    def get_server_time(self):
        """Fetch server time from Binance Futures Testnet"""
        url = f"{self.base_url}/fapi/v1/time"
        resp = self.session.get(url, timeout=5)
        data = resp.json()
        return data["serverTime"]

    def _sign(self, params: dict) -> str:
        """
        Sign parameters with HMAC SHA256 as required by Binance.
        Returns signature hex.
        """
        qs = urllib.parse.urlencode(params, doseq=True)
        signature = hmac.new(self.api_secret, qs.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature

    def _timestamped_params(self, extra: dict) -> dict:
        p = dict(extra)
        try:
            server_time = self.get_server_time()
            p["timestamp"] = server_time + 500
        except Exception as e:
            logger.warning("Could not fetch server time, falling back to local time: %s", e)
            p["timestamp"] = int(time.time() * 1000)
        p["recvWindow"] = RECV_WINDOW
        return p

    def request(self, method: str, path: str, params: dict = None, signed: bool = False) -> dict:
        """
        Send request to Binance testnet/specified base URL.
        Logs request + response.
        """
        if params is None:
            params = {}
        url = f"{self.base_url}{path}"
        try:
            if signed:
                full_params = self._timestamped_params(params)
                signature = self._sign(full_params)
                full_params["signature"] = signature
            else:
                full_params = params

            # Log request (do not include api secret; signature included)
            logger.debug("REQUEST --> %s %s params=%s", method.upper(), url, {k: full_params.get(k) for k in full_params if k != "signature"})

            if self.dry_run:
                logger.info("[DRY RUN] Would send request: %s %s", method.upper(), url)
                return {"dry_run": True, "method": method, "url": url, "params": full_params}

            resp = None
            if method.upper() == "GET":
                resp = self.session.get(url, params=full_params, timeout=10)
            elif method.upper() == "POST":
                resp = self.session.post(url, params=full_params, timeout=10)
            elif method.upper() == "DELETE":
                resp = self.session.delete(url, params=full_params, timeout=10)
            else:
                raise ValueError("Unsupported method: " + method)

            logger.debug("HTTP %s %s --> status %s", method.upper(), url, resp.status_code)
            j = resp.json() if resp.text else {}
            logger.debug("RESPONSE <-- %s", j)

            if not resp.ok:
                # Binance returns JSON errors with code/msg
                msg = j.get("msg") or resp.text
                raise BinanceAPIError(f"HTTP {resp.status_code} error: {msg}")

            # Binance may still return error fields; check typical schema
            if isinstance(j, dict) and j.get("code") and j.get("code") < 0:
                raise BinanceAPIError(f"Binance error: {j}")

            return j

        except requests.RequestException as e:
            logger.exception("Network error during request to %s", url)
            raise

    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, price: Optional[float] = None,
                    time_in_force: str = "GTC", reduce_only: bool = False, close_position: bool = False, position_side: Optional[str] = None) -> dict:
        """
        General order function for futures.
        side: BUY or SELL
        order_type: MARKET or LIMIT
        """
        symbol = symbol.upper()
        side = side.upper()
        order_type = order_type.upper()

        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if order_type not in {"MARKET", "LIMIT"}:
            raise ValueError("order_type must be MARKET or LIMIT")

        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": float(quantity),
            "reduceOnly": str(reduce_only).lower(),
            "closePosition": str(close_position).lower(),
        }

        if position_side:
            params["positionSide"] = position_side

        if order_type == "LIMIT":
            if price is None:
                raise ValueError("LIMIT orders require a price")
            params["price"] = str(price)
            params["timeInForce"] = time_in_force

        # Use POST /fapi/v1/order (signed)
        result = self.request("POST", ORDER_PATH, params=params, signed=True)
        logger.info("Order result: %s", result)
        return result

    def place_market_order(self, symbol: str, side: str, quantity: float, reduce_only: bool = False, position_side: Optional[str] = None) -> dict:
        return self.place_order(symbol, side, "MARKET", quantity, price=None, reduce_only=reduce_only, position_side=position_side)

    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float, time_in_force: str = "GTC",
                          reduce_only: bool = False, position_side: Optional[str] = None) -> dict:
        return self.place_order(symbol, side, "LIMIT", quantity, price=price, time_in_force=time_in_force, reduce_only=reduce_only, position_side=position_side)

    def place_twap_order(self, symbol: str, side: str, quantity: float, slices: int = 5, duration: int = 60):
        """
        Simple TWAP: split quantity into `slices` equal parts and send market orders evenly over `duration` seconds.
        This is a naive TWAP; production systems require better error handling, slippage management, cancellation, rate limiting handling, and concurrency protections.
        """
        if slices < 1:
            raise ValueError("slices must be >= 1")
        if duration < 0:
            raise ValueError("duration must be >= 0")

        slice_qty = float(quantity) / slices
        interval = duration / slices if slices > 0 else 0
        logger.info("Starting TWAP: %s %s total=%s slices=%s interval=%.2fs slice_qty=%.8f", symbol, side, quantity, slices, interval, slice_qty)

        responses = []
        for i in range(slices):
            logger.info("TWAP slice %d/%d placing market order qty=%s", i + 1, slices, slice_qty)
            try:
                resp = self.place_market_order(symbol, side, quantity=slice_qty)
                responses.append(resp)
            except Exception as e:
                logger.exception("TWAP slice %d failed", i + 1)
                responses.append({"error": str(e)})
            if i < slices - 1 and interval > 0:
                time.sleep(interval)
        logger.info("TWAP complete")
        return responses


def parse_args():
    p = argparse.ArgumentParser(description="Simplified Binance Futures Testnet Trading Bot (Python)")
    p.add_argument("--api-key", required=True, help="Binance API key (testnet)")
    p.add_argument("--api-secret", required=True, help="Binance API secret (testnet)")
    p.add_argument("--symbol", required=True, help="Trading symbol, e.g. BTCUSDT")
    p.add_argument("--side", required=True, choices=["BUY", "SELL", "buy", "sell"], help="BUY or SELL")
    p.add_argument("--type", required=True, choices=["MARKET", "LIMIT", "TWAP", "market", "limit", "twap"], help="Order type")
    p.add_argument("--quantity", required=True, type=float, help="Quantity to trade (contracts for futures)")
    p.add_argument("--price", type=float, help="Price for LIMIT order")
    p.add_argument("--time-in-force", default="GTC", help="Time in force for limit orders (default GTC)")
    p.add_argument("--dry-run", action="store_true", help="Do not send requests; just log and validate")
    # TWAP options
    p.add_argument("--twap-slices", type=int, default=5, help="TWAP number of slices (default 5)")
    p.add_argument("--twap-duration", type=int, default=60, help="TWAP total duration in seconds (default 60)")
    return p.parse_args()


def main():
    args = parse_args()
    # normalize
    order_type = args.type.upper()
    side = args.side.upper()
    symbol = args.symbol.upper()
    price = args.price
    quantity = args.quantity

    bot = BasicBot(api_key=args.api_key, api_secret=args.api_secret, dry_run=args.dry_run)

    try:
        if order_type == "MARKET":
            logger.info("Placing MARKET order %s %s %s", symbol, side, quantity)
            res = bot.place_market_order(symbol, side, quantity)
            print("Result:", res)

        elif order_type == "LIMIT":
            if price is None:
                logger.error("LIMIT order requires --price")
                sys.exit(2)
            logger.info("Placing LIMIT order %s %s %s @ %s", symbol, side, quantity, price)
            res = bot.place_limit_order(symbol, side, quantity, price, time_in_force=args.time_in_force)
            print("Result:", res)

        elif order_type == "TWAP":
            slices = args.twap_slices
            duration = args.twap_duration
            logger.info("Placing TWAP order %s %s total=%s slices=%s duration=%ss", symbol, side, quantity, slices, duration)
            res = bot.place_twap_order(symbol, side, quantity, slices=slices, duration=duration)
            print("TWAP results:")
            for idx, r in enumerate(res, 1):
                print(f" Slice {idx}: {r}")

        else:
            logger.error("Unsupported order type: %s", order_type)
            sys.exit(2)

    except BinanceAPIError as e:
        logger.error("Binance API returned an error: %s", e)
        print("Error:", e)
        sys.exit(1)

    except Exception as e:
        logger.exception("Unhandled exception")
        print("Unhandled error:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
