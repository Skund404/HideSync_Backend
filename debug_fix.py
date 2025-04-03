#!/usr/bin/env python3
"""
This script adds the missing entity_media_service method to ServiceFactory
"""
import os
from pathlib import Path


def main():
    # Find the service factory file
    app_dir = Path("./app")
    service_factory_path = app_dir / "services" / "service_factory.py"

    if not service_factory_path.exists():
        print(f"ERROR: Could not find service_factory.py at {service_factory_path}")
        return

    # Read the current content
    with open(service_factory_path, "r") as f:
        content = f.read()

    # Check if we need to add the import for EntityMediaService
    if "from app.services.entity_media_service import EntityMediaService" not in content:
        # Find the block of imports for services
        lines = content.split("\n")
        import_section_end = 0

        for i, line in enumerate(lines):
            if line.startswith("from app.services.") and "import" in line:
                import_section_end = i

        # Add the import
        if import_section_end > 0:
            lines.insert(import_section_end + 1, "from app.services.entity_media_service import EntityMediaService")
            print("Added EntityMediaService import")
        else:
            print("WARNING: Could not find where to add the import")
            return

        # Update content with the new import
        content = "\n".join(lines)

    # Add the get_entity_media_service method if it doesn't exist
    if "def get_entity_media_service" not in content:
        # Find the class definition and where to add the method
        lines = content.split("\n")

        # Find a similar get_*_service method to use as template
        service_method_template = None
        method_indent = "    "  # Default indentation

        for i, line in enumerate(lines):
            if line.strip().startswith("def get_") and "_service" in line:
                # Found a service method to use as template
                j = i
                method_lines = []
                while j < len(lines) and (lines[j].strip() == "" or lines[j].startswith(method_indent)):
                    method_lines.append(lines[j])
                    j += 1

                service_method_template = "\n".join(method_lines)
                break

        if service_method_template:
            # Use the template to create our new method
            new_method = service_method_template.replace(
                "def get_media_asset_service",
                "def get_entity_media_service"
            ).replace(
                "MediaAssetService",
                "EntityMediaService"
            ).replace(
                "media_asset_service",
                "entity_media_service"
            ).replace(
                "_media_asset_service",
                "_entity_media_service"
            )

            # Find where to add the new method (before the last method or at the end of class)
            class_end = len(lines)
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip() == "":
                    class_end = i
                    break

            lines.insert(class_end, new_method)
            content = "\n".join(lines)
            print("Added get_entity_media_service method")
        else:
            print("WARNING: Could not find a template service method")
            # Create a generic method
            new_method = """
    def get_entity_media_service(self) -> EntityMediaService:
        """
        Get or create
        an
        EntityMediaService
        instance.

        Returns:
        EntityMediaService: The
        entity
        media
        service
        instance
    """
    if not hasattr(self, "_entity_media_service"):
        self._entity_media_service = EntityMediaService(self.db, self.encryption_service)
    return self._entity_media_service
"""
    lines.append(new_method)
    content = "\n".join(lines)
    print("Added generic get_entity_media_service method")


# Write the updated content
with open(service_factory_path, "w") as f:
    f.write(content)

print(f"Successfully updated {service_factory_path}")
print("Please restart your FastAPI server for changes to take effect")

if __name__ == "__main__":
    main()