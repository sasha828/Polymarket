import logging
from dataclasses import dataclass, field

import pandas as pd

from strategies.base import BaseStrategy, Signal

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    timestamp: pd.Timestamp
    side: str
    price: float
    size: float
    reason: str


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    initial_balance: float = 0.0
    final_balance: float = 0.0

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def pnl(self) -> float:
        return self.final_balance - self.initial_balance

    @property
    def return_pct(self) -> float:
        if self.initial_balance == 0:
            return 0.0
        return (self.pnl / self.initial_balance) * 100

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        # Pair up buy/sell trades and check profitability
        buys: list[Trade] = []
        wins = 0
        total_pairs = 0
        for trade in self.trades:
            if trade.side == "BUY":
                buys.append(trade)
            elif trade.side == "SELL" and buys:
                buy = buys.pop(0)
                total_pairs += 1
                if trade.price > buy.price:
                    wins += 1
        return (wins / total_pairs * 100) if total_pairs > 0 else 0.0

    @property
    def max_drawdown(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for value in self.equity_curve:
            peak = max(peak, value)
            dd = (peak - value) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        return max_dd * 100

    def summary(self) -> str:
        return (
            f"Backtest Results\n"
            f"{'='*40}\n"
            f"Total Trades:  {self.total_trades}\n"
            f"PnL:           ${self.pnl:.2f}\n"
            f"Return:        {self.return_pct:.2f}%\n"
            f"Win Rate:      {self.win_rate:.1f}%\n"
            f"Max Drawdown:  {self.max_drawdown:.2f}%\n"
        )


class BacktestEngine:
    """
    Simulates strategy execution against historical price data.

    Assumes limit orders fill at the requested price when the market
    price crosses through it on the next bar.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_balance: float = 1000.0,
        order_size: float = 10.0,
        fee_rate: float = 0.0,
    ):
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.order_size = order_size
        self.fee_rate = fee_rate

    def run(self, price_history: pd.DataFrame) -> BacktestResult:
        """
        Run the backtest over the provided price history DataFrame.

        Expects at minimum a 'price' column and a DatetimeIndex or
        'timestamp' column.
        """
        result = BacktestResult(initial_balance=self.initial_balance)
        balance = self.initial_balance
        position = 0.0
        pending_order = None

        for i in range(1, len(price_history)):
            current_bar = price_history.iloc[i]
            current_price = current_bar["price"]

            # Check if pending limit order fills
            if pending_order is not None:
                filled = False
                if pending_order["side"] == "BUY" and current_price <= pending_order["price"]:
                    filled = True
                elif pending_order["side"] == "SELL" and current_price >= pending_order["price"]:
                    filled = True

                if filled:
                    fill_price = pending_order["price"]
                    size = pending_order["size"]
                    fee = fill_price * size * self.fee_rate

                    if pending_order["side"] == "BUY":
                        balance -= fill_price * size + fee
                        position += size
                    else:
                        balance += fill_price * size - fee
                        position -= size

                    ts = (
                        current_bar.name
                        if isinstance(current_bar.name, pd.Timestamp)
                        else pd.Timestamp.now()
                    )
                    result.trades.append(
                        Trade(
                            timestamp=ts,
                            side=pending_order["side"],
                            price=fill_price,
                            size=size,
                            reason=pending_order["reason"],
                        )
                    )
                    pending_order = None

            # Generate new signal from history up to current bar
            history_slice = price_history.iloc[: i + 1]
            signal = self.strategy.generate_signal(history_slice)

            if signal != Signal.HOLD and pending_order is None:
                # Only buy if we have balance, only sell if we have position
                if signal == Signal.BUY and balance >= self.order_size * current_price:
                    limit_price = self.strategy.get_limit_price(
                        signal, current_price, history_slice
                    )
                    pending_order = {
                        "side": "BUY",
                        "price": limit_price,
                        "size": self.order_size,
                        "reason": f"{self.strategy.name}:{signal.value}",
                    }
                elif signal == Signal.SELL and position >= self.order_size:
                    limit_price = self.strategy.get_limit_price(
                        signal, current_price, history_slice
                    )
                    pending_order = {
                        "side": "SELL",
                        "price": limit_price,
                        "size": self.order_size,
                        "reason": f"{self.strategy.name}:{signal.value}",
                    }

            # Mark-to-market equity
            equity = balance + position * current_price
            result.equity_curve.append(equity)

        result.final_balance = balance + position * price_history["price"].iloc[-1]
        return result
