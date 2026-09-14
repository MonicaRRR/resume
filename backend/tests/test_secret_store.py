from unittest.mock import Mock
import os
import sys
from uuid import uuid4

import pytest
from keyring.errors import PasswordDeleteError

from resume_mvp.secret_store import MacOSKeychainStore, provider_key_account


def test_delete_does_not_hide_keychain_failure() -> None:
    store = object.__new__(MacOSKeychainStore)
    store._backend = Mock()
    store._backend.delete_password.side_effect = PasswordDeleteError("denied")
    with pytest.raises(PasswordDeleteError):
        store.delete("test-account")


def test_secret_accounts_normalize_origin_and_separate_ports() -> None:
    assert provider_key_account("https://API.example:443/v1/") == provider_key_account("https://api.example/v2")
    assert provider_key_account("https://api.example:8443") != provider_key_account("https://api.example")
    assert provider_key_account("http://api.example") != provider_key_account("https://api.example")


@pytest.mark.integration
@pytest.mark.skipif(
    sys.platform != "darwin" or os.environ.get("RESUME_MVP_KEYCHAIN_TEST") != "1",
    reason="Opt in to native Keychain smoke test; uses only a unique dummy credential",
)
def test_native_keychain_roundtrip() -> None:
    account = f"selftest:{uuid4()}"
    store = MacOSKeychainStore()
    try:
        store.set(account, "resume-mvp-dummy-credential")
        assert MacOSKeychainStore().get(account) == "resume-mvp-dummy-credential"
    finally:
        store.delete(account)
    assert MacOSKeychainStore().get(account) is None
