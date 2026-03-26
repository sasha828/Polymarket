import logging
import os
import time

import pandas as pd
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

from bot.risk_manager import RiskManager
from strategies.base import BaseStrategy, OrderRequest

logger = logging.getLogger(__name__)


class Trader:
    """
    Core trading loop. Fetches market data, runs strategy signals,
    and submits limit orders through the Polymarket CLOB API.
    """

    def __init__(
        self,
        client: ClobClient,
        strategy: BaseStrategy,
        risk_manager: RiskManager,
        token_id: str,
        order_size: float = 10.0,
        poll_interval: int = 30,
    ):
        self.client = client
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.token_id = token_id
        self.order_size = order_size
        self.poll_interval = poll_interval
        self.running = False
        self.price_history: list[dict] = []

    def _fetch_current_price(self) -> float | None:
        """Fetch the current mid-market price from the order book."""
        try:
            book = self.client.get_order_book(self.token_id)
            best_bid = float(book.bids[0].price) if book.bids else 0.0
            best_ask = float(book.asks[0].price) if book.asks else 1.0
            return (best_bid + best_ask) / 2
        except Exception:
            logger.exception("Failed to fetch order book")
            return None

    def _build_price_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.price_history)

    def _submit_limit_order(self, order: OrderRequest) -> str | None:
        """Submit a limit order via the CLOB client. Returns order ID or None."""
        try:
            order_args = OrderArgs(
                token_id=order.token_id,
                price=order.price,
                size=order.size,
                side=order.side,
            )
            response = self.client.create_order(order_args)
            order_id = response.get("orderID")
            logger.info(
                "Order placed: %s %s @ %.2f x %.1f [%s] -> %s",
                order.side,
                order.token_id,
                order.price,
                order.size,
                order.reason,
                order_id,
            )
            return order_id
        except Exception:
            logger.exception("Failed to submit order")
            return None

    def _cancel_open_orders(self) -> None:
        """Cancel all open orders for the tracked token."""
        try:
            open_orders = self.client.get_orders(
                params={"asset_id": self.token_id, "state": "live"}
            )
            for order in open_orders:
                self.client.cancel(order["id"])
                logger.info("Cancelled order %s", order["id"])
        except Exception:
            logger.exception("Failed to cancel open orders")

    def tick(self) -> None:
        """Execute one iteration of the trading loop."""
        price = self._fetch_current_price()
        if price is None:
            return

        self.price_history.append(
            {
                "price": price,
                "timestamp": pd.Timestamp.now(),
                "buy_volume": 0.0,
                "sell_volume": 0.0,
            }
        )

        df = self._build_price_dataframe()
        signal = self.strategy.generate_signal(df)
        order = self.strategy.create_order(
            self.token_id, signal, price, self.order_size, df
        )

        if order is None:
            logger.debug("Signal: HOLD — no order")
            return

        approved, reason = self.risk_manager.check_order(order)
        if not approved:
            logger.warning("Order rejected by risk manager: %s", reason)
            return

        order_id = self._submit_limit_order(order)
        if order_id:
            self.risk_manager.record_order_placed()

    def run(self) -> None:
        """Start the main polling loop."""
        self.running = True
        logger.info(
            "Trader started: strategy=%s token=%s interval=%ds",
            self.strategy.name,
            self.token_id,
            self.poll_interval,
        )
        while self.running:
            try:
                self.tick()
            except KeyboardInterrupt:
                logger.info("Shutting down trader...")
                self.running = False
            except Exception:
                logger.exception("Unhandled error in trading loop")
            time.sleep(self.poll_interval)

    def stop(self) -> None:
        self.running = False
        self._cancel_open_orders()
        logger.info("Trader stopped")
