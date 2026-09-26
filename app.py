import argparse
import json
import time
from datetime import datetime
from typing import Dict, List
from pathlib import Path

import requests

from database import PortfolioDatabase
from alerts import AlertConfig, AlertSystem
from exporter import PortfolioExporter


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


class CryptoGainsTracker:
    def __init__(self, config_path: str = "tracker_config.json"):
        self.config = self.load_config(config_path)
        self.db = PortfolioDatabase(self.config.get("database_path", "portfolio_history.db"))
        self.alerts = AlertSystem(AlertConfig(self.config.get("alerts_config", "alerts_config.json")))
        self.exporter = PortfolioExporter(self.config.get("database_path", "portfolio_history.db"))

    def load_config(self, path: str) -> Dict:
        """Load or create configuration file."""
        config_path = Path(path)
        if config_path.exists():
            with open(config_path, "r") as f:
                return json.load(f)
        
        default_config = {
            "portfolio_path": "portfolio.json",
            "database_path": "portfolio_history.db",
            "alerts_config": "alerts_config.json",
            "refresh_interval": 60,
            "currency": "usd",
            "alerts_enabled": False,
            "export_on_exit": False
        }
        
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=2)
        
        print(f"✅ Created default config at {path}")
        return default_config

    def load_portfolio(self, path: str) -> List[Dict[str, float]]:
        """Load portfolio from JSON file."""
        with open(path, "r", encoding="utf-8") as file:
            portfolio = json.load(file)

        if not isinstance(portfolio, list):
            raise ValueError("Portfolio file must contain a JSON list of holdings.")

        return portfolio

    def fetch_live_prices(self, symbols: List[str], currency: str = "usd") -> Dict[str, float]:
        """Fetch live prices from CoinGecko."""
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
                "price_change_percentage": "1h,24h,7d"
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

    def fetch_market_sentiment(self) -> Dict:
        """Fetch overall market sentiment."""
        try:
            response = requests.get("https://api.coingecko.com/api/v3/global", timeout=20)
            response.raise_for_status()
            data = response.json()["data"]
            
            return {
                "btc_dominance": data.get("btc_market_cap_percentage", {}).get("btc"),
                "market_cap_change_24h": data.get("market_cap_change_percentage_24h_usd"),
                "total_market_cap": data.get("total_market_cap", {}).get("usd")
            }
        except Exception as e:
            print(f"⚠️ Could not fetch market sentiment: {e}")
            return {}

    def fetch_crypto_news(self, limit: int = 5) -> List[Dict]:
        """Fetch trending coins."""
        try:
            response = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=20)
            response.raise_for_status()
            data = response.json()
            
            trending = []
            for item in data.get("coins", [])[:limit]:
                coin = item.get("item", {})
                trending.append({
                    "name": coin.get("name"),
                    "symbol": coin.get("symbol"),
                    "market_cap_rank": coin.get("market_cap_rank"),
                })
            
            return trending
        except Exception as e:
            print(f"⚠️ Could not fetch trending coins: {e}")
            return []

    def compute_gain(self, position: Dict[str, float], price_map: Dict[str, float], currency: str) -> Dict[str, float]:
        """Calculate gain/loss for a position."""
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

    def print_header(self) -> None:
        """Print dashboard header."""
        print("\n" + "=" * 110)
        print(f"Crypto Gains Summary — Updated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 110)
        print(f"{'Symbol':<8} {'Amount':>12} {'Avg Buy':>12} {'Current':>12} {'Value':>14} {'P/L':>14} {'1h%':>8} {'24h%':>8}")
        print("-" * 110)

    def print_summary(self, results: List[Dict[str, float]], updates: Dict = None) -> tuple:
        """Print portfolio summary."""
        total_invested = sum(item["invested"] for item in results)
        total_value = sum(item["current_value"] for item in results)
        total_gain = total_value - total_invested
        total_percent = ((total_value / total_invested) - 1) * 100 if total_invested else 0.0

        for item in results:
            color = "\033[92m" if item["gain"] >= 0 else "\033[91m"
            reset = "\033[0m"
            
            update = updates.get(item["symbol"], {}) if updates else {}
            change_1h = update.get("price_change_percentage_1h_in_currency", 0) or 0
            change_24h = update.get("price_change_percentage_24h", 0) or 0
            
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

    def print_market_sentiment(self, sentiment: Dict) -> None:
        """Print market sentiment."""
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

    def print_trending(self, trending: List[Dict]) -> None:
        """Print trending coins."""
        if not trending:
            return
        
        print("\n🔥 Trending Coins:")
        for coin in trending[:5]:
            print(f"  • {coin['name']} ({coin['symbol'].upper()})")

    def watch_portfolio(self) -> None:
        """Main monitoring loop."""
        portfolio_path = self.config.get("portfolio_path", "portfolio.json")
        refresh_interval = self.config.get("refresh_interval", 60)
        currency = self.config.get("currency", "usd")
        
        portfolio = self.load_portfolio(portfolio_path)
        symbols = [str(item.get("symbol", "")) for item in portfolio]

        print(f"\n🚀 Starting real-time crypto portfolio monitor")
        print(f"📰 Tracking market sentiment and news")
        print(f"Portfolio: {portfolio_path}")
        print(f"Currency: {currency.upper()}")
        print(f"Database: {self.config.get('database_path', 'portfolio_history.db')}")

        previous_total_gain = None
        news_fetch_counter = 0

        try:
            while True:
                try:
                    # Fetch prices and updates
                    price_map = self.fetch_live_prices(symbols, currency)
                    response = requests.get(
                        "https://api.coingecko.com/api/v3/coins/markets",
                        params={
                            "vs_currency": currency,
                            "ids": ",".join([COIN_ID_MAP.get(s.upper(), s.lower()) for s in symbols]),
                            "order": "market_cap_desc",
                            "sparkline": "false",
                            "price_change_percentage": "1h,24h,7d"
                        },
                        timeout=20
                    )
                    updates = {item.get("symbol", "").upper(): item for item in response.json()}
                    
                    # Fetch market data every 5 iterations
                    sentiment = {}
                    trending = []
                    news_fetch_counter += 1
                    if news_fetch_counter % 5 == 0:
                        sentiment = self.fetch_market_sentiment()
                        trending = self.fetch_crypto_news()
                    
                    results = [self.compute_gain(item, price_map, currency) for item in portfolio]

                    self.print_header()
                    total_invested, total_value, total_gain, total_percent = self.print_summary(results, updates)

                    if sentiment:
                        self.print_market_sentiment(sentiment)
                    if trending:
                        self.print_trending(trending)

                    # Record to database
                    self.db.record_portfolio_snapshot(total_invested, total_value, total_gain, total_percent, currency)
                    for result in results:
                        self.db.record_position_snapshot(result, currency)

                    # Check alerts
                    if self.config.get("alerts_enabled"):
                        self.alerts.config.config["alerts"].check_price_alerts(price_map)
                        if previous_total_gain is not None:
                            self.alerts.config.config["alerts"].check_profit_loss_alert(total_gain, previous_total_gain)

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
            print("\n\n✋ Monitoring stopped.")
            
            if self.config.get("export_on_exit"):
                print("📁 Exporting portfolio history...")
                self.exporter.export_json(f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", currency)
                self.exporter.export_position_csv(f"positions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", currency)

    def run_once(self) -> None:
        """Run tracker once and display results."""
        portfolio_path = self.config.get("portfolio_path", "portfolio.json")
        currency = self.config.get("currency", "usd")
        
        portfolio = self.load_portfolio(portfolio_path)
        symbols = [str(item.get("symbol", "")) for item in portfolio]
        price_map = self.fetch_live_prices(symbols, currency)
        
        response = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": currency,
                "ids": ",".join([COIN_ID_MAP.get(s.upper(), s.lower()) for s in symbols]),
                "sparkline": "false",
                "price_change_percentage": "1h,24h,7d"
            },
            timeout=20
        )
        updates = {item.get("symbol", "").upper(): item for item in response.json()}
        
        results = [self.compute_gain(item, price_map, currency) for item in portfolio]

        self.print_header()
        self.print_summary(results, updates)
        
        sentiment = self.fetch_market_sentiment()
        self.print_market_sentiment(sentiment)
        
        trending = self.fetch_crypto_news()
        self.print_trending(trending)


