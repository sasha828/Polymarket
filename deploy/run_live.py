"""
Entry point for live trading on Polymarket.

Usage:
    # Yes/No arbitrage (requires both token IDs):
    python -m deploy.run_live --strategy arb --yes-token <YES_ID> --no-token <NO_ID>

    # Market making on a single token:
    python -m deploy.run_live --strategy mm --token-id <TOKEN_ID>

    # Scanner (bond strategy) on a single token:
    python -m deploy.run_live --strategy scanner --token-id <TOKEN_ID>
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from py_clob_client.client import ClobClient

from bot.risk_manager import RiskManager
from bot.trader import Trader
from strategies import ArbStrategy, MarketMakerStrategy, ScannerStrategy

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def build_client() -> ClobClient:
    host = os.environ["CLOB_API_URL"]
    key = os.environ["CLOB_API_KEY"]
    secret = os.environ["CLOB_API_SECRET"]
    passphrase = os.environ["CLOB_API_PASSPHRASE"]
    chain_id = int(os.environ.get("CHAIN_ID", "137"))

    return ClobClient(
        host,
        key=key,
        secret=secret,
        passphrase=passphrase,
        chain_id=chain_id,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket live trading bot")
    parser.add_argument(
        "--strategy",
        choices=["arb", "mm", "scanner"],
        required=True,
        help="Trading strategy: arb (Yes/No arbitrage), mm (market maker), scanner (bond/fade)",
    )
    parser.add_argument("--token-id", help="Token ID (for mm and scanner strategies)")
    parser.add_argument("--yes-token", help="YES token ID (for arb strategy)")
    parser.add_argument("--no-token", help="NO token ID (for arb strategy)")
    parser.add_argument(
        "--order-size",
        type=float,
        default=float(os.environ.get("DEFAULT_ORDER_SIZE", "10.0")),
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.environ.get("POLL_INTERVAL_SECONDS", "5")),
    )
    args = parser.parse_args()

    # Build token list and strategy based on mode
    if args.strategy == "arb":
        if not args.yes_token or not args.no_token:
            parser.error("--yes-token and --no-token are required for arb strategy")
        token_ids = [args.yes_token, args.no_token]
        strategy = ArbStrategy(order_size=args.order_size)
    elif args.strategy == "mm":
        if not args.token_id:
            parser.error("--token-id is required for mm strategy")
        token_ids = [args.token_id]
        strategy = MarketMakerStrategy(order_size=args.order_size)
    elif args.strategy == "scanner":
        if not args.token_id:
            parser.error("--token-id is required for scanner strategy")
        token_ids = [args.token_id]
        strategy = ScannerStrategy(order_size=args.order_size)

    client = build_client()
    risk_manager = RiskManager(
        max_position_size=float(os.environ.get("MAX_POSITION_SIZE", "100.0")),
        max_daily_loss=float(os.environ.get("MAX_DAILY_LOSS", "50.0")),
        max_open_orders=int(os.environ.get("MAX_OPEN_ORDERS", "20")),
    )

    trader = Trader(
        client=client,
        strategy=strategy,
        risk_manager=risk_manager,
        token_ids=token_ids,
        poll_interval=args.poll_interval,
    )

    logger.info("Starting %s strategy...", args.strategy.upper())
    try:
        trader.run()
    except KeyboardInterrupt:
        trader.stop()
        logger.info("Bot shut down cleanly")
        sys.exit(0)


if __name__ == "__main__":
    main()
