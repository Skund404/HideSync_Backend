def fix_storage_utilization():
    """One-time fix to synchronize storage utilization counts."""

    # Get session
    from app.db.session import SessionLocal
    session = SessionLocal()

    try:
        # Get all materials with storage locations
        from app.db.models.material import Material
        from app.db.models.storage import StorageLocation

        materials = session.query(Material).filter(
            Material.storage_location.isnot(None)
        ).all()

        # Count materials per location
        location_counts = {}
        for material in materials:
            loc_id = material.storage_location
            location_counts[loc_id] = location_counts.get(loc_id, 0) + 1

        # Update each storage location
        for loc_id, count in location_counts.items():
            location = session.query(StorageLocation).filter(
                StorageLocation.id == loc_id
            ).first()

            if location:
                location.utilized = count
                print(f"Updated location {location.name}: utilized = {count}")

        # Commit changes
        session.commit()
        print("Storage utilization fixed successfully")

    except Exception as e:
        session.rollback()
        print(f"Error fixing storage utilization: {e}")
    finally:
        session.close()


# Run the fix
if __name__ == "__main__":
    fix_storage_utilization()