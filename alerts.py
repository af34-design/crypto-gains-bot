import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
import json
from pathlib import Path


class AlertConfig:
    def __init__(self, config_path: str = "alerts_config.json"):
        self.config_path = Path(config_path)
        self.config = self.load_config()

    def load_config(self) -> Dict:
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                return json.load(f)
        return {
            "email": {"enabled": False, "smtp_server": "", "sender_email": "", "password": "", "recipients": []},
            "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
            "discord": {"enabled": False, "webhook_url": ""},
            "price_alerts": [],
            "profit_loss_threshold": 100,
        }

    def save_config(self) -> None:
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)


class AlertSystem:
    def __init__(self, config: AlertConfig):
        self.config = config

    def send_email_alert(self, subject: str, message: str) -> bool:
        """Send email alert."""
        if not self.config.config["email"]["enabled"]:
            return False

        try:
            email_config = self.config.config["email"]
            msg = MIMEMultipart()
            msg["From"] = email_config["sender_email"]
            msg["To"] = ", ".join(email_config["recipients"])
            msg["Subject"] = subject

            msg.attach(MIMEText(message, "plain"))

            with smtplib.SMTP_SSL(email_config["smtp_server"], 465) as server:
                server.login(email_config["sender_email"], email_config["password"])
                server.send_message(msg)
            print(f"✉️ Email alert sent: {subject}")
            return True
        except Exception as e:
            print(f"❌ Email alert failed: {e}")
            return False

    def send_telegram_alert(self, message: str) -> bool:
        """Send Telegram alert."""
        if not self.config.config["telegram"]["enabled"]:
            return False

        try:
            import requests
            telegram_config = self.config.config["telegram"]
            url = f"https://api.telegram.org/bot{telegram_config['bot_token']}/sendMessage"
            data = {"chat_id": telegram_config["chat_id"], "text": message}
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                print(f"📱 Telegram alert sent")
                return True
            return False
        except Exception as e:
            print(f"❌ Telegram alert failed: {e}")
            return False

    def send_discord_alert(self, message: str) -> bool:
        """Send Discord webhook alert."""
        if not self.config.config["discord"]["enabled"]:
            return False

        try:
            import requests
            discord_config = self.config.config["discord"]
            data = {"content": message}
            response = requests.post(discord_config["webhook_url"], json=data, timeout=10)
            if response.status_code == 204:
                print(f"🤖 Discord alert sent")
                return True
            return False
        except Exception as e:
            print(f"❌ Discord alert failed: {e}")
            return False

    def check_price_alerts(self, price_data: Dict[str, float]) -> None:
        """Check if any price alerts should trigger."""
        for alert in self.config.config.get("price_alerts", []):
            symbol = alert.get("symbol", "").upper()
            current_price = price_data.get(symbol)
            if current_price:
                if alert.get("type") == "above" and current_price >= alert.get("price"):
                    msg = f"🚀 {symbol} is now ${current_price:.2f} (above target of ${alert['price']:.2f})"
                    self.broadcast_alert(f"{symbol} Price Alert", msg)
                elif alert.get("type") == "below" and current_price <= alert.get("price"):
                    msg = f"📉 {symbol} is now ${current_price:.2f} (below target of ${alert['price']:.2f})"
                    self.broadcast_alert(f"{symbol} Price Alert", msg)

    def check_profit_loss_alert(self, total_gain: float, previous_gain: Optional[float] = None) -> None:
        """Check if portfolio P/L crossed threshold."""
        threshold = self.config.config.get("profit_loss_threshold", 100)
        if previous_gain is not None:
            change = abs(total_gain - previous_gain)
            if change >= threshold:
                direction = "📈 UP" if total_gain > previous_gain else "📉 DOWN"
                msg = f"{direction} Portfolio P/L changed by ${change:.2f}.\nCurrent: ${total_gain:.2f}"
                self.broadcast_alert("Portfolio Alert", msg)

    def broadcast_alert(self, subject: str, message: str) -> None:
        """Send alert through all enabled channels."""
        self.send_email_alert(subject, message)
        self.send_telegram_alert(f"{subject}\n{message}")
        self.send_discord_alert(f"**{subject}**\n{message}")
