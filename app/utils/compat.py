"""
Cross-platform compatibility module for eventlet/threading

On Linux (production with gunicorn+eventlet): Uses eventlet for non-blocking I/O
On Windows (development): Uses standard threading module

This allows the same codebase to work on both platforms without modification.
"""

import platform
import time as _time

IS_WINDOWS = platform.system() == 'Windows'

if IS_WINDOWS:
    # Windows: Use standard threading
    import threading

    def sleep(seconds):
        """Sleep for specified seconds (blocking on Windows)"""
        _time.sleep(seconds)

    def spawn(func, *args, **kwargs):
        """Spawn a background task (thread on Windows)"""
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        return thread

    def create_lock():
        """Create a lock for thread synchronization"""
        return threading.Lock()

    class GreenletWrapper:
        """Wrapper to provide greenlet-like interface for threads"""
        def __init__(self, thread):
            self.thread = thread
            self._dead = False

        @property
        def dead(self):
            return not self.thread.is_alive()

        def wait(self, timeout=None):
            """Wait for thread to complete"""
            self.thread.join(timeout=timeout)

        def kill(self):
            """Cannot actually kill a thread, just mark as dead"""
            self._dead = True

    def spawn_n(func, *args, **kwargs):
        """Spawn without returning handle"""
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        thread.start()

else:
    # Linux: Use eventlet for non-blocking I/O
    import eventlet
    eventlet.monkey_patch()

    def sleep(seconds):
        """Sleep for specified seconds (non-blocking with eventlet)"""
        eventlet.sleep(seconds)

    def spawn(func, *args, **kwargs):
        """Spawn a background task (greenlet on Linux)"""
        return eventlet.spawn(func, *args, **kwargs)

    def create_lock():
        """Create a lock for greenlet synchronization"""
        return eventlet.semaphore.Semaphore()

    GreenletWrapper = None  # Not needed, eventlet.spawn returns greenlet directly

    def spawn_n(func, *args, **kwargs):
        """Spawn without returning handle"""
        eventlet.spawn_n(func, *args, **kwargs)
