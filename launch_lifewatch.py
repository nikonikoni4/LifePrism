
import os
import sys
import threading
import webbrowser
import time
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from PIL import Image
import pystray
import logging

# Configure logging
logging.basicConfig(filename='lifewatch.log', level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure the module can be found
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from lifewatch.server.main import app
except ImportError as e:
    logger.error(f"Failed to import app: {e}")
    # Fallback/Debug if imports fail
    raise e

# Determine if running in frozen mode (PyInstaller)
if getattr(sys, 'frozen', False):
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    base_path = sys._MEIPASS
    frontend_dist = os.path.join(base_path, 'frontend_dist')
    icon_path = os.path.join(base_path, 'icon.jpg')
else:
    base_path = os.path.dirname(os.path.abspath(__file__))
    frontend_dist = os.path.join(base_path, 'frontend', 'dist')
    icon_path = os.path.join(base_path, 'icon.jpg')

logger.info(f"Base path: {base_path}")
logger.info(f"Frontend dist: {frontend_dist}")

# Modify app to serve frontend
if os.path.exists(frontend_dist):
    # Remove existing root route if it exists (to replace with frontend)
    # Filter out the existing '/' route
    new_routes = [r for r in app.router.routes if getattr(r, 'path', '') != '/']
    app.router.routes = new_routes
    
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Check if file exists (e.g. favicon.ico, manifestation.json)
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
             return FileResponse(file_path)
        
        # Avoid catching API routes that might have been missed or 404'd by API router?
        # No, API routes are checked first if they are in the router list before this catch-all?
        # Actually, in FastAPI, routes are matched in order. 
        # Since we append this route LAST, it should be fine.
        # But wait, app.include_router was called in main.py, so those routes are already there.
        # So this catch-all matches anything NOT matched by previous routes.
        
        return FileResponse(os.path.join(frontend_dist, "index.html"))
        
    @app.get("/")
    async def serve_root():
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    logger.warning(f"Frontend dist not found at {frontend_dist}")

def run_server():
    try:
        # Check for free port? defaulting to 8000
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    except Exception as e:
        logger.error(f"Server error: {e}")

def on_quit(icon, item):
    icon.stop()
    os._exit(0)

def on_open(icon, item):
    webbrowser.open("http://127.0.0.1:8000")

def setup_tray():
    if not os.path.exists(icon_path):
        logger.error(f"Icon not found at {icon_path}")
        return
        
    image = Image.open(icon_path)
    menu = pystray.Menu(
        pystray.MenuItem("Open LifeWatch", on_open, default=True),
        pystray.MenuItem("Exit", on_quit)
    )
    icon = pystray.Icon("LifeWatch AI", image, "LifeWatch AI", menu)
    icon.run()

if __name__ == "__main__":
    # Start server
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server
    time.sleep(2)
    
    # Open browser
    webbrowser.open("http://127.0.0.1:8000")
    
    # Run tray
    try:
        setup_tray()
    except Exception as e:
        logger.error(f"Tray error: {e}")
        # If tray fails, keep running so server stays up? Or exit. 
        # Usually exit.
        input("Press enter to exit...")
