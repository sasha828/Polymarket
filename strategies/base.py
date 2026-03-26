from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import pandas as pd


class Signal(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class OrderRequest:
    token_id: str
    side: str  # "BUY" or "SELL"
    price: float
    size: float
    reason: str


class BaseStrategy(ABC):
    """Base class for all trading strategies."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def generate_signal(self, price_history: pd.DataFrame) -> Signal:
        """Analyze price history and return a trading signal."""

    @abstractmethod
    def get_limit_price(
        self, signal: Signal, current_price: float, price_history: pd.DataFrame
    ) -> float:
        """Compute the limit order price for a given signal."""

    def create_order(
        self,
        token_id: str,
        signal: Signal,
        current_price: float,
        size: float,
        price_history: pd.DataFrame,
    ) -> OrderRequest | None:
        if signal == Signal.HOLD:
            return None

        price = self.get_limit_price(signal, current_price, price_history)
        side = "BUY" if signal == Signal.BUY else "SELL"
        return OrderRequest(
            token_id=token_id,
            side=side,
            price=round(price, 2),
            size=size,
            reason=f"{self.name}:{signal.value}",
        )
