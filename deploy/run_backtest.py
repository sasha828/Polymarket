"""
Entry point for backtesting the market maker strategy against historical data.

Usage:
    python -m deploy.run_backtest --data prices.csv --balance 1000
"""

import argparse
import logging

import pandas as pd

from backtesting.engine import BacktestEngine
from strategies.market_maker_strategy import MarketMakerStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest Polymarket strategies")
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
    parser.add_argument(
        "--half-spread", type=float, default=0.02, help="Half-spread for market maker"
    )
    args = parser.parse_args()

    df = pd.read_csv(args.data, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    strategy = MarketMakerStrategy(
        half_spread=args.half_spread,
        order_size=args.order_size,
    )
    engine = BacktestEngine(
        strategy=strategy,
        initial_balance=args.balance,
        order_size=args.order_size,
    )

    logger.info("Running MM backtest: rows=%d spread=%.3f", len(df), args.half_spread)
    result = engine.run(df)
    print(result.summary())


if __name__ == "__main__":
    main()
