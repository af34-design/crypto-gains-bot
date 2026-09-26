import multiprocessing
import os

bind = f"127.0.0.1:{os.getenv('SERVER_PORT', '5000')}"
workers = max(2, multiprocessing.cpu_count() // 2)
threads = 4
worker_class = "gthread"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = False
capture_output = True
accesslog = "-"
errorlog = "-"
loglevel = "info"
