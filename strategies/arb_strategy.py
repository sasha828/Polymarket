import logging

from strategies.base import BaseStrategy, MarketContext, OrderRequest

logger = logging.getLogger(__name__)


class ArbStrategy(BaseStrategy):
    """
    Yes/No arbitrage strategy for Polymarket.

    On Polymarket, YES + NO tokens for the same market must sum to $1.00.
    When best_ask(YES) + best_ask(NO) < 1.00, buy both sides to lock in
    a risk-free profit equal to 1.00 - total_cost per share.

    Requires exactly two token_ids: [yes_token_id, no_token_id].
    """

    def __init__(
        self,
        min_edge: float = 0.01,
        order_size: float = 20.0,
    ):
        super().__init__("ARB")
        self.min_edge = min_edge
        self.order_size = order_size

    def generate_orders(self, ctx: MarketContext) -> list[OrderRequest]:
        if len(ctx.token_ids) != 2:
            logger.warning("Arb strategy requires exactly 2 token IDs (YES and NO)")
            return []

        yes_id, no_id = ctx.token_ids
        yes_book = ctx.order_books.get(yes_id)
        no_book = ctx.order_books.get(no_id)

        if not yes_book or not no_book:
            return []
        if not yes_book.asks or not no_book.asks:
            return []

        orders = []

        # Buy-buy arbitrage: buy YES + buy NO for less than $1.00
        best_ask_yes = yes_book.best_ask
        best_ask_no = no_book.best_ask
        total_cost = best_ask_yes + best_ask_no

        if total_cost < (1.0 - self.min_edge):
            edge = 1.0 - total_cost
            # Size limited by available liquidity on both sides
            yes_liq = yes_book.asks[0][1]
            no_liq = no_book.asks[0][1]
            size = min(self.order_size, yes_liq, no_liq)

            if size > 0:
                logger.info(
                    "ARB opportunity: YES@%.2f + NO@%.2f = %.3f (edge: %.3f, size: %.1f)",
                    best_ask_yes,
                    best_ask_no,
                    total_cost,
                    edge,
                    size,
                )
                orders.append(
                    OrderRequest(
                        token_id=yes_id,
                        side="BUY",
                        price=round(best_ask_yes, 2),
                        size=size,
                        reason=f"ARB:buy_yes@{best_ask_yes:.2f}",
                    )
                )
                orders.append(
                    OrderRequest(
                        token_id=no_id,
                        side="BUY",
                        price=round(best_ask_no, 2),
                        size=size,
                        reason=f"ARB:buy_no@{best_ask_no:.2f}",
                    )
                )

        # Sell-sell arbitrage: if holding both sides and bids sum > $1.00
        yes_held = ctx.inventory.get(yes_id, 0.0)
        no_held = ctx.inventory.get(no_id, 0.0)

        if yes_held > 0 and no_held > 0 and yes_book.bids and no_book.bids:
            best_bid_yes = yes_book.best_bid
            best_bid_no = no_book.best_bid
            total_bid = best_bid_yes + best_bid_no

            if total_bid > (1.0 + self.min_edge):
                size = min(self.order_size, yes_held, no_held)
                if size > 0:
                    logger.info(
                        "ARB sell opportunity: bids sum %.3f > 1.00",
                        total_bid,
                    )
                    orders.append(
                        OrderRequest(
                            token_id=yes_id,
                            side="SELL",
                            price=round(best_bid_yes, 2),
                            size=size,
                            reason=f"ARB:sell_yes@{best_bid_yes:.2f}",
                        )
                    )
                    orders.append(
                        OrderRequest(
                            token_id=no_id,
                            side="SELL",
                            price=round(best_bid_no, 2),
                            size=size,
                            reason=f"ARB:sell_no@{best_bid_no:.2f}",
                        )
                    )

        return orders
