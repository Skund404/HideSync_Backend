import sys
import os

print("--- Python Path Check ---")
print(f"Current Working Directory: {os.getcwd()}")
print("sys.path contains:")
project_root_found = False
for p in sys.path:
    print(f"  - {p}")
    if p == os.getcwd():
        project_root_found = True

print("--- Analysis ---")
if project_root_found:
    print("OK: Project root directory is in sys.path.")
else:
    print("PROBLEM: Project root directory is NOT in sys.path.")

print("\nChecking for 'app' directory...")
app_dir = os.path.join(os.getcwd(), "app")
if os.path.isdir(app_dir):
    print(f"OK: Directory '{app_dir}' exists.")
else:
    print(f"PROBLEM: Directory '{app_dir}' does NOT exist or is not a directory.")
print("--- End Check ---")
