import argparse
import json
import time
from datetime import datetime
from typing import Dict, List

import requests

from database import PortfolioDatabase


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

# News APIs for crypto market data
NEWS_SOURCES = {
    "cryptonews": "https://cryptonews-api.com/api/v1",
    "coingecko_events": "https://api.coingecko.com/api/v3/events",
    "newsapi": "https://newsapi.org/v2"
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
            "market_cap_rank": "true",
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


def fetch_market_sentiment() -> Dict[str, any]:
    """Fetch overall crypto market sentiment and fear/greed index."""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/global",
            timeout=20
        )
        response.raise_for_status()
        data = response.json()["data"]
        
        return {
            "btc_dominance": data.get("btc_market_cap_percentage", {}).get("btc"),
            "eth_dominance": data.get("btc_market_cap_percentage", {}).get("eth"),
            "market_cap_change_24h": data.get("market_cap_change_percentage_24h_usd"),
            "total_market_cap": data.get("total_market_cap", {}).get("usd")
        }
    except Exception as e:
        print(f"⚠️ Could not fetch market sentiment: {e}")
        return {}


def fetch_crypto_news(limit: int = 5) -> List[Dict]:
    """Fetch recent crypto news that affects prices."""
    try:
        # Using CoinGecko's trending data (no API key needed)
        response = requests.get(
            "https://api.coingecko.com/api/v3/search/trending",
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
        
        trending = []
        for item in data.get("coins", [])[:limit]:
            coin = item.get("item", {})
            trending.append({
                "name": coin.get("name"),
                "symbol": coin.get("symbol"),
                "market_cap_rank": coin.get("market_cap_rank"),
                "score": item.get("score", "N/A")
            })
        
        return trending
    except Exception as e:
        print(f"⚠️ Could not fetch trending coins: {e}")
        return []


def fetch_coin_updates(symbols: List[str]) -> Dict[str, Dict]:
    """Fetch detailed coin updates including market data and changes."""
    try:
        coin_ids = [COIN_ID_MAP.get(symbol.upper(), symbol.lower()) for symbol in symbols]
        response = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": ",".join(coin_ids),
                "order": "market_cap_desc",
                "per_page": 250,
                "sparkline": "false",
                "price_change_percentage": "1h,24h,7d"
            },
            timeout=20
        )
        response.raise_for_status()
        
        updates = {}
        for item in response.json():
            symbol = item.get("symbol", "").upper()
            updates[symbol] = {
                "price": item.get("current_price"),
                "market_cap": item.get("market_cap"),
                "volume_24h": item.get("total_volume"),
                "price_change_1h": item.get("price_change_percentage_1h_in_currency"),
                "price_change_24h": item.get("price_change_percentage_24h"),
                "price_change_7d": item.get("price_change_percentage_7d_in_currency"),
                "ath": item.get("ath"),
                "atl": item.get("atl")
            }
        
        return updates
    except Exception as e:
        print(f"⚠️ Could not fetch coin updates: {e}")
        return {}


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
    print("\n" + "=" * 110)
    print(f"Crypto Gains Summary — Updated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 110)
    print(f"{'Symbol':<8} {'Amount':>12} {'Avg Buy':>12} {'Current':>12} {'Value':>14} {'P/L':>14} {'1h%':>8} {'24h%':>8}")
    print("-" * 110)


def print_summary(results: List[Dict[str, float]], updates: Dict = None) -> tuple:
    total_invested = sum(item["invested"] for item in results)
    total_value = sum(item["current_value"] for item in results)
    total_gain = total_value - total_invested
    total_percent = ((total_value / total_invested) - 1) * 100 if total_invested else 0.0

    for item in results:
        color = "\033[92m" if item["gain"] >= 0 else "\033[91m"
        reset = "\033[0m"
        
        # Get price changes if available
        update = updates.get(item["symbol"], {}) if updates else {}
        change_1h = update.get("price_change_1h", 0) or 0
        change_24h = update.get("price_change_24h", 0) or 0
        
        print(
            f"{item['symbol']:<8} "
            f"{item['amount']:>12.4f} "
            f"{item['avg_buy_price']:>12.2f} "
            f"{item['current_price']:>12.2f} "
            f"{item['current_value']:>14.2f} "
            f"{color}{item['gain']:>14.2f}{reset} "
            f"{change_1h:>7.2f}% "
            f"{change_24h:>7.2f}%"
        )

    print("-" * 110)
    color = "\033[92m" if total_gain >= 0 else "\033[91m"
    reset = "\033[0m"
    print(
        f"{'TOTAL':<8} "
        f"{'':>12} "
        f"{'':>12} "
        f"{'':>12} "
        f"{total_value:>14.2f} "
        f"{color}{total_gain:>14.2f}{reset} "
        f"{'':>8} "
        f"{'':>8}"
    )
    print("=" * 110)
    return total_invested, total_value, total_gain, total_percent


def print_market_sentiment(sentiment: Dict) -> None:
    """Display market sentiment and trends."""
    if not sentiment:
        return
    
    print("\n📊 Market Sentiment:")
    if sentiment.get("btc_dominance"):
        print(f"  • BTC Dominance: {sentiment['btc_dominance']:.2f}%")
    if sentiment.get("market_cap_change_24h"):
        change = sentiment['market_cap_change_24h']
        color = "\033[92m" if change >= 0 else "\033[91m"
        reset = "\033[0m"
        print(f"  • Market Cap Change (24h): {color}{change:.2f}%{reset}")
    if sentiment.get("total_market_cap"):
        print(f"  • Total Market Cap: ${sentiment['total_market_cap']/1e12:.2f}T")


def print_trending(trending: List[Dict]) -> None:
    """Display trending coins."""
    if not trending:
        return
    
    print("\n🔥 Trending Coins:")
    for coin in trending[:5]:
        print(f"  • {coin['name']} ({coin['symbol'].upper()}) - Rank: {coin['market_cap_rank']}")


def watch_portfolio(portfolio_path: str, currency: str = "usd", refresh_interval: int = 60, db: PortfolioDatabase = None) -> None:
    """Continuously monitor portfolio with real-time price updates and market news."""
    portfolio = load_portfolio(portfolio_path)
    symbols = [str(item.get("symbol", "")) for item in portfolio]

    print(f"\n🚀 Starting real-time crypto portfolio monitor (refresh every {refresh_interval}s)")
    print(f"📰 Tracking market sentiment and news")
    print(f"Portfolio: {portfolio_path}")
    print(f"Currency: {currency.upper()}")

    previous_total_gain = None
    news_fetch_counter = 0

    try:
        while True:
            try:
                # Fetch live prices
                price_map = fetch_live_prices(symbols, currency)
                
                # Fetch detailed updates (price changes, volume, etc.)
                updates = fetch_coin_updates(symbols)
                
                # Fetch market sentiment every 5 iterations (to reduce API calls)
                sentiment = {}
                trending = []
                news_fetch_counter += 1
                if news_fetch_counter % 5 == 0:
                    sentiment = fetch_market_sentiment()
                    trending = fetch_crypto_news()
                
                results = [compute_gain(item, price_map, currency) for item in portfolio]

                print_header()
                total_invested, total_value, total_gain, total_percent = print_summary(results, updates)

                # Print market sentiment and trending
                if sentiment:
                    print_market_sentiment(sentiment)
                if trending:
                    print_trending(trending)

                # Record to database if provided
                if db:
                    db.record_portfolio_snapshot(total_invested, total_value, total_gain, total_percent, currency)
                    for result in results:
                        db.record_position_snapshot(result, currency)

                if previous_total_gain is not None:
                    change = total_gain - previous_total_gain
                    if abs(change) > 1:
                        direction = "📈 UP" if change > 0 else "📉 DOWN"
                        print(f"\n{direction} Portfolio changed by ${abs(change):.2f}")

                previous_total_gain = total_gain

                print(f"\n⏳ Next update in {refresh_interval}s... (Press Ctrl+C to stop)")
                time.sleep(refresh_interval)

            except requests.exceptions.RequestException as e:
                print(f"❌ Error fetching data: {e}")
                print(f"⏳ Retrying in {refresh_interval}s...")
                time.sleep(refresh_interval)

    except KeyboardInterrupt:
        print("\n\n✋ Monitoring stopped. Goodbye!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Real-time crypto portfolio gain tracker with market news.")
    parser.add_argument("--portfolio", required=True, help="Path to a JSON portfolio file")
    parser.add_argument("--currency", default="usd", help="Currency to query prices in (default: usd)")
    parser.add_argument("--refresh", type=int, default=60, help="Refresh interval in seconds (default: 60)")
    parser.add_argument("--watch", action="store_true", help="Enable real-time monitoring mode")
    parser.add_argument("--db", action="store_true", help="Enable database tracking")

    args = parser.parse_args()

    db = PortfolioDatabase() if args.db else None

    if args.watch:
        watch_portfolio(args.portfolio, args.currency, args.refresh, db)
    else:
        portfolio = load_portfolio(args.portfolio)
        symbols = [str(item.get("symbol", "")) for item in portfolio]
        price_map = fetch_live_prices(symbols, args.currency)
        updates = fetch_coin_updates(symbols)
        results = [compute_gain(item, price_map, args.currency) for item in portfolio]

        print_header()
        print_summary(results, updates)
        
        sentiment = fetch_market_sentiment()
        print_market_sentiment(sentiment)
        
        trending = fetch_crypto_news()
        print_trending(trending)


if __name__ == "__main__":
    main()
