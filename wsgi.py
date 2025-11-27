# CRITICAL: Monkey patch MUST be first, before any other imports
# This fixes the "RLock(s) were not greened" warning and prevents blocking
# Only use eventlet on Linux (production) - Windows doesn't support it properly
import platform
if platform.system() != 'Windows':
    import eventlet
    eventlet.monkey_patch()

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Use use_reloader=False to prevent double initialization
    app.run(debug=False, host='0.0.0.0', port=8000, use_reloader=False)