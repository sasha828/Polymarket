"""
Entry point for scanning multiple Polymarket markets for mispriced contracts.

Fetches all active markets, identifies near-certain outcomes trading at a
discount (bond strategy), and places limit buy orders.

Usage:
    python -m deploy.run_scanner --min-price 0.92 --max-price 0.97 --order-size 15
"""

import argparse
import logging
import os
import sys
import time

from dotenv import load_dotenv
from py_clob_client.client import ClobClient

from bot.risk_manager import RiskManager
from strategies.base import MarketContext, OrderBookSnapshot, OrderRequest
from strategies.scanner_strategy import ScannerStrategy

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


def fetch_order_book(client: ClobClient, token_id: str) -> OrderBookSnapshot | None:
    try:
        book = client.get_order_book(token_id)
        bids = [(float(b.price), float(b.size)) for b in book.bids]
        asks = [(float(a.price), float(a.size)) for a in book.asks]
        return OrderBookSnapshot(token_id=token_id, bids=bids, asks=asks)
    except Exception:
        logger.debug("Failed to fetch book for %s", token_id)
        return None


def scan_markets(client: ClobClient) -> list[dict]:
    """Fetch all active markets and return their metadata."""
    try:
        # py-clob-client's get_markets() returns paginated results
        markets = []
        next_cursor = None
        while True:
            params = {"active": True}
            if next_cursor:
                params["next_cursor"] = next_cursor
            response = client.get_markets(params=params)
            batch = response if isinstance(response, list) else response.get("data", [])
            if not batch:
                break
            markets.extend(batch)
            # Check for pagination
            if isinstance(response, dict) and response.get("next_cursor"):
                next_cursor = response["next_cursor"]
            else:
                break
        return markets
    except Exception:
        logger.exception("Failed to fetch markets")
        return []


def submit_order(client: ClobClient, order: OrderRequest) -> str | None:
    try:
        from py_clob_client.clob_types import OrderArgs

        order_args = OrderArgs(
            token_id=order.token_id,
            price=order.price,
            size=order.size,
            side=order.side,
        )
        response = client.create_order(order_args)
        order_id = response.get("orderID")
        logger.info(
            "Scanner order: %s %s @ %.2f x %.1f [%s] -> %s",
            order.side,
            order.token_id[:12],
            order.price,
            order.size,
            order.reason,
            order_id,
        )
        return order_id
    except Exception:
        logger.exception("Failed to submit order")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan Polymarket for mispriced markets")
    parser.add_argument("--min-price", type=float, default=0.92, help="Min midpoint for bond buys")
    parser.add_argument("--max-price", type=float, default=0.97, help="Max limit price for bond buys")
    parser.add_argument("--order-size", type=float, default=15.0)
    parser.add_argument("--scan-interval", type=int, default=300, help="Seconds between scans")
    parser.add_argument("--dry-run", action="store_true", help="Log opportunities without placing orders")
    args = parser.parse_args()

    client = build_client()
    strategy = ScannerStrategy(
        high_threshold=args.min_price,
        max_buy_price=args.max_price,
        order_size=args.order_size,
    )
    risk_manager = RiskManager(
        max_position_size=float(os.environ.get("MAX_POSITION_SIZE", "100.0")),
        max_daily_loss=float(os.environ.get("MAX_DAILY_LOSS", "50.0")),
        max_open_orders=int(os.environ.get("MAX_OPEN_ORDERS", "20")),
    )

    logger.info(
        "Scanner started: min_price=%.2f max_price=%.2f interval=%ds dry_run=%s",
        args.min_price,
        args.max_price,
        args.scan_interval,
        args.dry_run,
    )

    while True:
        try:
            markets = scan_markets(client)
            logger.info("Scanning %d active markets...", len(markets))

            for market in markets:
                tokens = market.get("tokens", [])
                for token in tokens:
                    token_id = token.get("token_id")
                    if not token_id:
                        continue

                    book = fetch_order_book(client, token_id)
                    if not book or not book.asks:
                        continue

                    # Quick filter: only look at high-probability tokens
                    if book.midpoint < args.min_price:
                        continue

                    ctx = MarketContext(
                        token_ids=[token_id],
                        order_books={token_id: book},
                        inventory={token_id: 0.0},
                    )
                    orders = strategy.generate_orders(ctx)

                    for order in orders:
                        approved, reason = risk_manager.check_order(order)
                        if not approved:
                            logger.debug("Rejected: %s", reason)
                            continue

                        market_q = market.get("question", "unknown")
                        outcome = token.get("outcome", "?")
                        logger.info(
                            "Opportunity: %s [%s] @ %.2f (mid=%.2f)",
                            market_q[:60],
                            outcome,
                            order.price,
                            book.midpoint,
                        )

                        if not args.dry_run:
                            submit_order(client, order)
                            risk_manager.record_order_placed()

        except KeyboardInterrupt:
            logger.info("Scanner stopped")
            sys.exit(0)
        except Exception:
            logger.exception("Error during scan cycle")

        time.sleep(args.scan_interval)


if __name__ == "__main__":
    main()
