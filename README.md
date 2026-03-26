# Polymarket Trading Bot

Automated limit-order trading bot for [Polymarket](https://polymarket.com) prediction markets, powered by the [py-clob-client](https://github.com/Polymarket/py-clob-client) SDK.

## Project Structure

```
├── strategies/          # Trading strategy implementations
│   ├── base.py          # Abstract base strategy + Signal/OrderRequest types
│   ├── macd_strategy.py # MACD crossover strategy
│   ├── rsi_strategy.py  # RSI mean-reversion strategy
│   └── cvd_strategy.py  # Cumulative Volume Delta divergence strategy
├── backtesting/         # Backtesting framework
│   └── engine.py        # Backtest engine with fill simulation
├── bot/                 # Live trading components
│   ├── trader.py        # Main trading loop + CLOB order submission
│   └── risk_manager.py  # Position limits, daily loss caps, order gating
├── deploy/              # Entry points
│   ├── run_live.py      # Live trading entry point
│   └── run_backtest.py  # Backtesting entry point
├── .env.example         # Environment variable template
├── requirements.txt     # Python dependencies
└── .gitignore
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Polymarket API credentials and private key
```

## Strategies

| Strategy | Signal Logic | Best For |
|----------|-------------|----------|
| **MACD** | Buy on MACD/signal bullish crossover, sell on bearish crossover | Trending markets |
| **RSI** | Buy when RSI < 30 (oversold), sell when RSI > 70 (overbought) | Mean-reverting markets |
| **CVD** | Buy on bullish volume/price divergence, sell on bearish divergence | Volume-driven markets |

All strategies place **limit orders only** — no market orders are ever used.

## Usage

### Live Trading

```bash
python -m deploy.run_live --token-id <TOKEN_ID> --strategy macd --order-size 10
```

### Backtesting

Prepare a CSV file with columns `timestamp` and `price` (plus `buy_volume` and `sell_volume` for the CVD strategy):

```bash
python -m deploy.run_backtest --strategy rsi --data historical_prices.csv --balance 1000
```

## Risk Management

The risk manager enforces:
- **Max position size** — caps notional exposure per token
- **Daily loss limit** — halts trading if cumulative daily loss exceeds threshold
- **Open order limit** — prevents excessive concurrent orders
- **Price bounds** — ensures limit prices stay within Polymarket's [0.01, 0.99] range

Configure limits via environment variables in `.env`.

## Adding a New Strategy

1. Create a new file in `strategies/`
2. Subclass `BaseStrategy` and implement `generate_signal()` and `get_limit_price()`
3. Register the strategy in `deploy/run_live.py` and `deploy/run_backtest.py`
