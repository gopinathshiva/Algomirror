# Gunicorn configuration for AlgoMirror with eventlet
# Monkey patch must happen before anything else

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    pass

def on_starting(server):
    """Called just before the master process is initialized."""
    pass

# Worker configuration
worker_class = 'eventlet'
workers = 1
timeout = 0

# Binding
bind = 'unix:/var/python/algomirror/algomirror.sock'

# Logging
loglevel = 'info'
accesslog = '/var/python/algomirror/logs/access.log'
errorlog = '/var/python/algomirror/logs/error.log'

# Eventlet specific
worker_connections = 1000
