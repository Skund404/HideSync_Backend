# HideSync Database Tools

This directory contains scripts for managing the HideSync database, including creation, seeding, and validation.

## Available Scripts

- **create_db.py**: Creates a new SQLCipher encrypted database with the necessary schema
- **seed_db.py**: Seeds the database with data from a JSON file
- **validate_db.py**: Validates the database structure and content
- **manage_db.py**: Unified interface for all database operations

## Usage

### Creating a New Database

```bash
python -m db_tools.create_db
```

Options:
- `--minimal`: Create minimal database with core tables only
- `--force`: Force creation even if database exists

### Seeding the Database

```bash
python -m db_tools.seed_db
```

Options:
- `--seed-file`: Path to the seed data JSON file (default: app/db/seed_data.json)
- `--debug`: Enable debug logging for more detailed output

### Validating the Database

```bash
python -m db_tools.validate_db
```

Options:
- `--verbose`: Enable verbose output

### All-in-One Management

```bash
python -m db_tools.manage_db --create --seed --validate
```

Options:
- `--create`: Create the database
- `--seed`: Seed the database with initial data
- `--validate`: Validate the database structure and content
- `--reset`: Reset (delete and recreate) the database
- `--seed-file`: Path to the seed data JSON file
- `--verbose`: Enable verbose output

## Examples

### Create a fresh database and seed it

```bash
python -m db_tools.manage_db --reset --seed
```

### Create a database and seed it with a custom seed file

```bash
python -m db_tools.manage_db --create --seed --seed-file custom_seed.json
```

### Validate an existing database

```bash
python -m db_tools.validate_db --verbose
```

## Requirements

These scripts require the following dependencies:

- pysqlcipher3
- SQLAlchemy (for model-based schema creation)
- The HideSync application core modules

## Database Structure

The database includes the following core entity types:

- User management: users, roles, permissions
- Customer management: customers, suppliers
- Inventory: materials, tools, storage locations
- Projects: project templates, projects, components, tasks
- Sales: sales, sale items, purchases, purchase items
- Media management: media assets, tags

## Encryption

The database is encrypted using SQLCipher with a key managed by the application's KeyManager.
The encryption settings include:

- PRAGMA cipher_page_size = 4096
- PRAGMA kdf_iter = 256000
- PRAGMA cipher_hmac_algorithm = HMAC_SHA512
- PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512