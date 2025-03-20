# HideSync Key Management Guide

## Introduction

This guide explains how to securely manage encryption keys for HideSync in different deployment environments. Proper key management is critical for the security of your data.

## Key Management Methods

HideSync supports multiple key management methods to accommodate different deployment scenarios:

1. **File-based** (Default, best for local hosting)
2. **Environment Variable** (Simple but less secure)
3. **AWS Secrets Manager** (For AWS deployments)
4. **Azure Key Vault** (For Azure deployments)
5. **Google Secret Manager** (For GCP deployments)

## Local Hosting Setup

For locally hosted deployments, the file-based method offers a good balance of security and simplicity.

### Generating a Secure Key

1. Run the key generation script:

```bash
python scripts/generate_key.py
```

This will:
- Generate a secure random 256-bit key
- Create a key file at `/etc/hidesync/keys/db.key` (configurable)
- Set proper file permissions (read-only by owner)

2. Update your `.env` file with the key management method:

```
KEY_MANAGEMENT_METHOD=file
KEY_FILE_PATH=/etc/hidesync/keys/db.key
ENFORCE_KEY_FILE_PERMISSIONS=true
```

### File Permissions

For the file-based method, ensure:
- The key file has 0400 permissions (`-r--------`)
- The parent directory has 0700 permissions (`drwx------`)
- Both are owned by the user running the HideSync application

To check permissions:
```bash
ls -la /etc/hidesync/keys/db.key
```

To set proper permissions manually:
```bash
chmod 400 /etc/hidesync/keys/db.key
chmod 700 /etc/hidesync/keys
```

## Cloud Hosting Options

### AWS Setup

1. Create a secret in AWS Secrets Manager:
   - Sign in to AWS Console
   - Navigate to Secrets Manager
   - Create a new secret with the key "database_key"
   - Note the secret name and region

2. Update your `.env` file:

```
KEY_MANAGEMENT_METHOD=aws
AWS_SECRET_NAME=hidesync/database-key
AWS_REGION=us-east-1
AWS_SECRET_KEY_FIELD=database_key
```

3. Ensure proper IAM permissions are set for the application to access the secret.

### Azure Setup

1. Create a secret in Azure Key Vault:
   - Sign in to Azure Portal
   - Navigate to Key Vault
   - Create a new vault if needed
   - Add a secret for the database key

2. Update your `.env` file:

```
KEY_MANAGEMENT_METHOD=azure
AZURE_VAULT_URL=https://hidesync-vault.vault.azure.net/
AZURE_SECRET_NAME=database-key
```

3. Configure appropriate access policies for the application identity.

### GCP Setup

1. Create a secret in Google Secret Manager:
   - Sign in to Google Cloud Console
   - Navigate to Secret Manager
   - Create a new secret for the database key

2. Update your `.env` file:

```
KEY_MANAGEMENT_METHOD=gcp
GCP_PROJECT_ID=hidesync-project
GCP_SECRET_ID=database-key
GCP_SECRET_VERSION=latest
```

3. Ensure the application has proper IAM permissions to access the secret.

## Security Best Practices

1. **Never store the encryption key:**
   - In source code
   - In version control
   - In unsecured configuration files
   - In logs or console output

2. **Key Backup:**
   - Create a secure backup of your encryption key
   - Store it separately from database backups
   - Consider using a secure password manager or physical safe

3. **Key Rotation:**
   - Periodically rotate your encryption key (e.g., every 90-180 days)
   - This requires re-encrypting the database with the new key

4. **Access Control:**
   - Limit access to encryption keys to only essential personnel
   - Use the principle of least privilege for cloud service permissions

## Key Rotation Procedure

To rotate your encryption key:

1. Create a new secure key:
```bash
python scripts/generate_key.py --path /etc/hidesync/keys/db.key.new
```

2. Run the key rotation script:
```bash
python scripts/rotate_key.py --old-key-path /etc/hidesync/keys/db.key --new-key-path /etc/hidesync/keys/db.key.new
```

3. This script will:
   - Create a backup of your database
   - Re-encrypt the database with the new key
   - Update the active key file

## Troubleshooting

### Common Issues

1. **Permission Denied:**
   - Check file permissions on key file and directory
   - Ensure the application has read access to the key file

2. **Key Not Found:**
   - Verify the key file path in your configuration
   - Ensure the key file exists and has content

3. **Cloud Provider Authentication:**
   - Check your cloud provider credentials
   - Verify IAM/access permissions for the secret

For additional help, please contact the HideSync support team.