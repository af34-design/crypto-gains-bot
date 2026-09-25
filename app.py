import argparse
import json
import time
from datetime import datetime
from typing import Dict, List

import requests


COIN_ID_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "XRP": "ripple",
    "BNB": "binancecoin",
    "MATIC": "matic-network",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "USDC": "usd-coin",
    "USDT": "tether",
}


def load_portfolio(path: str) -> List[Dict[str, float]]:
    with open(path, "r", encoding="utf-8") as file:
        portfolio = json.load(file)

    if not isinstance(portfolio, list):
        raise ValueError("Portfolio file must contain a JSON list of holdings.")

    return portfolio


def fetch_live_prices(symbols: List[str], currency: str = "usd") -> Dict[str, float]:
    unique_symbols = sorted({symbol.upper() for symbol in symbols if symbol})
    coin_ids = [COIN_ID_MAP.get(symbol, symbol.lower()) for symbol in unique_symbols]

    if not coin_ids:
        return {}

    response = requests.get(
        "https://api.coingecko.com/api/v3/coins/markets",
        params={
            "vs_currency": currency,
            "ids": ",".join(coin_ids),
            "sparkline": "false",
        },
        timeout=20,
    )
    response.raise_for_status()

    market_data = response.json()
    prices: Dict[str, float] = {}

    for item in market_data:
        symbol = item.get("symbol", "").upper()
        if symbol:
            prices[symbol] = float(item.get("current_price", 0.0))

    return prices


def compute_gain(position: Dict[str, float], price_map: Dict[str, float], currency: str) -> Dict[str, float]:
    symbol = str(position.get("symbol", "")).upper()
    amount = float(position.get("amount", 0.0))
    avg_buy_price = float(position.get("avg_buy_price", 0.0))
    current_price = float(price_map.get(symbol, 0.0))

    current_value = amount * current_price
    invested = amount * avg_buy_price
    gain = current_value - invested
    percent_gain = ((current_price / avg_buy_price) - 1) * 100 if avg_buy_price else 0.0

    return {
        "symbol": symbol,
        "amount": amount,
        "avg_buy_price": avg_buy_price,
        "current_price": current_price,
        "current_value": current_value,
        "invested": invested,
        "gain": gain,
        "percent_gain": percent_gain,
        "currency": currency.upper(),
    }


def print_header() -> None:
    print("\n" + "=" * 95)
    print(f"Crypto Gains Summary — Updated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 95)
    print(f"{'Symbol':<8} {'Amount':>12} {'Avg Buy':>12} {'Current':>12} {'Value':>14} {'P/L':>14} {'%':>10}")
    print("-" * 95)


def print_summary(results: List[Dict[str, float]]) -> None:
    total_invested = sum(item["invested"] for item in results)
    total_value = sum(item["current_value"] for item in results)
    total_gain = total_value - total_invested
    total_percent = ((total_value / total_invested) - 1) * 100 if total_invested else 0.0

    for item in results:
        color = "\033[92m" if item["gain"] >= 0 else "\033[91m"
        reset = "\033[0m"
        print(
            f"{item['symbol']:<8} "
            f"{item['amount']:>12.4f} "
            f"{item['avg_buy_price']:>12.2f} "
            f"{item['current_price']:>12.2f} "
            f"{item['current_value']:>14.2f} "
            f"{color}{item['gain']:>14.2f}{reset} "
            f"{color}{item['percent_gain']:>9.2f}%{reset}"
        )

    print("-" * 95)
    color = "\033[92m" if total_gain >= 0 else "\033[91m"
    reset = "\033[0m"
    print(
        f"{'TOTAL':<8} "
        f"{'':>12} "
        f"{'':>12} "
        f"{'':>12} "
        f"{total_value:>14.2f} "
        f"{color}{total_gain:>14.2f}{reset} "
        f"{color}{total_percent:>9.2f}%{reset}"
    )
    print("=" * 95)
    return total_invested, total_value, total_gain, total_percent


def watch_portfolio(portfolio_path: str, currency: str = "usd", refresh_interval: int = 60) -> None:
    """Continuously monitor portfolio with real-time price updates."""
    portfolio = load_portfolio(portfolio_path)
    symbols = [str(item.get("symbol", "")) for item in portfolio]

    print(f"\n🚀 Starting real-time crypto portfolio monitor (refresh every {refresh_interval}s)")
    print(f"Portfolio: {portfolio_path}")
    print(f"Currency: {currency.upper()}")

    previous_total_gain = None

    try:
        while True:
            try:
                price_map = fetch_live_prices(symbols, currency)
                results = [compute_gain(item, price_map, currency) for item in portfolio]

                print_header()
                total_invested, total_value, total_gain, total_percent = print_summary(results)

                if previous_total_gain is not None:
                    change = total_gain - previous_total_gain
                    if abs(change) > 1:
                        direction = "📈 UP" if change > 0 else "📉 DOWN"
                        print(f"\n{direction} Portfolio changed by ${abs(change):.2f}")

                previous_total_gain = total_gain
                print(f"\n⏳ Next update in {refresh_interval}s... (Press Ctrl+C to stop)")
                time.sleep(refresh_interval)

            except requests.exceptions.RequestException as e:
                print(f"❌ Error fetching prices: {e}")
                print(f"⏳ Retrying in {refresh_interval}s...")
                time.sleep(refresh_interval)

    except KeyboardInterrupt:
        print("\n\n✋ Monitoring stopped. Goodbye!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-time crypto portfolio gain tracker.")
    parser.add_argument("--portfolio", required=True, help="Path to a JSON portfolio file")
    parser.add_argument("--currency", default="usd", help="Currency to query prices in (default: usd)")
    parser.add_argument("--refresh", type=int, default=60, help="Refresh interval in seconds (default: 60)")
    parser.add_argument("--watch", action="store_true", help="Enable real-time monitoring mode")

    args = parser.parse_args()

    if args.watch:
        watch_portfolio(args.portfolio, args.currency, args.refresh)
    else:
        portfolio = load_portfolio(args.portfolio)
        symbols = [str(item.get("symbol", "")) for item in portfolio]
        price_map = fetch_live_prices(symbols, args.currency)
        results = [compute_gain(item, price_map, args.currency) for item in portfolio]

        print_header()
        print_summary(results)


if __name__ == "__main__":
    main()
