import argparse
import sqlite3
from pathlib import Path
from functools import wraps
from datetime import datetime, timedelta
import logging
import os

from flask import Flask, jsonify, render_template, request, session, redirect, url_for, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from auth import AuthManager
from security import (
    SecurityConfig, SecurityHeaders, InputValidator, RateLimiter
)
from exporter import PortfolioExporter


# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-key-change-in-production")
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SECURE_COOKIES", "True") == "True"
app.config["SESSION_COOKIE_HTTPONLY"] = os.getenv("HTTPONLY_COOKIES", "True") == "True"
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SAMESITE_COOKIES", "Strict")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
    minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", 60))
)

# Initialize security
SecurityHeaders.apply_to_flask(app)
auth_manager = AuthManager()
rate_limiter = RateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_REQUESTS", 100)),
    window_seconds=int(os.getenv("RATE_LIMIT_WINDOW", 3600))
)

# Setup logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.getenv("LOG_FILE", "crypto-gains.log"))
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("DATABASE_URL", "portfolio_history.db").replace("sqlite:///", ""))
EXPORTER = PortfolioExporter(str(DB_PATH))


def query_all(sql: str, params=()):
    """Safely query database."""
    if not DB_PATH.exists():
        return []
    try:
        with sqlite3.connect(str(DB_PATH)) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(sql, params).fetchall()]
    except Exception as e:
        logger.error(f"Database query error: {e}")
        return []


def login_required(f):
    """Decorator to require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            logger.warning(f"Unauthorized access attempt from {request.remote_addr}")
            return redirect(url_for("login"))
        
        # Check session timeout
        if "last_activity" in session:
            session_timeout = int(os.getenv("SESSION_TIMEOUT_MINUTES", 60))
            last_activity = datetime.fromisoformat(session["last_activity"])
            if datetime.now() - last_activity > timedelta(minutes=session_timeout):
                session.clear()
                logger.info(f"Session timeout for user {session.get('username')}")
                return redirect(url_for("login", message="Session expired. Please login again."))
        
        session["last_activity"] = datetime.now().isoformat()
        return f(*args, **kwargs)
    
    return decorated_function


def rate_limit_check(f):
    """Decorator to enforce rate limiting."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not rate_limiter.is_allowed(request.remote_addr):
            logger.warning(f"Rate limit exceeded for {request.remote_addr}")
            return jsonify({"error": "Rate limit exceeded"}), 429
        return f(*args, **kwargs)
    
    return decorated_function


@app.before_request
def security_checks():
    """Perform security checks on every request."""
    # Check allowed hosts
    allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if request.host.split(":")[0] not in allowed_hosts and "127.0.0.1" not in allowed_hosts:
        logger.warning(f"Invalid host: {request.host}")
        return jsonify({"error": "Forbidden"}), 403
    
    # Log requests
    if request.path != "/":
        logger.debug(f"{request.method} {request.path} from {request.remote_addr}")


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


# ==================== Authentication Routes ====================

@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration endpoint."""
    if request.method == "GET":
        return render_template("register.html")
    
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip()
    
    # Validate inputs
    if not InputValidator.validate_username(username):
        return jsonify({"error": "Invalid username. Use 3-32 alphanumeric characters."}), 400
    
    if not InputValidator.validate_email(email):
        return jsonify({"error": "Invalid email address"}), 400
    
    is_valid, errors = InputValidator.validate_password(password)
    if not is_valid:
        return jsonify({"error": "Password too weak: " + "; ".join(errors)}), 400
    
    # Register user
    if auth_manager.register_user(username, password, email):
        logger.info(f"New user registered: {username}")
        return jsonify({"message": "Registration successful. Please login."}), 201
    else:
        return jsonify({"error": "User already exists"}), 409


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login endpoint."""
    if request.method == "GET":
        message = request.args.get("message", "")
        return render_template("login.html", message=message)
    
    if not rate_limiter.is_allowed(f"login-{request.remote_addr}"):
        logger.warning(f"Login rate limit exceeded for {request.remote_addr}")
        return jsonify({"error": "Too many login attempts. Try again later."}), 429
    
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    
    # Verify credentials
    if not auth_manager.verify_password(username, password):
        logger.warning(f"Failed login attempt for user: {username}")
        return jsonify({"error": "Invalid username or password"}), 401
    
    # Create session
    session.permanent = True
    session["username"] = username
    session["last_activity"] = datetime.now().isoformat()
    logger.info(f"User logged in: {username}")
    
    return jsonify({"message": "Login successful", "redirect": url_for("dashboard")}), 200


