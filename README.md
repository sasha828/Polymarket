# Polymarket Trading Bot

Automated limit-order trading bot for [Polymarket](https://polymarket.com) prediction markets, powered by the [py-clob-client](https://github.com/Polymarket/py-clob-client) SDK.

Three strategies targeting real edges in prediction markets — no technical analysis indicators.

## Project Structure

```
├── strategies/                  # Trading strategies
│   ├── base.py                  # Base types: OrderBookSnapshot, MarketContext, OrderRequest
│   ├── arb_strategy.py          # Yes/No arbitrage (risk-free spread capture)
│   ├── market_maker_strategy.py # Two-sided quoting with inventory skew
│   └── scanner_strategy.py      # Bond strategy + longshot fading
├── backtesting/                 # Backtesting framework
│   └── engine.py                # Backtest engine with limit order fill simulation
├── bot/                         # Live trading components
│   ├── trader.py                # Multi-token trading loop with order management
│   └── risk_manager.py          # Position limits, daily loss caps, order gating
├── deploy/                      # Entry points
│   ├── run_live.py              # Live trading (arb, mm, scanner)
│   ├── run_scanner.py           # Multi-market scanner with dry-run mode
│   └── run_backtest.py          # Backtesting entry point
├── .env.example                 # Environment variable template
├── requirements.txt             # Python dependencies
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

### 1. Yes/No Arbitrage (`arb`)

**Edge**: YES + NO tokens must sum to $1.00. When `best_ask(YES) + best_ask(NO) < $1.00`, buy both sides for risk-free profit.

- Documented profit: 1.5-3% per trade
- $40M in arb profits extracted from Polymarket in 2024-2025
- Zero directional risk when both legs fill

```bash
python -m deploy.run_live --strategy arb \
  --yes-token <YES_TOKEN_ID> \
  --no-token <NO_TOKEN_ID> \
  --order-size 20 \
  --poll-interval 2
```

### 2. Market Maker (`mm`)

**Edge**: Post two-sided limit orders to capture bid-ask spread plus Polymarket liquidity rewards.

- Inventory skew: automatically adjusts quotes to stay flat
- Best for markets with $50K+ daily volume and 30+ day duration
- Returns scale with capital

```bash
python -m deploy.run_live --strategy mm \
  --token-id <TOKEN_ID> \
  --order-size 10 \
  --poll-interval 5
```

### 3. Market Scanner (`scanner`)

**Edge**: Exploits systematic mispricings — near-certain outcomes (>92c) are underpriced, longshots (<8c) are overpriced by fan bias.

- "Bond strategy": buy near-certain outcomes at a discount, collect $1 at resolution
- Expected return: 3-8% per position
- Supports dry-run mode for testing

```bash
# Scan all markets (dry-run first):
python -m deploy.run_scanner --dry-run --min-price 0.92 --max-price 0.97

# Live scanning:
python -m deploy.run_scanner --order-size 15 --scan-interval 300

# Single-token scanner:
python -m deploy.run_live --strategy scanner --token-id <TOKEN_ID>
```

## Risk Management

| Limit | Default | Description |
|-------|---------|-------------|
| Max position size | $100 | Caps notional exposure per token |
| Daily loss limit | $50 | Halts all trading if exceeded |
| Open order limit | 20 | Prevents excessive concurrent orders |
| Price bounds | [0.01, 0.99] | Enforces Polymarket valid range |

Configure via `.env`.

## Architecture

All strategies implement `BaseStrategy.generate_orders(ctx: MarketContext) -> list[OrderRequest]`:

- **MarketContext** provides order books, token IDs, and current inventory
- Strategies return zero or more `OrderRequest` objects (limit orders only)
- The `Trader` loop handles order submission, cancellation, and requoting
- The `RiskManager` gates every order before submission

## Adding a New Strategy

1. Create `strategies/my_strategy.py`, subclass `BaseStrategy`
2. Implement `generate_orders(ctx) -> list[OrderRequest]`
3. Register in `deploy/run_live.py`
