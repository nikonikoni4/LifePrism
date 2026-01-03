
import PyInstaller.__main__
import os
import shutil

# Clean up previous builds
if os.path.exists("dist"):
    shutil.rmtree("dist")
if os.path.exists("build"):
    shutil.rmtree("build")

# Define paths
base_path = os.path.dirname(os.path.abspath(__file__))
frontend_dist = os.path.join(base_path, "frontend", "dist")
icon_path = os.path.join(base_path, "icon.jpg")
egg_info_path = os.path.join(base_path, "lifewatch.egg-info")

# Verify paths
if not os.path.exists(frontend_dist):
    print(f"Error: Frontend dist not found at {frontend_dist}. Please run 'npm run build' in frontend directory.")
    exit(1)

# PyInstaller arguments
args = [
    'launch_lifewatch.py',  # Script to run
    '--name=LifeWatch-AI',  # Name of the executable
    '--noconfirm',
    '--onefile',            # One file executable
    '--windowed',           # No console window
    f'--icon={icon_path}',  # Icon
    f'--add-data={frontend_dist};frontend_dist', # Include frontend assets
    f'--add-data={icon_path};.',                 # Include icon for tray
    # '--hidden-import=uvicorn.logging',
    # '--hidden-import=uvicorn.loops',
    # '--hidden-import=uvicorn.loops.auto',
    # '--hidden-import=uvicorn.protocols',
    # '--hidden-import=uvicorn.protocols.http',
    # '--hidden-import=uvicorn.protocols.http.auto',
    # '--hidden-import=uvicorn.protocols.websockets',
    # '--hidden-import=uvicorn.protocols.websockets.auto',
    # '--hidden-import=uvicorn.lifespan.on',
    '--collect-all=lifewatch', # Collect everything in lifewatch package
    '--collect-all=pystray',
    '--collect-all=DrissionPage', 
    '--collect-all=langgraph',
]

if os.path.exists(egg_info_path):
    args.append(f'--add-data={egg_info_path};lifewatch.egg-info')

print("Running PyInstaller with args:", args)

PyInstaller.__main__.run(args)

print("Build complete. Executable should be in 'dist' folder.")
