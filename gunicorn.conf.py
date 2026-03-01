bind = "0.0.0.0:8080"
workers = 1  # Single worker to avoid duplicate scheduler jobs
threads = 4
preload_app = True


def on_starting(server):
    """Start the background scheduler when Gunicorn starts."""
    from app import scheduler
    if not scheduler.running:
        scheduler.start()


def on_exit(server):
    """Shut down scheduler on exit."""
    from app import scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)
