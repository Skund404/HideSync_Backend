# HideSync Database Setup Guide

This guide explains how to set up the HideSync database with SQLCipher encryption.

## Prerequisites

Before setting up the database, make sure you have the required dependencies:

```bash
pip install sqlalchemy sqlcipher3 pysqlcipher3
```

For Ubuntu/Debian systems, you may need to install additional system packages:

```bash
sudo apt-get install libsqlcipher-dev
```

For macOS with Homebrew:

```bash
brew install sqlcipher
```

## Database Configuration

The database settings are configured in `app/core/config.py`. The relevant settings are:

- `USE_SQLCIPHER`: Set to `True` to enable SQLCipher encryption
- `DATABASE_PATH`: Path to the SQLite database file (e.g., `hidesync.db`)
- `DATABASE_ENCRYPTION_KEY`: Encryption key for SQLCipher

For production environments, always set a strong encryption key through environment variables:

```bash
export DATABASE_ENCRYPTION_KEY="your-strong-secure-key-here"
```

## Setup Process

### 1. Initialize the Database

Run the setup script to create the database, all tables, and the initial admin user:

```bash
python scripts/setup_db.py
```

This will:
1. Create a new SQLCipher-encrypted database file at the configured path
2. Create all the database tables based on SQLAlchemy models
3. Create the initial admin user if one doesn't exist

### 2. Verify the Setup

You can verify the database setup by running:

```bash
python scripts/verify_db.py
```

### 3. Backup and Restore

To backup the encrypted database:

```bash
python scripts/backup_db.py
```

This creates an encrypted backup file in the `backups` directory.

To restore from a backup:

```bash
python scripts/restore_db.py --backup backups/hidesync_backup_20240320.db
```

## Security Considerations

1. **Encryption Key**: Store your encryption key securely and never commit it to version control
2. **Backups**: Regularly backup your database and store backups securely
3. **Key Rotation**: For high-security environments, consider implementing key rotation

## Troubleshooting

### Common Issues

1. **SQLCipher Not Available**: 
   - Error: "SQLCipher requested but libraries not found"
   - Solution: Install the required dependencies as described in Prerequisites

2. **Wrong Encryption Key**:
   - Error: "file is encrypted or is not a database" 
   - Solution: Ensure you're using the correct encryption key

3. **Database File Permissions**:
   - Error: "unable to open database file"
   - Solution: Check file permissions on the database file and directory

For additional help, please refer to the HideSync documentation or contact the development team.

Documentation Update
I recommend adding a section to your documentation about secure key management in production:

Never store keys in:

Source code repositories
Configuration files with standard permissions
Environment variables (visible in process listings)
Logs or output streams


Consider key rotation:

Implement a process for regular key rotation
This requires re-encrypting the database with the new key


Backup strategy:

Ensure both the encrypted database AND the encryption key are backed up
But store them separately with different access controls



This approach creates defense in depth - even if someone obtains the encrypted database file, they still need the separately stored encryption key to access the data.