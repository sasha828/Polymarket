import logging
import time

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs

from bot.risk_manager import RiskManager
from strategies.base import BaseStrategy, MarketContext, OrderBookSnapshot, OrderRequest

logger = logging.getLogger(__name__)


class Trader:
    """
    Core trading loop. Fetches order books, runs strategy logic,
    and submits limit orders through the Polymarket CLOB API.

    Supports multi-token strategies (e.g. YES/NO arbitrage).
    """

    def __init__(
        self,
        client: ClobClient,
        strategy: BaseStrategy,
        risk_manager: RiskManager,
        token_ids: list[str],
        poll_interval: float = 5.0,
    ):
        self.client = client
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.token_ids = token_ids
        self.poll_interval = poll_interval
        self.running = False
        self.inventory: dict[str, float] = {tid: 0.0 for tid in token_ids}
        self.open_order_ids: list[str] = []

    def _fetch_order_book(self, token_id: str) -> OrderBookSnapshot | None:
        try:
            book = self.client.get_order_book(token_id)
            bids = [(float(b.price), float(b.size)) for b in book.bids]
            asks = [(float(a.price), float(a.size)) for a in book.asks]
            return OrderBookSnapshot(token_id=token_id, bids=bids, asks=asks)
        except Exception:
            logger.exception("Failed to fetch order book for %s", token_id)
            return None

    def _fetch_all_books(self) -> dict[str, OrderBookSnapshot] | None:
        books = {}
        for tid in self.token_ids:
            snap = self._fetch_order_book(tid)
            if snap is None:
                return None
            books[tid] = snap
        return books

    def _cancel_stale_orders(self) -> None:
        for order_id in self.open_order_ids:
            try:
                self.client.cancel(order_id)
                logger.debug("Cancelled stale order %s", order_id)
            except Exception:
                logger.debug("Could not cancel order %s (may already be filled)", order_id)
        self.open_order_ids.clear()

    def _submit_limit_order(self, order: OrderRequest) -> str | None:
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

    def tick(self) -> None:
        """Execute one iteration of the trading loop."""
        # Cancel previous cycle's orders before requoting
        self._cancel_stale_orders()

        books = self._fetch_all_books()
        if books is None:
            return

        ctx = MarketContext(
            token_ids=self.token_ids,
            order_books=books,
            inventory=dict(self.inventory),
        )

        orders = self.strategy.generate_orders(ctx)
        if not orders:
            logger.debug("No orders from %s", self.strategy.name)
            return

        for order in orders:
            approved, reason = self.risk_manager.check_order(order)
            if not approved:
                logger.warning("Order rejected: %s", reason)
                continue

            order_id = self._submit_limit_order(order)
            if order_id:
                self.open_order_ids.append(order_id)
                self.risk_manager.record_order_placed()

    def run(self) -> None:
        """Start the main polling loop."""
        self.running = True
        logger.info(
            "Trader started: strategy=%s tokens=%s interval=%.1fs",
            self.strategy.name,
            self.token_ids,
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
        self._cancel_stale_orders()
        logger.info("Trader stopped")
