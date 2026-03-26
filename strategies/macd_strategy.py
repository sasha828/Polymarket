import pandas as pd
from ta.trend import MACD

from strategies.base import BaseStrategy, Signal


class MACDStrategy(BaseStrategy):
    """
    MACD crossover strategy for Polymarket prediction markets.

    Generates BUY when the MACD line crosses above the signal line,
    and SELL when it crosses below.
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        price_offset: float = 0.01,
    ):
        super().__init__("MACD")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.price_offset = price_offset

    def generate_signal(self, price_history: pd.DataFrame) -> Signal:
        if len(price_history) < self.slow_period + self.signal_period:
            return Signal.HOLD

        macd = MACD(
            close=price_history["price"],
            window_slow=self.slow_period,
            window_fast=self.fast_period,
            window_sign=self.signal_period,
        )
        macd_line = macd.macd()
        signal_line = macd.macd_signal()

        if len(macd_line) < 2:
            return Signal.HOLD

        prev_diff = macd_line.iloc[-2] - signal_line.iloc[-2]
        curr_diff = macd_line.iloc[-1] - signal_line.iloc[-1]

        if prev_diff <= 0 < curr_diff:
            return Signal.BUY
        elif prev_diff >= 0 > curr_diff:
            return Signal.SELL

        return Signal.HOLD

    def get_limit_price(
        self, signal: Signal, current_price: float, price_history: pd.DataFrame
    ) -> float:
        if signal == Signal.BUY:
            return max(0.01, current_price - self.price_offset)
        else:
            return min(0.99, current_price + self.price_offset)
