import argparse
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template


app = Flask(__name__)
DB_PATH = Path("portfolio_history.db")


def query_all(sql: str, params=()):
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


@app.get("/")
def dashboard():
    return render_template("dashboard.html")


@app.get("/api/summary")
def summary():
    rows = query_all(
        """
        SELECT timestamp, total_invested, total_value, total_gain,
               total_percent_gain, currency
        FROM portfolio_snapshots
        ORDER BY timestamp DESC
        LIMIT 1
        """
    )
    return jsonify(rows[0] if rows else {
        "timestamp": None,
        "total_invested": 0,
        "total_value": 0,
        "total_gain": 0,
        "total_percent_gain": 0,
        "currency": "USD",
    })


@app.get("/api/history")
def history():
    rows = query_all(
        """
        SELECT timestamp, total_value, total_gain, total_percent_gain, currency
        FROM portfolio_snapshots
        ORDER BY timestamp ASC
        LIMIT 500
        """
    )
    return jsonify(rows)


@app.get("/api/positions")
def positions():
    latest = query_all(
        """
        SELECT p.symbol, p.amount, p.avg_buy_price, p.current_price,
               p.current_value, p.invested, p.gain, p.percent_gain, p.currency
        FROM position_snapshots p
        JOIN (
            SELECT symbol, MAX(timestamp) AS timestamp
            FROM position_snapshots
            GROUP BY symbol
        ) latest ON latest.symbol = p.symbol AND latest.timestamp = p.timestamp
        ORDER BY p.current_value DESC
        """
    )
    return jsonify(latest)


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "database": str(DB_PATH), "database_exists": DB_PATH.exists()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crypto gains web dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--db", default="portfolio_history.db")
    args = parser.parse_args()
    DB_PATH = Path(args.db)
    app.run(host=args.host, port=args.port, debug=False)
