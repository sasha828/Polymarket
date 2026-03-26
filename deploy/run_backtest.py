"""
Entry point for backtesting strategies against historical data.

Usage:
    python -m deploy.run_backtest --strategy macd --data prices.csv
"""

import argparse
import logging

import pandas as pd

from backtesting.engine import BacktestEngine
from strategies import CVDStrategy, MACDStrategy, RSIStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STRATEGY_MAP = {
    "macd": MACDStrategy,
    "rsi": RSIStrategy,
    "cvd": CVDStrategy,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest Polymarket strategies")
    parser.add_argument(
        "--strategy",
        choices=list(STRATEGY_MAP.keys()),
        default="macd",
        help="Strategy to backtest",
    )
    parser.add_argument(
        "--data",
        required=True,
        help="Path to CSV with historical price data (columns: timestamp, price)",
    )
    parser.add_argument(
        "--balance", type=float, default=1000.0, help="Starting balance"
    )
    parser.add_argument(
        "--order-size", type=float, default=10.0, help="Order size per trade"
    )
    args = parser.parse_args()

    df = pd.read_csv(args.data, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Fill missing volume columns for non-CVD strategies
    for col in ["buy_volume", "sell_volume"]:
        if col not in df.columns:
            df[col] = 0.0

    strategy = STRATEGY_MAP[args.strategy]()
    engine = BacktestEngine(
        strategy=strategy,
        initial_balance=args.balance,
        order_size=args.order_size,
    )

    logger.info("Running backtest: strategy=%s rows=%d", args.strategy, len(df))
    result = engine.run(df)
    print(result.summary())


if __name__ == "__main__":
    main()
