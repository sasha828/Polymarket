import logging
from dataclasses import dataclass, field

from strategies.base import OrderRequest

logger = logging.getLogger(__name__)


@dataclass
class RiskManager:
    """
    Enforces risk limits before orders are submitted.

    - max_position_size: maximum notional value of any single position
    - max_daily_loss: maximum cumulative loss allowed per day
    - max_open_orders: maximum number of concurrent open orders
    - price_bounds: Polymarket prices must be in (0, 1)
    """

    max_position_size: float = 100.0
    max_daily_loss: float = 50.0
    max_open_orders: int = 10
    daily_pnl: float = 0.0
    open_order_count: int = 0
    positions: dict[str, float] = field(default_factory=dict)

    def check_order(self, order: OrderRequest) -> tuple[bool, str]:
        """Return (approved, reason) for the proposed order."""
        # Price bounds check
        if not 0.01 <= order.price <= 0.99:
            return False, f"Price {order.price} outside valid range [0.01, 0.99]"

        # Daily loss check
        if self.daily_pnl <= -self.max_daily_loss:
            return False, f"Daily loss limit reached: ${self.daily_pnl:.2f}"

        # Open order limit
        if self.open_order_count >= self.max_open_orders:
            return False, f"Max open orders reached: {self.open_order_count}"

        # Position size check
        notional = order.price * order.size
        current_position = self.positions.get(order.token_id, 0.0)
        if order.side == "BUY":
            new_position = current_position + notional
        else:
            new_position = current_position - notional

        if abs(new_position) > self.max_position_size:
            return False, (
                f"Position would exceed max: ${abs(new_position):.2f} > "
                f"${self.max_position_size:.2f}"
            )

        logger.info("Order approved: %s", order)
        return True, "approved"

    def record_fill(self, token_id: str, side: str, price: float, size: float) -> None:
        notional = price * size
        current = self.positions.get(token_id, 0.0)
        if side == "BUY":
            self.positions[token_id] = current + notional
        else:
            self.positions[token_id] = current - notional
        self.open_order_count = max(0, self.open_order_count - 1)

    def record_order_placed(self) -> None:
        self.open_order_count += 1

    def update_daily_pnl(self, pnl_change: float) -> None:
        self.daily_pnl += pnl_change

    def reset_daily(self) -> None:
        self.daily_pnl = 0.0
