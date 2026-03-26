from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class OrderBookSnapshot:
    """Snapshot of one side of an order book."""

    token_id: str
    bids: list[tuple[float, float]] = field(default_factory=list)  # (price, size)
    asks: list[tuple[float, float]] = field(default_factory=list)  # (price, size)

    @property
    def best_bid(self) -> float:
        return self.bids[0][0] if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0][0] if self.asks else 1.0

    @property
    def midpoint(self) -> float:
        return (self.best_bid + self.best_ask) / 2

    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid


@dataclass
class OrderRequest:
    token_id: str
    side: str  # "BUY" or "SELL"
    price: float
    size: float
    reason: str


@dataclass
class MarketContext:
    """All data a strategy needs to make decisions."""

    token_ids: list[str]
    order_books: dict[str, OrderBookSnapshot]  # token_id -> snapshot
    inventory: dict[str, float]  # token_id -> net shares held


class BaseStrategy(ABC):
    """Base class for all trading strategies."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def generate_orders(self, ctx: MarketContext) -> list[OrderRequest]:
        """Analyze market context and return zero or more limit orders."""
