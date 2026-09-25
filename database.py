import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class PortfolioDatabase:
    def __init__(self, db_path: str = "portfolio_history.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self) -> None:
        """Initialize database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table for tracking price snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT DEFAULT 'usd',
                UNIQUE(timestamp, symbol, currency)
            )
        """)

        # Table for portfolio snapshots (periodic snapshots of entire portfolio)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_invested REAL NOT NULL,
                total_value REAL NOT NULL,
                total_gain REAL NOT NULL,
                total_percent_gain REAL NOT NULL,
                currency TEXT DEFAULT 'usd'
            )
        """)

        # Table for individual position snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                amount REAL NOT NULL,
                avg_buy_price REAL NOT NULL,
                current_price REAL NOT NULL,
                current_value REAL NOT NULL,
                invested REAL NOT NULL,
                gain REAL NOT NULL,
                percent_gain REAL NOT NULL,
                currency TEXT DEFAULT 'usd'
            )
        """)

        conn.commit()
        conn.close()

    def record_price(self, symbol: str, price: float, currency: str = "usd") -> None:
        """Record a single coin price."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO price_history (symbol, price, currency) VALUES (?, ?, ?)",
                (symbol.upper(), price, currency.lower())
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # Ignore duplicate entries within the same second
            pass
        finally:
            conn.close()

    def record_portfolio_snapshot(
        self,
        total_invested: float,
        total_value: float,
        total_gain: float,
        total_percent_gain: float,
        currency: str = "usd"
    ) -> None:
        """Record a full portfolio snapshot."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO portfolio_snapshots (total_invested, total_value, total_gain, total_percent_gain, currency) VALUES (?, ?, ?, ?, ?)",
            (total_invested, total_value, total_gain, total_percent_gain, currency.lower())
        )
        conn.commit()
        conn.close()

    def record_position_snapshot(self, result: Dict, currency: str = "usd") -> None:
        """Record a position snapshot."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO position_snapshots (symbol, amount, avg_buy_price, current_price, current_value, invested, gain, percent_gain, currency) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result["symbol"],
                result["amount"],
                result["avg_buy_price"],
                result["current_price"],
                result["current_value"],
                result["invested"],
                result["gain"],
                result["percent_gain"],
                currency.lower()
            )
        )
        conn.commit()
        conn.close()

    def get_price_history(self, symbol: str, limit: int = 100, currency: str = "usd") -> List[Dict]:
        """Get recent price history for a symbol."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, symbol, price FROM price_history WHERE symbol = ? AND currency = ? ORDER BY timestamp DESC LIMIT ?",
            (symbol.upper(), currency.lower(), limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_portfolio_history(self, limit: int = 100, currency: str = "usd") -> List[Dict]:
        """Get recent portfolio snapshots."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM portfolio_snapshots WHERE currency = ? ORDER BY timestamp DESC LIMIT ?",
            (currency.lower(), limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_position_history(self, symbol: str, limit: int = 100, currency: str = "usd") -> List[Dict]:
        """Get recent position history for a symbol."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM position_snapshots WHERE symbol = ? AND currency = ? ORDER BY timestamp DESC LIMIT ?",
            (symbol.upper(), currency.lower(), limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_price_stats(self, symbol: str, currency: str = "usd") -> Optional[Dict]:
        """Get price statistics for a symbol."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MIN(price) as min_price, MAX(price) as max_price, AVG(price) as avg_price, COUNT(*) as sample_count "
            "FROM price_history WHERE symbol = ? AND currency = ?",
            (symbol.upper(), currency.lower())
        )
        result = cursor.fetchone()
        conn.close()
        if result:
            return {
                "symbol": symbol.upper(),
                "min_price": result[0],
                "max_price": result[1],
                "avg_price": result[2],
                "sample_count": result[3]
            }
        return None

    def get_portfolio_stats(self, currency: str = "usd") -> Optional[Dict]:
        """Get overall portfolio statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MIN(total_value) as min_value, MAX(total_value) as max_value, AVG(total_gain) as avg_gain, COUNT(*) as snapshot_count "
            "FROM portfolio_snapshots WHERE currency = ?",
            (currency.lower(),)
        )
        result = cursor.fetchone()
        conn.close()
        if result:
            return {
                "min_portfolio_value": result[0],
                "max_portfolio_value": result[1],
                "avg_gain": result[2],
                "snapshot_count": result[3]
            }
        return None

    def export_history(self, output_path: str, currency: str = "usd") -> None:
        """Export portfolio history to JSON."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM portfolio_snapshots WHERE currency = ? ORDER BY timestamp",
            (currency.lower(),)
        )
        portfolio_history = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            "SELECT * FROM position_snapshots WHERE currency = ? ORDER BY timestamp",
            (currency.lower(),)
        )
        position_history = [dict(row) for row in cursor.fetchall()]

        conn.close()

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "currency": currency.upper(),
            "portfolio_snapshots": portfolio_history,
            "position_snapshots": position_history
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str)

    def clear_old_data(self, days: int = 30, currency: str = "usd") -> None:
        """Delete data older than specified days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM price_history WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days') AND currency = ?",
            (days, currency.lower())
        )
        cursor.execute(
            "DELETE FROM portfolio_snapshots WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days') AND currency = ?",
            (days, currency.lower())
        )
        cursor.execute(
            "DELETE FROM position_snapshots WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days') AND currency = ?",
            (days, currency.lower())
        )
        conn.commit()
        conn.close()
