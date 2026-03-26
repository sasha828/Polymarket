"""
Entry point for live trading on Polymarket.

Usage:
    python -m deploy.run_live --token-id <TOKEN_ID> --strategy macd
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from py_clob_client.client import ClobClient

from bot.risk_manager import RiskManager
from bot.trader import Trader
from strategies import CVDStrategy, MACDStrategy, RSIStrategy

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STRATEGY_MAP = {
    "macd": MACDStrategy,
    "rsi": RSIStrategy,
    "cvd": CVDStrategy,
}


def build_client() -> ClobClient:
    host = os.environ["CLOB_API_URL"]
    key = os.environ["CLOB_API_KEY"]
    secret = os.environ["CLOB_API_SECRET"]
    passphrase = os.environ["CLOB_API_PASSPHRASE"]
    chain_id = int(os.environ.get("CHAIN_ID", "137"))

    client = ClobClient(
        host,
        key=key,
        secret=secret,
        passphrase=passphrase,
        chain_id=chain_id,
    )
    return client


def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket live trading bot")
    parser.add_argument("--token-id", required=True, help="CLOB token ID to trade")
    parser.add_argument(
        "--strategy",
        choices=list(STRATEGY_MAP.keys()),
        default="macd",
        help="Trading strategy to use",
    )
    parser.add_argument(
        "--order-size",
        type=float,
        default=float(os.environ.get("DEFAULT_ORDER_SIZE", "10.0")),
        help="Size per order",
    )
    args = parser.parse_args()

    client = build_client()
    strategy = STRATEGY_MAP[args.strategy]()

    risk_manager = RiskManager(
        max_position_size=float(os.environ.get("MAX_POSITION_SIZE", "100.0")),
        max_daily_loss=float(os.environ.get("MAX_DAILY_LOSS", "50.0")),
        max_open_orders=int(os.environ.get("MAX_OPEN_ORDERS", "10")),
    )

    trader = Trader(
        client=client,
        strategy=strategy,
        risk_manager=risk_manager,
        token_id=args.token_id,
        order_size=args.order_size,
        poll_interval=int(os.environ.get("POLL_INTERVAL_SECONDS", "30")),
    )

    logger.info("Starting live trader with %s strategy...", args.strategy.upper())
    try:
        trader.run()
    except KeyboardInterrupt:
        trader.stop()
        logger.info("Bot shut down cleanly")
        sys.exit(0)


if __name__ == "__main__":
    main()
