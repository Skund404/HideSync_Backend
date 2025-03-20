# File: app/core/key_manager.py
"""
Secure key management for HideSync.

This module provides functions for securely retrieving encryption keys
and other sensitive credentials from various secure storage options.
"""

import os
import stat
import logging
import json
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.exceptions import SecurityException

logger = logging.getLogger(__name__)


class KeyManager:
    """Manages secure access to encryption keys and other sensitive credentials."""

    @staticmethod
    def get_database_encryption_key() -> str:
        """
        Retrieve the database encryption key from the configured secure source.

        Returns:
            str: The encryption key

        Raises:
            SecurityException: If key cannot be securely retrieved
        """
        # For development/testing environments, use the config value
        if (
            settings.ENVIRONMENT in ("development", "testing")
            and not settings.PRODUCTION
        ):
            logger.warning(
                "Using development key management method - NOT SECURE FOR PRODUCTION"
            )
            return settings.DATABASE_ENCRYPTION_KEY

        # For production, use the configured key management method
        key_method = settings.KEY_MANAGEMENT_METHOD.lower()

        if key_method == "file":
            return KeyManager._get_key_from_file()
        elif key_method == "environment":
            return KeyManager._get_key_from_environment()
        elif key_method == "aws":
            return KeyManager._get_key_from_aws()
        elif key_method == "azure":
            return KeyManager._get_key_from_azure()
        elif key_method == "gcp":
            return KeyManager._get_key_from_gcp()
        else:
            raise SecurityException(f"Unsupported key management method: {key_method}")

    @staticmethod
    def _get_key_from_file() -> str:
        """
        Retrieve encryption key from a secure file.

        The file should:
        - Be located outside web root
        - Have 400 permissions (read-only by owner)
        - Be owned by the application service account

        Returns:
            str: The encryption key

        Raises:
            SecurityException: If file permissions are unsafe or file can't be read
        """
        key_file = settings.KEY_FILE_PATH

        try:
            # Ensure the key file exists
            if not os.path.isfile(key_file):
                raise SecurityException(f"Key file not found: {key_file}")

            # Check file permissions (should be 400 - read-only by owner)
            file_stats = os.stat(key_file)

            # On Unix systems, check if group or others have any permissions
            if hasattr(stat, "S_IRWXG") and hasattr(stat, "S_IRWXO"):
                if file_stats.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                    logger.warning(
                        f"Key file has unsafe permissions: {oct(file_stats.st_mode)}"
                    )

                    if settings.ENFORCE_KEY_FILE_PERMISSIONS:
                        raise SecurityException("Key file has unsafe permissions")

            # Read and return the key
            with open(key_file, "r") as f:
                key = f.read().strip()

            if not key:
                raise SecurityException("Empty key in key file")

            return key

        except Exception as e:
            logger.error(f"Error accessing key file: {str(e)}")
            raise SecurityException(f"Failed to retrieve key from file: {str(e)}")

    @staticmethod
    def _get_key_from_environment() -> str:
        """
        Retrieve encryption key from environment variable.

        Note: This is less secure than file-based storage as environment variables
        can be exposed in process listings. Use only when necessary.

        Returns:
            str: The encryption key

        Raises:
            SecurityException: If environment variable is not set
        """
        env_var = settings.KEY_ENVIRONMENT_VARIABLE
        key = os.environ.get(env_var)

        if not key:
            raise SecurityException(f"Environment variable {env_var} not set or empty")

        return key

    @staticmethod
    def _get_key_from_aws() -> str:
        """
        Retrieve encryption key from AWS Secrets Manager.

        Requires:
        - boto3 library installed
        - AWS credentials configured

        Returns:
            str: The encryption key

        Raises:
            SecurityException: If key cannot be retrieved from AWS
        """
        try:
            import boto3

            secret_name = settings.AWS_SECRET_NAME
            region = settings.AWS_REGION

            # Create a Secrets Manager client
            client = boto3.client(service_name="secretsmanager", region_name=region)

            # Get the secret value
            response = client.get_secret_value(SecretId=secret_name)

            # The secret can be either a string or binary, handle both
            if "SecretString" in response:
                secret = response["SecretString"]
                # If the secret is a JSON string, parse it
                try:
                    secret_dict = json.loads(secret)
                    if settings.AWS_SECRET_KEY_FIELD in secret_dict:
                        return secret_dict[settings.AWS_SECRET_KEY_FIELD]
                    else:
                        return secret
                except json.JSONDecodeError:
                    # Not JSON, return as is
                    return secret
            else:
                # Binary secret, decode it
                import base64

                binary_secret = response["SecretBinary"]
                return base64.b64decode(binary_secret).decode("utf-8")

        except ImportError:
            raise SecurityException(
                "boto3 library not installed, required for AWS Secrets Manager"
            )
        except Exception as e:
            logger.error(f"Error retrieving key from AWS Secrets Manager: {str(e)}")
            raise SecurityException(f"Failed to retrieve key from AWS: {str(e)}")

    @staticmethod
    def _get_key_from_azure() -> str:
        """
        Retrieve encryption key from Azure Key Vault.

        Requires:
        - azure-keyvault-secrets library installed
        - Azure credentials configured

        Returns:
            str: The encryption key

        Raises:
            SecurityException: If key cannot be retrieved from Azure
        """
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            vault_url = settings.AZURE_VAULT_URL
            secret_name = settings.AZURE_SECRET_NAME

            # Create a credential
            credential = DefaultAzureCredential()

            # Create a secret client
            client = SecretClient(vault_url=vault_url, credential=credential)

            # Get the secret
            retrieved_secret = client.get_secret(secret_name)

            return retrieved_secret.value

        except ImportError:
            raise SecurityException(
                "azure-keyvault-secrets library not installed, required for Azure Key Vault"
            )
        except Exception as e:
            logger.error(f"Error retrieving key from Azure Key Vault: {str(e)}")
            raise SecurityException(f"Failed to retrieve key from Azure: {str(e)}")

    @staticmethod
    def _get_key_from_gcp() -> str:
        """
        Retrieve encryption key from Google Secret Manager.

        Requires:
        - google-cloud-secret-manager library installed
        - GCP credentials configured

        Returns:
            str: The encryption key

        Raises:
            SecurityException: If key cannot be retrieved from GCP
        """
        try:
            from google.cloud import secretmanager

            project_id = settings.GCP_PROJECT_ID
            secret_id = settings.GCP_SECRET_ID
            version_id = settings.GCP_SECRET_VERSION

            # Create the Secret Manager client
            client = secretmanager.SecretManagerServiceClient()

            # Build the resource name
            name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

            # Access the secret version
            response = client.access_secret_version(request={"name": name})

            # Return the decoded payload
            return response.payload.data.decode("UTF-8")

        except ImportError:
            raise SecurityException(
                "google-cloud-secret-manager library not installed, required for GCP Secret Manager"
            )
        except Exception as e:
            logger.error(f"Error retrieving key from Google Secret Manager: {str(e)}")
            raise SecurityException(f"Failed to retrieve key from GCP: {str(e)}")

    @staticmethod
    def create_key_file(key: Optional[str] = None) -> str:
        """
        Create a secure key file with proper permissions.

        Args:
            key: Optional encryption key to write. If None, generates a new key.

        Returns:
            str: The path to the created key file

        Raises:
            SecurityException: If file cannot be created securely
        """
        # Generate a key if not provided
        if key is None:
            import secrets

            key = secrets.token_hex(32)  # 256-bit key

        # Get the key file path
        key_file = settings.KEY_FILE_PATH

        try:
            # Create directory if it doesn't exist
            key_dir = os.path.dirname(key_file)
            os.makedirs(key_dir, exist_ok=True)

            # Write the key to the file
            with open(key_file, "w") as f:
                f.write(key)

            # Set secure permissions (0400 - read-only by owner)
            os.chmod(key_file, 0o400)

            logger.info(f"Created secure key file at {key_file}")
            return key_file

        except Exception as e:
            logger.error(f"Error creating key file: {str(e)}")
            raise SecurityException(f"Failed to create key file: {str(e)}")
