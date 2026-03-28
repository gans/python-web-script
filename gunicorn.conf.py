# gunicorn.conf.py
# Gunicorn configuration for PyRunner
# Run with: gunicorn -c gunicorn.conf.py app:app

import multiprocessing

# Server socket
bind = "0.0.0.0:8000"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"   # handles keep-alive without tying up whole workers
threads = 2
worker_connections = 1000
timeout = 30
keepalive = 5              # seconds to wait for next request on a keep-alive conn

# Logging
accesslog = "-"   # stdout
errorlog  = "-"   # stderr
loglevel  = "info"

# Process naming
proc_name = "pyrunner"

# Reload on code change (disable in production)
reload = False
