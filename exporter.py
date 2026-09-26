import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import sqlite3


class PortfolioExporter:
    def __init__(self, db_path: str = "portfolio_history.db"):
        self.db_path = db_path

    def export_csv(self, output_path: str, currency: str = "usd") -> bool:
        """Export portfolio snapshots to CSV."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM portfolio_snapshots WHERE currency = ? ORDER BY timestamp DESC",
                (currency.lower(),)
            )
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                print("❌ No portfolio data to export")
                return False

            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = ["timestamp", "total_invested", "total_value", "total_gain", "total_percent_gain", "currency"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))

            print(f"✅ Exported {len(rows)} portfolio snapshots to {output_path}")
            return True
        except Exception as e:
            print(f"❌ CSV export failed: {e}")
            return False

    def export_json(self, output_path: str, currency: str = "usd") -> bool:
        """Export portfolio history to JSON."""
        try:
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
                "position_snapshots": position_history,
                "summary": {
                    "total_snapshots": len(portfolio_history),
                    "date_range": {
                        "start": portfolio_history[0]["timestamp"] if portfolio_history else None,
                        "end": portfolio_history[-1]["timestamp"] if portfolio_history else None,
                    }
                }
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, default=str)

            print(f"✅ Exported portfolio history to {output_path}")
            return True
        except Exception as e:
            print(f"❌ JSON export failed: {e}")
            return False

    def export_position_csv(self, output_path: str, currency: str = "usd") -> bool:
        """Export current positions to CSV."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT p.symbol, p.amount, p.avg_buy_price, p.current_price,
                       p.current_value, p.invested, p.gain, p.percent_gain, p.currency
                FROM position_snapshots p
                JOIN (
                    SELECT symbol, MAX(timestamp) AS timestamp
                    FROM position_snapshots
                    WHERE currency = ?
                    GROUP BY symbol
                ) latest ON latest.symbol = p.symbol AND latest.timestamp = p.timestamp
                ORDER BY p.current_value DESC
                """,
                (currency.lower(),)
            )
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                print("❌ No position data to export")
                return False

            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = ["symbol", "amount", "avg_buy_price", "current_price", "current_value", "invested", "gain", "percent_gain", "currency"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))

            print(f"✅ Exported {len(rows)} positions to {output_path}")
            return True
        except Exception as e:
            print(f"❌ Position CSV export failed: {e}")
            return False

    def generate_report(self, output_path: str, currency: str = "usd") -> bool:
        """Generate a text summary report."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get latest snapshot
            cursor.execute(
                "SELECT * FROM portfolio_snapshots WHERE currency = ? ORDER BY timestamp DESC LIMIT 1",
                (currency.lower(),)
            )
            latest = cursor.fetchone()

            # Get position data
            cursor.execute(
                """
                SELECT p.symbol, p.amount, p.avg_buy_price, p.current_price,
                       p.current_value, p.invested, p.gain, p.percent_gain
                FROM position_snapshots p
                JOIN (
                    SELECT symbol, MAX(timestamp) AS timestamp
                    FROM position_snapshots
                    WHERE currency = ?
                    GROUP BY symbol
                ) latest ON latest.symbol = p.symbol AND latest.timestamp = p.timestamp
                ORDER BY p.current_value DESC
                """,
                (currency.lower(),)
            )
            positions = cursor.fetchall()
            conn.close()

            report = []
            report.append("=" * 80)
            report.append("CRYPTO PORTFOLIO REPORT")
            report.append("=" * 80)
            report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"Currency: {currency.upper()}")

            if latest:
                report.append(f"\nPORTFOLIO SUMMARY:")
                report.append(f"  Total Invested: ${latest['total_invested']:,.2f}")
                report.append(f"  Portfolio Value: ${latest['total_value']:,.2f}")
                report.append(f"  Gain/Loss: ${latest['total_gain']:,.2f}")
                report.append(f"  Return: {latest['total_percent_gain']:.2f}%")

            if positions:
                report.append(f"\nPOSITIONS ({len(positions)} assets):")
                report.append("-" * 80)
                for pos in positions:
                    report.append(f"\n{pos['symbol']}:")
                    report.append(f"  Amount: {pos['amount']:.6f}")
                    report.append(f"  Avg Buy Price: ${pos['avg_buy_price']:,.2f}")
                    report.append(f"  Current Price: ${pos['current_price']:,.2f}")
                    report.append(f"  Value: ${pos['current_value']:,.2f}")
                    report.append(f"  P/L: ${pos['gain']:,.2f} ({pos['percent_gain']:.2f}%)")

            report.append("\n" + "=" * 80)
            report_text = "\n".join(report)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report_text)

            print(f"✅ Report generated: {output_path}")
            return True
        except Exception as e:
            print(f"❌ Report generation failed: {e}")
            return False
