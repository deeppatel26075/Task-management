import os

files_to_delete = [
    "models.py",
    "fix_db.py",
    "capture_screenshot.py",
    "screenshot.png"
]

for filename in files_to_delete:
    filepath = os.path.join(os.path.dirname(__file__), filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            print(f"✅ Deleted: {filename}")
        except Exception as e:
            print(f"❌ Failed to delete {filename}: {e}")
    else:
        print(f"ℹ️ Already deleted or not found: {filename}")

print("\nCleanup complete! You can safely delete this cleanup.py file as well.")
