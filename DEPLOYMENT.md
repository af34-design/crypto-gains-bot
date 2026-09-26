# Deployment and Hardening Guide

This project should be deployed with a reverse proxy and TLS, using environment variables for secrets and a non-root service account.

## 1. Install dependencies

python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

## 2. Create a production environment file

Copy `.env.example` to `.env` and replace all placeholder values.

cp .env.example .env

Critical variables:
- `SECRET_KEY`
- `FLASK_ENV=production`
- `DEBUG=False`
- `SERVER_HOST=127.0.0.1`
- `SERVER_PORT=5000`
- `ALLOWED_HOSTS=localhost,127.0.0.1`

Do not commit `.env` to Git. It is already ignored by `.gitignore`.

## 3. Run with Gunicorn

gunicorn -c gunicorn.conf.py dashboard:app

This starts the application using a production WSGI server instead of Flask's development server.

## 4. Use a reverse proxy

A reverse proxy should sit in front of Gunicorn for TLS and request handling.

Example Nginx config is included at:
- `deploy/nginx-crypto-gains.conf`

Use it with a valid certificate from Let's Encrypt.

## 5. Run as a system service

A sample `systemd` service is included at:
- `deploy/crypto-gains.service`

Example installation:

sudo cp deploy/crypto-gains.service /etc/systemd/system/crypto-gains.service
sudo systemctl daemon-reload
sudo systemctl enable --now crypto-gains

## 6. Security checklist

- Keep `DEBUG=False`
- Keep private dashboard access behind authentication
- Do not bind the app directly to public interfaces
- Do not expose secrets in source control
- Use HTTPS only
- Set strict cookie hygiene
- Keep the DB file in a secure location with limited permissions
- Restrict the service account with `NoNewPrivileges=true`
- Rotate secrets periodically
- Keep logs and backups outside public web paths

## 7. Optional hardening

- Add rate limiting for `/login` and `/api/*`
- Use a dedicated database user or permissions if expanded to Postgres/MySQL
- Add periodic backups of `portfolio_history.db`
- Add SSO or OAuth if multiple users are expected
- Put the app behind a VPN or private network if it is not intended for public access

## 8. Health checks

Use a local health endpoint to confirm the app is running:

curl http://127.0.0.1:5000/api/health

## 9. Production notes

This dashboard is meant for private or semi-private use. It should not be exposed directly to the internet unless it is behind HTTPS, authentication, and a reverse proxy.
