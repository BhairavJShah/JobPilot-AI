"""
Secure credential storage using OS keyring.
Falls back to in-memory cache if keyring is unavailable.
Passwords are never stored as plaintext in config.json.
"""
import os

# Service name used to namespace credentials in the OS keyring
_SERVICE_NAME = "JobPilot-AI"
_keyring_available = False

try:
    import keyring
    # Quick test to verify keyring backend is functional
    keyring.get_credential(_SERVICE_NAME, "")
    _keyring_available = True
except Exception:
    _keyring_available = False

# In-memory fallback cache (populated from CONFIG on first access)
_mem_cache = {}


def store_credential(key, value):
    """Store a credential securely. Key format: 'accounts.naukri_pass', 'smtp.password', etc."""
    if _keyring_available:
        try:
            if value:
                keyring.set_password(_SERVICE_NAME, key, value)
            else:
                # Delete empty credentials
                try:
                    keyring.delete_password(_SERVICE_NAME, key)
                except keyring.errors.PasswordDeleteError:
                    pass
            return
        except Exception:
            pass
    # Fallback to in-memory
    _mem_cache[key] = value


def get_credential(key, fallback=""):
    """Retrieve a credential. Returns fallback if not found."""
    if _keyring_available:
        try:
            val = keyring.get_password(_SERVICE_NAME, key)
            if val is not None:
                return val
        except Exception:
            pass
    # Fallback to in-memory cache
    return _mem_cache.get(key, fallback)


def migrate_plaintext_credentials(config):
    """
    One-time migration: move any plaintext passwords from config dict
    into the secure store, then blank them in config.
    Returns True if any credentials were migrated.
    """
    migrated = False

    # All sensitive fields: (config_section, config_key, credential_store_key)
    sensitive_fields = [
        ("accounts", "indeed_pass", "accounts.indeed_pass"),
        ("accounts", "naukri_pass", "accounts.naukri_pass"),
        ("accounts", "linkedin_pass", "accounts.linkedin_pass"),
        ("smtp", "password", "smtp.password"),
        ("settings", "cloud_ai_api_key", "settings.cloud_ai_api_key"),
        ("settings", "cloud_ai_password", "settings.cloud_ai_password"),
        ("settings", "cloud_ai_username", "settings.cloud_ai_username"),
    ]

    for section, key, store_key in sensitive_fields:
        if section in config and key in config[section]:
            val = config[section][key]
            if val:  # Only migrate non-empty values
                store_credential(store_key, val)
                config[section][key] = ""  # Blank out from config
                migrated = True

    return migrated


def is_keyring_available():
    """Check if the OS keyring backend is functional."""
    return _keyring_available
