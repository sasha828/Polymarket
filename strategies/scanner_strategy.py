import logging

from strategies.base import BaseStrategy, MarketContext, OrderRequest

logger = logging.getLogger(__name__)


class ScannerStrategy(BaseStrategy):
    """
    Market scanner / calibration edge strategy for Polymarket.

    Exploits systematic mispricings in prediction markets:
    1. "Bond strategy": Buy near-certain outcomes (price > high_threshold)
       at a discount — collect $1.00 at resolution for a small, consistent gain.
    2. "Fade longshots": Sell overpriced longshot contracts (price < low_threshold)
       that are inflated by fan/public bias.

    Operates on a single token. For multi-market scanning, run multiple
    instances or use the scanner entry point.
    """

    def __init__(
        self,
        high_threshold: float = 0.92,
        low_threshold: float = 0.08,
        max_buy_price: float = 0.97,
        min_sell_price: float = 0.03,
        order_size: float = 15.0,
    ):
        super().__init__("SCANNER")
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.max_buy_price = max_buy_price
        self.min_sell_price = min_sell_price
        self.order_size = order_size

    def generate_orders(self, ctx: MarketContext) -> list[OrderRequest]:
        orders = []

        for token_id in ctx.token_ids:
            book = ctx.order_books.get(token_id)
            if not book:
                continue

            mid = book.midpoint
            current_inventory = ctx.inventory.get(token_id, 0.0)

            # Bond strategy: buy near-certain outcomes at a discount
            if mid >= self.high_threshold and book.asks:
                best_ask = book.best_ask
                # Place limit below the ask to get a better fill
                limit_price = round(min(best_ask, self.max_buy_price) - 0.01, 2)

                if self.high_threshold <= limit_price <= self.max_buy_price:
                    expected_return = (1.0 - limit_price) / limit_price * 100
                    logger.info(
                        "SCANNER bond: %s mid=%.2f, limit=%.2f, expected=%.1f%%",
                        token_id[:12],
                        mid,
                        limit_price,
                        expected_return,
                    )
                    orders.append(
                        OrderRequest(
                            token_id=token_id,
                            side="BUY",
                            price=limit_price,
                            size=self.order_size,
                            reason=f"SCANNER:bond@{limit_price:.2f}",
                        )
                    )

            # Fade longshots: sell overpriced low-probability contracts
            elif mid <= self.low_threshold and current_inventory > 0 and book.bids:
                best_bid = book.best_bid
                limit_price = round(max(best_bid, self.min_sell_price) + 0.01, 2)

                if self.min_sell_price <= limit_price <= self.low_threshold:
                    size = min(self.order_size, current_inventory)
                    logger.info(
                        "SCANNER fade longshot: %s mid=%.2f, limit=%.2f",
                        token_id[:12],
                        mid,
                        limit_price,
                    )
                    orders.append(
                        OrderRequest(
                            token_id=token_id,
                            side="SELL",
                            price=limit_price,
                            size=size,
                            reason=f"SCANNER:fade@{limit_price:.2f}",
                        )
                    )

        return orders
