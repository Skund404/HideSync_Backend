#!/usr/bin/env python3
"""
This script checks and fixes the entity_media router registration.
"""
import os
import sys
from pathlib import Path


def main():
    # Find the app directory
    app_dir = Path("./app")
    if not app_dir.exists():
        print("ERROR: Could not find the app directory")
        sys.exit(1)

    # Check the api.py file where routers should be registered
    api_py_path = app_dir / "api" / "api.py"
    if not api_py_path.exists():
        print(f"ERROR: Could not find api.py at {api_py_path}")
        sys.exit(1)

    # Read the current content
    with open(api_py_path, "r") as f:
        content = f.read()

    # Check if entity_media is already imported
    if "from app.api.endpoints import entity_media" in content:
        print("entity_media module is already imported")
    else:
        print("entity_media module is NOT imported - adding import")

        # Find where to add the import
        lines = content.split("\n")

        # Find the import section
        import_section_end = 0
        for i, line in enumerate(lines):
            if line.startswith("from app.api.endpoints import"):
                import_section_end = i

        # Insert the import
        if import_section_end > 0:
            lines.insert(
                import_section_end + 1, "from app.api.endpoints import entity_media"
            )
            print("Added entity_media import")
        else:
            print("WARNING: Could not find where to add the import")
            return

    # Check if the router is included
    if "api_router.include_router(entity_media.router" in content:
        print("entity_media router is already included")
    else:
        print("entity_media router is NOT included - adding router")

        # Find where to add the router
        lines = content.split("\n")

        # Find the router section
        router_section_end = 0
        for i, line in enumerate(lines):
            if line.startswith("api_router.include_router("):
                router_section_end = i

        # Insert the router registration
        if router_section_end > 0:
            lines.insert(
                router_section_end + 1,
                'api_router.include_router(entity_media.router, prefix="/entity-media", tags=["entity-media"])',
            )
            print("Added entity_media router registration")
        else:
            print("WARNING: Could not find where to add the router registration")
            return

        # Write back the updated content
        with open(api_py_path, "w") as f:
            f.write("\n".join(lines))

        print(f"Successfully updated {api_py_path}")
        print("Please restart your FastAPI server for changes to take effect")


if __name__ == "__main__":
    main()
