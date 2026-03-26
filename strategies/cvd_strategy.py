import pandas as pd

from strategies.base import BaseStrategy, Signal


class CVDStrategy(BaseStrategy):
    """
    Cumulative Volume Delta strategy for Polymarket prediction markets.

    Tracks the running sum of (buy_volume - sell_volume). A rising CVD
    with price divergence signals buying pressure; a falling CVD signals
    selling pressure.

    Expects price_history to contain columns: price, buy_volume, sell_volume.
    """

    def __init__(
        self,
        lookback: int = 20,
        divergence_threshold: float = 0.02,
        price_offset: float = 0.01,
    ):
        super().__init__("CVD")
        self.lookback = lookback
        self.divergence_threshold = divergence_threshold
        self.price_offset = price_offset

    def _compute_cvd(self, price_history: pd.DataFrame) -> pd.Series:
        delta = price_history["buy_volume"] - price_history["sell_volume"]
        return delta.cumsum()

    def generate_signal(self, price_history: pd.DataFrame) -> Signal:
        if len(price_history) < self.lookback:
            return Signal.HOLD

        if "buy_volume" not in price_history.columns:
            return Signal.HOLD

        window = price_history.tail(self.lookback)
        cvd = self._compute_cvd(window)

        price_change = (window["price"].iloc[-1] - window["price"].iloc[0]) / max(
            window["price"].iloc[0], 0.01
        )
        cvd_direction = cvd.iloc[-1] - cvd.iloc[0]

        # Bullish divergence: CVD rising while price flat or falling
        if cvd_direction > 0 and price_change < -self.divergence_threshold:
            return Signal.BUY

        # Bearish divergence: CVD falling while price flat or rising
        if cvd_direction < 0 and price_change > self.divergence_threshold:
            return Signal.SELL

        return Signal.HOLD

    def get_limit_price(
        self, signal: Signal, current_price: float, price_history: pd.DataFrame
    ) -> float:
        if signal == Signal.BUY:
            return max(0.01, current_price - self.price_offset)
        else:
            return min(0.99, current_price + self.price_offset)
