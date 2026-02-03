"""
Copy updated script to T: drive location
"""
import shutil
import os

# Source (git repo)
source = r"/home/user/updating_wetlands/scripts/update_wetland_boundaries.py"

# Destination (T: drive where you're running from)
dest = r"T:\work\giss\monthly\202601jan\gallaga\lakes_and_streams_planning\scripts\update_wetland_boundaries.py"

# Convert WSL path to Windows path if needed
if source.startswith("/"):
    # This is a WSL path, need to convert
    print("Converting WSL path to Windows path...")
    # /home/user maps to \\wsl$\Ubuntu\home\user or similar
    # Or just use the local path
    source = r"T:\path\to\your\git\repo\updating_wetlands\scripts\update_wetland_boundaries.py"
    print(f"Please manually copy from your git repo to: {dest}")
else:
    # Backup old file
    if os.path.exists(dest):
        backup = dest + ".backup"
        shutil.copy2(dest, backup)
        print(f"Backed up old file to: {backup}")

    # Copy new file
    shutil.copy2(source, dest)
    print(f"Copied updated script to: {dest}")
    print("You can now re-run the script!")