@app.route("/logout")
@login_required
def logout():
    """User logout endpoint."""
    username = session.get("username")
    session.clear()
    logger.info(f"User logged out: {username}")
    return redirect(url_for("login"))


# ==================== Dashboard Routes ====================

@app.route("/")
def index():
    """Redirect to dashboard or login."""
    if "username" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard page."""
    username = session.get("username")
    return render_template("dashboard.html", username=username)


# ==================== API Routes ====================

@app.get("/api/summary")
@login_required
@rate_limit_check
def api_summary():
    """Get portfolio summary."""
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
@login_required
@rate_limit_check
def api_history():
    """Get portfolio history."""
    limit = request.args.get("limit", 500, type=int)
    if limit > 10000:
        limit = 10000
    
    rows = query_all(
        """
        SELECT timestamp, total_value, total_gain, total_percent_gain, currency
        FROM portfolio_snapshots
        ORDER BY timestamp ASC
        LIMIT ?
        """,
        (limit,)
    )
    return jsonify(rows)


@app.get("/api/positions")
@login_required
@rate_limit_check
def api_positions():
    """Get current positions."""
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


@app.get("/api/position/<symbol>")
@login_required
@rate_limit_check
def api_position_history(symbol):
    """Get history for a specific position."""
    symbol = InputValidator.sanitize_filename(symbol.upper())
    limit = request.args.get("limit", 100, type=int)
    if limit > 10000:
        limit = 10000
    
    rows = query_all(
        """
        SELECT timestamp, amount, current_price, current_value, gain, percent_gain
        FROM position_snapshots
        WHERE symbol = ?
        ORDER BY timestamp ASC
        LIMIT ?
        """,
        (symbol, limit)
    )
    return jsonify(rows)


@app.get("/api/stats")
@login_required
@rate_limit_check
def api_stats():
    """Get portfolio statistics."""
    portfolio_stats = query_all(
        """
        SELECT 
            MIN(total_value) as min_value,
            MAX(total_value) as max_value,
            AVG(total_gain) as avg_gain,
            COUNT(*) as snapshot_count
        FROM portfolio_snapshots
        """
    )
    
    position_count = query_all(
        """
        SELECT COUNT(DISTINCT symbol) as total_positions
        FROM position_snapshots
        """
    )
    
    stats = {
        "portfolio": portfolio_stats[0] if portfolio_stats else {},
        "positions": position_count[0] if position_count else {},
    }
    
    return jsonify(stats)


@app.post("/api/export")
@login_required
@rate_limit_check
def api_export():
    """Export portfolio data."""
    data = request.get_json() or {}
    export_format = data.get("format", "json").lower()
    
    if export_format not in ["json", "csv"]:
        return jsonify({"error": "Invalid export format"}), 400
    
    username = session.get("username")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        if export_format == "json":
            filename = f"portfolio_export_{timestamp}.json"
            EXPORTER.export_json(filename)
        else:
            filename = f"portfolio_export_{timestamp}.csv"
            EXPORTER.export_csv(filename)
        
        logger.info(f"User {username} exported data as {export_format}")
        return jsonify({
            "message": "Export successful",
            "filename": filename
        }), 200
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({"error": "Export failed"}), 500


@app.get("/api/health")
def api_health():
    """Health check endpoint."""
    return jsonify({
        "ok": True,
        "database": str(DB_PATH),
        "database_exists": DB_PATH.exists(),
        "timestamp": datetime.now().isoformat()
    })


# ==================== Error Handlers ====================

@app.errorhandler(401)
def unauthorized(error):
    """Handle 401 Unauthorized."""
    return jsonify({"error": "Unauthorized"}), 401


@app.errorhandler(403)
def forbidden(error):
    """Handle 403 Forbidden."""
    return jsonify({"error": "Forbidden"}), 403


def main():
    """Run the Flask application."""
    parser = argparse.ArgumentParser(description="Secure crypto gains web dashboard")
    parser.add_argument("--host", default=os.getenv("SERVER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("SERVER_PORT", 5000)))
    parser.add_argument("--db", default=os.getenv("DATABASE_URL", "portfolio_history.db"))
    parser.add_argument("--debug", action="store_true", default=os.getenv("DEBUG", "False") == "True")
    
    args = parser.parse_args()
    
    global DB_PATH
    DB_PATH = Path(args.db.replace("sqlite:///", ""))
    
    if os.getenv("FLASK_ENV") == "production" and args.debug:
        logger.warning("⚠️ Debug mode enabled in production. This is NOT recommended.")
    
    logger.info(f"Starting Crypto Gains Dashboard on {args.host}:{args.port}")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
    
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=False
    )


if __name__ == "__main__":
    main()
