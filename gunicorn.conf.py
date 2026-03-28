# gunicorn.conf.py
# Gunicorn configuration for PyRunner
# Run with: gunicorn -c gunicorn.conf.py app:app

import multiprocessing

# Server socket
bind = "0.0.0.0:8000"

# Worker processes — 2-4 x number of CPUs is a good rule of thumb
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30

# Logging
accesslog = "-"   # stdout
errorlog  = "-"   # stderr
loglevel  = "info"

# Process naming
proc_name = "pyrunner"

# Reload on code change (disable in production)
reload = False
