import pandas as pd
from ta.momentum import RSIIndicator

from strategies.base import BaseStrategy, Signal


class RSIStrategy(BaseStrategy):
    """
    RSI mean-reversion strategy for Polymarket prediction markets.

    Generates BUY when RSI drops below the oversold threshold,
    and SELL when RSI rises above the overbought threshold.
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        price_offset: float = 0.01,
    ):
        super().__init__("RSI")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.price_offset = price_offset

    def generate_signal(self, price_history: pd.DataFrame) -> Signal:
        if len(price_history) < self.period + 1:
            return Signal.HOLD

        rsi = RSIIndicator(
            close=price_history["price"], window=self.period
        ).rsi()

        current_rsi = rsi.iloc[-1]

        if current_rsi < self.oversold:
            return Signal.BUY
        elif current_rsi > self.overbought:
            return Signal.SELL

        return Signal.HOLD

    def get_limit_price(
        self, signal: Signal, current_price: float, price_history: pd.DataFrame
    ) -> float:
        if signal == Signal.BUY:
            return max(0.01, current_price - self.price_offset)
        else:
            return min(0.99, current_price + self.price_offset)
