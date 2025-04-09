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
from functools import lru_cache  # Import lru_cache

from app.core.config import settings
from app.core.exceptions import SecurityException

# Ensure logger is configured (might be redundant if configured elsewhere, but safe)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class KeyManager:
    """Manages secure access to encryption keys and other sensitive credentials."""

    @staticmethod
    @lru_cache()  # Cache the result to avoid repeated file reads/API calls
    def get_database_encryption_key() -> str:
        """
        Retrieve the database encryption key from the configured secure source.

        Returns:
            str: The encryption key

        Raises:
            SecurityException: If key cannot be securely retrieved or is missing when required.
        """
        # --- Determine Method ---
        # Use development key directly if configured and not in production mode
        # Note: The original logic checked settings.ENVIRONMENT and settings.PRODUCTION.
        # Let's simplify slightly: if PRODUCTION is explicitly true, use configured method.
        # Otherwise, if DATABASE_ENCRYPTION_KEY is set in settings, use that (treat as dev/test).
        key: Optional[str] = None
        key_method = "settings"  # Default assumption for dev/test

        if settings.PRODUCTION:
            key_method = settings.KEY_MANAGEMENT_METHOD.lower()
            logger.info(
                f"Production mode detected. Using key management method: '{key_method}'"
            )
        elif settings.DATABASE_ENCRYPTION_KEY:
            logger.warning(
                "Using DATABASE_ENCRYPTION_KEY from settings - intended for development/testing ONLY."
            )
            key = settings.DATABASE_ENCRYPTION_KEY  # Use directly from settings
        else:
            # Not production, and no direct key in settings, fall back to configured method
            key_method = settings.KEY_MANAGEMENT_METHOD.lower()
            logger.warning(
                f"Non-production mode, no direct key. Using configured method: '{key_method}'"
            )

        # --- Retrieve Key based on Method ---
        if key is None:  # Only retrieve if not already set from settings
            if key_method == "file":
                key = KeyManager._get_key_from_file()
            elif key_method == "environment":
                key = KeyManager._get_key_from_environment()
            elif key_method == "aws":
                key = KeyManager._get_key_from_aws()
            elif key_method == "azure":
                key = KeyManager._get_key_from_azure()
            elif key_method == "gcp":
                key = KeyManager._get_key_from_gcp()
            elif key_method == "settings":
                # This case should only be hit if PRODUCTION=false and DATABASE_ENCRYPTION_KEY was empty
                logger.error(
                    "Non-production mode, but DATABASE_ENCRYPTION_KEY setting is empty."
                )
                # Fall through to the check below
                pass
            else:
                logger.error(
                    f"Unsupported key management method configured: '{key_method}'"
                )
                raise SecurityException(
                    f"Unsupported key management method: {key_method}"
                )

        # --- Validate Result ---
        if not key:
            # If key is still None/empty after trying the method
            error_msg = f"Failed to retrieve database key using method: '{key_method}'."
            logger.error(error_msg)
            # Raise error only if SQLCipher is enabled, otherwise return empty string? Or None?
            # The original code implicitly expected a string, let's raise if required.
            if settings.USE_SQLCIPHER:
                raise SecurityException(
                    f"{error_msg} Database key is mandatory (USE_SQLCIPHER=true)."
                )
            else:
                logger.warning(
                    f"{error_msg} SQLCipher is disabled, proceeding without key."
                )
                # Returning an empty string might be safer than None if downstream expects str
                return ""

        # Key retrieved successfully
        logger.info(f"Successfully retrieved database key using method: '{key_method}'")
        # Avoid logging the key itself unless debugging is absolutely necessary
        # logger.debug(f"Retrieved key: {key[:4]}...{key[-4:]}")
        return key  # Return the non-empty key

    @staticmethod
    def _get_key_from_file() -> (
        Optional[str]
    ):  # Changed return type to Optional[str] for internal consistency
        """
        Retrieve encryption key from a secure file with enhanced logging.

        Returns:
            Optional[str]: The encryption key, or None if retrieval fails.

        Raises:
            SecurityException: Only if ENFORCE_KEY_FILE_PERMISSIONS is true and permissions are bad.
                               Other errors are logged and return None.
        """
        key_path_setting = settings.KEY_FILE_PATH
        if not key_path_setting:
            logger.error(
                "KEY_MANAGEMENT_METHOD is 'file' but KEY_FILE_PATH is not set in settings."
            )
            return None

        # --- Robust Logging & Reading ---
        key_path = None  # Define outside try block for use in logging
        try:
            # Resolve to absolute path for clarity in logs
            key_path = os.path.abspath(key_path_setting)
            logger.info(
                f"Attempting to read key from file path: '{key_path}' (from setting: '{key_path_setting}')"
            )

            if not os.path.exists(key_path):
                logger.error(f"Key file does not exist at path: '{key_path}'")
                return None
            if not os.path.isfile(key_path):
                logger.error(f"Path exists but is not a file: '{key_path}'")
                return None

            # Check permissions
            logger.debug(f"Checking permissions for key file: '{key_path}'")
            try:
                file_stat = os.stat(key_path)
                permissions = stat.S_IMODE(file_stat.st_mode)
                permissions_octal = oct(permissions)
                logger.debug(f"Key file permissions detected: {permissions_octal}")

                # Check if group or others have any permissions on Unix-like systems
                is_insecure = False
                if hasattr(os, "getuid"):  # Basic check for Unix-like
                    # Check if group or other has *any* permission bit set
                    if permissions & (stat.S_IRWXG | stat.S_IRWXO):
                        is_insecure = True
                # Add more platform-specific checks if needed (e.g., Windows ACLs)

                if is_insecure:
                    logger.warning(
                        f"Key file '{key_path}' has potentially unsafe permissions: {permissions_octal}"
                    )
                    if settings.ENFORCE_KEY_FILE_PERMISSIONS:
                        logger.error(
                            "Permission enforcement is ON. Raising SecurityException."
                        )
                        raise SecurityException(
                            f"Key file '{key_path}' has unsafe permissions ({permissions_octal})"
                        )
                    else:
                        logger.info(
                            "Permission enforcement is OFF. Proceeding despite unsafe permissions."
                        )
                else:
                    logger.debug(
                        f"Key file permissions appear secure ({permissions_octal})."
                    )

            except OSError as perm_e:
                logger.error(
                    f"Could not check permissions for key file '{key_path}': {perm_e}"
                )
                # If we can't check permissions, assume failure if enforcement is on
                if settings.ENFORCE_KEY_FILE_PERMISSIONS:
                    logger.error(
                        "Permission enforcement is ON. Raising SecurityException due to check failure."
                    )
                    raise SecurityException(
                        f"Could not verify permissions for key file '{key_path}': {perm_e}"
                    )
                else:
                    logger.info(
                        "Permission enforcement is OFF. Proceeding despite permission check failure."
                    )

            # Read the key from the file
            logger.debug(f"Opening and reading key file: '{key_path}'")
            with open(key_path, "r", encoding="utf-8") as f:
                # Read the key and strip leading/trailing whitespace (like newlines)
                key = f.read().strip()

            if not key:
                logger.error(
                    f"Key file '{key_path}' was found but is empty or contains only whitespace."
                )
                return None

            # Basic validation (e.g., check length if expecting hex)
            # Adjust expected length if your keys are different
            expected_len = 64
            if len(key) != expected_len:
                logger.warning(
                    f"Key read from '{key_path}' has unexpected length ({len(key)} chars). Expected {expected_len} hex chars."
                )
                # Depending on strictness, you might return None here

            logger.info(f"Successfully read key from file: '{key_path}'")
            return key

        except FileNotFoundError:
            # This case is technically covered by os.path.exists, but good practice
            logger.error(
                f"Key file not found at resolved path: '{key_path or key_path_setting}'"
            )
            return None
        except IOError as io_e:
            logger.error(
                f"IOError reading key file '{key_path or key_path_setting}': {io_e}"
            )
            return None
        except OSError as os_e:
            logger.error(
                f"OSError accessing key file '{key_path or key_path_setting}': {os_e}"
            )
            return None
        except SecurityException:
            # Re-raise SecurityExceptions from permission checks if enforcement is on
            raise
        except Exception as e:
            # Catch any other unexpected errors during file access
            logger.exception(
                f"Unexpected error reading key file '{key_path or key_path_setting}': {e}"
            )
            return None
        # --- End Robust Logging & Reading ---

    @staticmethod
    def _get_key_from_environment() -> Optional[str]:  # Changed return type
        """
        Retrieve encryption key from environment variable.
        """
        env_var = settings.KEY_ENVIRONMENT_VARIABLE
        if not env_var:
            logger.error(
                "KEY_MANAGEMENT_METHOD is 'environment' but KEY_ENVIRONMENT_VARIABLE is not set."
            )
            return None  # Return None on config error

        logger.info(f"Attempting to read key from environment variable: '{env_var}'")
        key = os.environ.get(env_var)

        if not key:
            logger.error(f"Environment variable '{env_var}' not set or is empty.")
            return None  # Return None if not found

        logger.info(f"Successfully read key from environment variable: '{env_var}'")
        return key.strip()  # Strip whitespace

    # --- Keep AWS, Azure, GCP methods as they were ---
    # (Add similar robust logging/error handling to them if needed)
    @staticmethod
    def _get_key_from_aws() -> str:
        """
        Retrieve encryption key from AWS Secrets Manager.
        Requires: boto3 library installed, AWS credentials configured
        """
        logger.info("Attempting to retrieve key from AWS Secrets Manager...")
        try:
            import boto3

            secret_name = settings.AWS_SECRET_NAME
            region = settings.AWS_REGION
            if not secret_name or not region:
                raise SecurityException(
                    "AWS_SECRET_NAME and AWS_REGION must be set for AWS method."
                )

            client = boto3.client(service_name="secretsmanager", region_name=region)
            logger.debug(f"Requesting secret '{secret_name}' from region '{region}'")
            response = client.get_secret_value(SecretId=secret_name)

            if "SecretString" in response:
                secret = response["SecretString"]
                logger.debug("Secret retrieved as SecretString")
                try:
                    secret_dict = json.loads(secret)
                    key_field = settings.AWS_SECRET_KEY_FIELD
                    if key_field and key_field in secret_dict:
                        key = secret_dict[key_field]
                        logger.info(
                            f"Successfully extracted key from field '{key_field}' in AWS secret."
                        )
                        return key
                    else:
                        logger.info(
                            "AWS secret is JSON, but key field not specified or found. Returning entire JSON string."
                        )
                        return secret  # Return whole JSON string if field not specified/found
                except json.JSONDecodeError:
                    logger.info(
                        "AWS secret is not JSON. Returning secret string directly."
                    )
                    return secret  # Not JSON, return as is
            elif "SecretBinary" in response:
                import base64

                logger.debug("Secret retrieved as SecretBinary. Decoding from base64.")
                binary_secret = response["SecretBinary"]
                key = base64.b64decode(binary_secret).decode("utf-8")
                logger.info("Successfully decoded binary secret from AWS.")
                return key
            else:
                logger.error(
                    f"No SecretString or SecretBinary found in AWS response for '{secret_name}'"
                )
                raise SecurityException(
                    f"Invalid response from AWS Secrets Manager for secret '{secret_name}'"
                )

        except ImportError:
            logger.error(
                "boto3 library not installed, required for AWS Secrets Manager"
            )
            raise SecurityException(
                "boto3 library not installed, required for AWS Secrets Manager"
            )
        except Exception as e:
            logger.exception(
                f"Error retrieving key from AWS Secrets Manager: {e}"
            )  # Use logger.exception for traceback
            raise SecurityException(f"Failed to retrieve key from AWS: {e}")

    @staticmethod
    def _get_key_from_azure() -> str:
        """
        Retrieve encryption key from Azure Key Vault.
        Requires: azure-keyvault-secrets, azure-identity libraries installed, Azure credentials configured
        """
        logger.info("Attempting to retrieve key from Azure Key Vault...")
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            vault_url = settings.AZURE_VAULT_URL
            secret_name = settings.AZURE_SECRET_NAME
            if not vault_url or not secret_name:
                raise SecurityException(
                    "AZURE_VAULT_URL and AZURE_SECRET_NAME must be set for Azure method."
                )

            logger.debug(f"Authenticating with Azure for Key Vault: '{vault_url}'")
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=vault_url, credential=credential)

            logger.debug(f"Requesting secret '{secret_name}' from Azure Key Vault")
            retrieved_secret = client.get_secret(secret_name)

            if not retrieved_secret or not retrieved_secret.value:
                logger.error(
                    f"Secret '{secret_name}' retrieved from Azure Key Vault but value is empty."
                )
                raise SecurityException(
                    f"Secret '{secret_name}' retrieved from Azure Key Vault but value is empty."
                )

            logger.info(
                f"Successfully retrieved secret '{secret_name}' from Azure Key Vault."
            )
            return retrieved_secret.value

        except ImportError:
            logger.error(
                "azure-keyvault-secrets and azure-identity libraries not installed, required for Azure Key Vault"
            )
            raise SecurityException(
                "azure libraries not installed, required for Azure Key Vault"
            )
        except Exception as e:
            logger.exception(f"Error retrieving key from Azure Key Vault: {e}")
            raise SecurityException(f"Failed to retrieve key from Azure: {e}")

    @staticmethod
    def _get_key_from_gcp() -> str:
        """
        Retrieve encryption key from Google Secret Manager.
        Requires: google-cloud-secret-manager library installed, GCP credentials configured
        """
        logger.info("Attempting to retrieve key from Google Secret Manager...")
        try:
            from google.cloud import secretmanager

            project_id = settings.GCP_PROJECT_ID
            secret_id = settings.GCP_SECRET_ID
            version_id = (
                settings.GCP_SECRET_VERSION or "latest"
            )  # Default to latest if not specified
            if not project_id or not secret_id:
                raise SecurityException(
                    "GCP_PROJECT_ID and GCP_SECRET_ID must be set for GCP method."
                )

            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

            logger.debug(
                f"Requesting secret version '{name}' from Google Secret Manager"
            )
            response = client.access_secret_version(request={"name": name})

            if not response or not response.payload or not response.payload.data:
                logger.error(
                    f"Invalid or empty payload received from Google Secret Manager for '{name}'"
                )
                raise SecurityException(
                    f"Invalid or empty payload received from Google Secret Manager for '{name}'"
                )

            key = response.payload.data.decode("UTF-8")
            logger.info(
                f"Successfully retrieved secret '{secret_id}' version '{version_id}' from Google Secret Manager."
            )
            return key

        except ImportError:
            logger.error(
                "google-cloud-secret-manager library not installed, required for GCP Secret Manager"
            )
            raise SecurityException(
                "google-cloud-secret-manager library not installed, required for GCP Secret Manager"
            )
        except Exception as e:
            logger.exception(f"Error retrieving key from Google Secret Manager: {e}")
            raise SecurityException(f"Failed to retrieve key from GCP: {e}")

    # --- create_key_file method can remain as is ---
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
        key_file_setting = settings.KEY_FILE_PATH
        if not key_file_setting:
            raise SecurityException(
                "Cannot create key file: KEY_FILE_PATH is not set in settings."
            )
        key_file = os.path.abspath(key_file_setting)  # Use absolute path

        try:
            # Create directory if it doesn't exist, with secure permissions (owner only)
            key_dir = os.path.dirname(key_file)
            # Check if dir exists, if not create with 0o700
            if not os.path.isdir(key_dir):
                logger.info(
                    f"Creating key directory: '{key_dir}' with secure permissions (0o700)"
                )
                os.makedirs(key_dir, mode=0o700, exist_ok=True)
            else:
                # Optionally check/set permissions on existing directory
                # os.chmod(key_dir, 0o700)
                pass

            # Write the key to the file (using 'w' truncates existing file)
            logger.debug(f"Writing key to file: '{key_file}'")
            with open(key_file, "w", encoding="utf-8") as f:
                f.write(key)

            # Set secure permissions (0400 - read-only by owner)
            logger.debug(f"Setting permissions to 0o400 for key file: '{key_file}'")
            os.chmod(key_file, 0o400)

            logger.info(f"Successfully created/updated secure key file at {key_file}")
            return key_file

        except Exception as e:
            logger.exception(f"Error creating/securing key file '{key_file}': {e}")
            raise SecurityException(f"Failed to create/secure key file: {e}")
