import multiprocessing
import os

# Worker configuration
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
worker_class = 'sync'

# Timeout configuration
timeout = 120  # Increase timeout to 120 seconds
graceful_timeout = 120
keepalive = 5

# Logging configuration
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Bind configuration
port = int(os.environ.get("PORT", 5000))
bind = f"0.0.0.0:{port}"

# Worker process name
proc_name = 'sperow_ai'

# Prevent worker timeout
worker_timeout = 120
