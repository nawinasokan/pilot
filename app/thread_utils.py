import threading
import logging

logger = logging.getLogger(__name__)


def run_in_thread(target, *args, **kwargs):
    
    thread = threading.Thread(
        target=target,
        args=args,
        kwargs=kwargs,
        daemon=True
    )
    thread.start()
