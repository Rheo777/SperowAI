import multiprocessing
import os

# Worker configuration
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
worker_class = 'sync'

# Timeout configuration
timeout = 1000  # Increased to 5 minutes
graceful_timeout = 1000
keepalive = 5

# Worker process configuration
max_requests = 1000
max_requests_jitter = 50
worker_connections = 1000

# Logging configuration
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Bind configuration
port = int(os.environ.get("PORT", 5000))
bind = f"0.0.0.0:{port}"

# Worker process name
proc_name = 'sperow_ai'

# SSL Configuration (if needed)
# keyfile = 'path/to/keyfile'
# certfile = 'path/to/certfile'

# Additional settings to prevent timeouts
worker_timeout = 1000  # Match the timeout setting
preload_app = True
reuse_port = True
