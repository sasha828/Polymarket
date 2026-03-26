import logging

from strategies.base import BaseStrategy, MarketContext, OrderRequest

logger = logging.getLogger(__name__)


class MarketMakerStrategy(BaseStrategy):
    """
    Market making strategy for Polymarket.

    Posts two-sided limit orders (bid + ask) around the midpoint to
    capture the bid-ask spread. Earns additional income from Polymarket's
    liquidity rewards program.

    Inventory management: skews quotes away from accumulated inventory
    to encourage mean-reversion back to flat.
    """

    def __init__(
        self,
        half_spread: float = 0.02,
        order_size: float = 10.0,
        max_inventory: float = 100.0,
        skew_factor: float = 0.005,
        min_spread: float = 0.01,
    ):
        super().__init__("MM")
        self.half_spread = half_spread
        self.order_size = order_size
        self.max_inventory = max_inventory
        self.skew_factor = skew_factor
        self.min_spread = min_spread

    def _compute_skew(self, inventory: float) -> float:
        """
        Shift the midpoint to discourage building more inventory.
        Positive inventory (long) -> lower mid -> cheaper asks attract sells.
        Negative inventory (short) -> higher mid -> cheaper bids attract buys.
        """
        return -inventory * self.skew_factor

    def generate_orders(self, ctx: MarketContext) -> list[OrderRequest]:
        orders = []

        for token_id in ctx.token_ids:
            book = ctx.order_books.get(token_id)
            if not book or not book.bids or not book.asks:
                continue

            mid = book.midpoint
            spread = book.spread

            # Don't quote if the existing spread is already tighter than our min
            if spread < self.min_spread:
                logger.debug(
                    "MM skip %s: spread %.3f < min %.3f",
                    token_id[:12],
                    spread,
                    self.min_spread,
                )
                continue

            inventory = ctx.inventory.get(token_id, 0.0)

            # Check inventory limits
            if abs(inventory) >= self.max_inventory:
                logger.warning(
                    "MM inventory limit hit for %s: %.1f",
                    token_id[:12],
                    inventory,
                )
                # Only quote the side that reduces inventory
                if inventory > 0:
                    # Long — only post an ask to sell
                    ask_price = round(min(0.99, mid + self.half_spread / 2), 2)
                    orders.append(
                        OrderRequest(
                            token_id=token_id,
                            side="SELL",
                            price=ask_price,
                            size=self.order_size,
                            reason=f"MM:unwind_ask@{ask_price:.2f}",
                        )
                    )
                else:
                    # Short — only post a bid to buy
                    bid_price = round(max(0.01, mid - self.half_spread / 2), 2)
                    orders.append(
                        OrderRequest(
                            token_id=token_id,
                            side="BUY",
                            price=bid_price,
                            size=self.order_size,
                            reason=f"MM:unwind_bid@{bid_price:.2f}",
                        )
                    )
                continue

            # Apply inventory skew to midpoint
            skew = self._compute_skew(inventory)
            adjusted_mid = mid + skew

            bid_price = round(max(0.01, adjusted_mid - self.half_spread), 2)
            ask_price = round(min(0.99, adjusted_mid + self.half_spread), 2)

            # Ensure we're improving on or matching current best quotes
            bid_price = round(max(bid_price, book.best_bid), 2)
            ask_price = round(min(ask_price, book.best_ask), 2)

            # Safety: bid must be below ask
            if bid_price >= ask_price:
                logger.debug("MM skip %s: bid %.2f >= ask %.2f", token_id[:12], bid_price, ask_price)
                continue

            logger.info(
                "MM quoting %s: bid=%.2f ask=%.2f mid=%.2f inv=%.1f skew=%.4f",
                token_id[:12],
                bid_price,
                ask_price,
                mid,
                inventory,
                skew,
            )

            orders.append(
                OrderRequest(
                    token_id=token_id,
                    side="BUY",
                    price=bid_price,
                    size=self.order_size,
                    reason=f"MM:bid@{bid_price:.2f}",
                )
            )
            orders.append(
                OrderRequest(
                    token_id=token_id,
                    side="SELL",
                    price=ask_price,
                    size=self.order_size,
                    reason=f"MM:ask@{ask_price:.2f}",
                )
            )

        return orders
