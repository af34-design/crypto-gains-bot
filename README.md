# Crypto Gains Bot

A simple Python bot that reads your crypto portfolio and calculates current gains/losses using live market prices from CoinGecko.

## Features
- Load a portfolio from a JSON file
- Fetch live prices for supported coins
- Compute current value, total invested, and profit/loss
- Print a simple summary table

## Supported coins
The bot currently supports the most common cryptocurrencies by symbol, including:
- BTC
- ETH
- SOL
- ADA
- DOGE
- XRP
- BNB
- MATIC
- AVAX
- LINK

## Setup

1. Create a virtual environment:
   python -m venv .venv
   source .venv/bin/activate

2. Install requirements:
   pip install -r requirements.txt

3. Edit `portfolio.json` with your holdings.

4. Run the bot:
   python app.py --portfolio portfolio.json --currency usd

## Example portfolio format

```json
[
  {"symbol": "BTC", "amount": 0.5, "avg_buy_price": 65000},
  {"symbol": "ETH", "amount": 3.0, "avg_buy_price": 3100},
  {"symbol": "SOL", "amount": 15.0, "avg_buy_price": 90}
]
```

## Notes
- The bot uses the public CoinGecko API.
- Internet access is required for price updates.
- For a production bot, add database storage, scheduled checks, and notifications.