def main() -> None:
    parser = argparse.ArgumentParser(description="Production crypto portfolio gains tracker with alerts and exports.")
    parser.add_argument("--config", default="tracker_config.json", help="Path to config file")
    parser.add_argument("--portfolio", help="Override portfolio path")
    parser.add_argument("--currency", help="Override currency")
    parser.add_argument("--watch", action="store_true", help="Enable continuous monitoring")
    parser.add_argument("--refresh", type=int, help="Override refresh interval in seconds")
    parser.add_argument("--alerts", action="store_true", help="Enable price and P/L alerts")
    parser.add_argument("--export-on-exit", action="store_true", help="Export data when stopping")
    
    args = parser.parse_args()

    tracker = CryptoGainsTracker(args.config)
    
    # Override config with CLI arguments
    if args.portfolio:
        tracker.config["portfolio_path"] = args.portfolio
    if args.currency:
        tracker.config["currency"] = args.currency
    if args.refresh:
        tracker.config["refresh_interval"] = args.refresh
    if args.alerts:
        tracker.config["alerts_enabled"] = True
    if args.export_on_exit:
        tracker.config["export_on_exit"] = True

    if args.watch:
        tracker.watch_portfolio()
    else:
        tracker.run_once()


if __name__ == "__main__":
    main()
