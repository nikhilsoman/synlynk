"""Host-local storage for the oMLX API credential.

The value is stored only in macOS Keychain. No subprocess is used, so the
credential never appears in command arguments or a child environment.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path


SERVICE = "com.synlynk.omlx"
ACCOUNT = "local-runtime"


class CredentialError(RuntimeError):
    """Base class for safe, non-secret credential failures."""


class CredentialUnavailable(CredentialError):
    """Credential is missing or Keychain cannot be accessed right now."""


class UnsupportedCredentialPlatform(CredentialError):
    """Keychain credential operations are supported only on macOS."""


class _SecurityKeychain:
    ERR_ITEM_NOT_FOUND = -25300
    ERR_DUPLICATE_ITEM = -25299
    ERR_INTERACTION_NOT_ALLOWED = -25308

    def __init__(self):
        security_path = ctypes.util.find_library("Security")
        foundation_path = ctypes.util.find_library("CoreFoundation")
        if not security_path or not foundation_path:
            raise CredentialUnavailable("macOS Keychain is unavailable")
        self.security = ctypes.CDLL(security_path)
        self.cf = ctypes.CDLL(foundation_path)
        self._configure_functions()

    def _configure_functions(self):
        cf = self.cf
        sec = self.security
        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFDataCreate.restype = ctypes.c_void_p
        cf.CFDataCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        cf.CFDataGetLength.restype = ctypes.c_long
        cf.CFDataGetLength.argtypes = [ctypes.c_void_p]
        cf.CFDataGetBytePtr.restype = ctypes.POINTER(ctypes.c_ubyte)
        cf.CFDataGetBytePtr.argtypes = [ctypes.c_void_p]
        cf.CFDictionaryCreateMutable.restype = ctypes.c_void_p
        cf.CFDictionaryCreateMutable.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p]
        cf.CFDictionarySetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        sec.SecItemAdd.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        sec.SecItemAdd.restype = ctypes.c_int32
        sec.SecItemUpdate.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        sec.SecItemUpdate.restype = ctypes.c_int32
        sec.SecItemCopyMatching.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        sec.SecItemCopyMatching.restype = ctypes.c_int32
        sec.SecItemDelete.argtypes = [ctypes.c_void_p]
        sec.SecItemDelete.restype = ctypes.c_int32

    def _constant(self, name):
        try:
            return ctypes.c_void_p.in_dll(self.security, name).value
        except ValueError as exc:
            raise CredentialUnavailable("macOS Keychain configuration is unavailable") from exc

    def _cf_constant(self, name):
        try:
            return ctypes.c_void_p.in_dll(self.cf, name).value
        except ValueError as exc:
            raise CredentialUnavailable("macOS Keychain configuration is unavailable") from exc

    def _string(self, value):
        # kCFStringEncodingUTF8 = 0x08000100.
        result = self.cf.CFStringCreateWithCString(None, value.encode("utf-8"), 0x08000100)
        if not result:
            raise CredentialUnavailable("could not prepare Keychain request")
        return ctypes.c_void_p(result)

    def _dict(self, pairs):
        # NULL callbacks use pointer identity. All objects stay strongly
        # referenced until the Security.framework call has completed.
        result = self.cf.CFDictionaryCreateMutable(None, len(pairs), None, None)
        if not result:
            raise CredentialUnavailable("could not prepare Keychain request")
        refs = [ctypes.c_void_p(result)]
        for key, value in pairs:
            key_ref = key if isinstance(key, ctypes.c_void_p) else ctypes.c_void_p(key)
            value_ref = value if isinstance(value, ctypes.c_void_p) else ctypes.c_void_p(value)
            if isinstance(value, ctypes.c_void_p):
                refs.append(value_ref)
            self.cf.CFDictionarySetValue(refs[0], key_ref, value_ref)
        return refs[0], refs

    def _base_pairs(self):
        return [
            (self._constant("kSecClass"), self._constant("kSecClassGenericPassword")),
            (self._constant("kSecAttrService"), self._string(SERVICE)),
            (self._constant("kSecAttrAccount"), self._string(ACCOUNT)),
        ]

    def _release(self, refs):
        for ref in refs:
            if ref:
                self.cf.CFRelease(ref)

    def add(self, service, account, value, accessibility):
        pairs = self._base_pairs()
        data_buffer = ctypes.create_string_buffer(value)
        data = ctypes.c_void_p(self.cf.CFDataCreate(None, data_buffer, len(value)))
        pairs.extend([
            (self._constant("kSecValueData"), data),
            (self._constant("kSecAttrAccessible"), self._constant("kSecAttrAccessibleWhenUnlockedThisDeviceOnly")),
        ])
        query, refs = self._dict(pairs)
        try:
            status = self.security.SecItemAdd(query, None)
        finally:
            self._release(refs)
        self._raise_status(status, allow_duplicate=True)

    def update(self, service, account, value, accessibility):
        query, query_refs = self._dict(self._base_pairs())
        data_buffer = ctypes.create_string_buffer(value)
        data = ctypes.c_void_p(self.cf.CFDataCreate(None, data_buffer, len(value)))
        attrs, attrs_refs = self._dict([
            (self._constant("kSecValueData"), data),
            (self._constant("kSecAttrAccessible"), self._constant("kSecAttrAccessibleWhenUnlockedThisDeviceOnly")),
        ])
        try:
            status = self.security.SecItemUpdate(query, attrs)
        finally:
            self._release(query_refs)
            self._release(attrs_refs)
        self._raise_status(status)

    def get(self, service, account):
        pairs = self._base_pairs()
        pairs.extend([
            (self._constant("kSecReturnData"), self._cf_constant("kCFBooleanTrue")),
            (self._constant("kSecMatchLimit"), self._constant("kSecMatchLimitOne")),
            (self._constant("kSecUseAuthenticationUI"), self._constant("kSecUseAuthenticationUIFail")),
        ])
        query, refs = self._dict(pairs)
        result = ctypes.c_void_p()
        try:
            status = self.security.SecItemCopyMatching(query, ctypes.byref(result))
            self._raise_status(status, allow_missing=True)
            if status == self.ERR_ITEM_NOT_FOUND:
                raise FileNotFoundError
            length = self.cf.CFDataGetLength(result)
            raw = ctypes.string_at(self.cf.CFDataGetBytePtr(result), length)
            return raw.decode("utf-8")
        finally:
            self._release(refs)
            if result:
                self.cf.CFRelease(result)

    def delete(self, service, account):
        query, refs = self._dict(self._base_pairs())
        try:
            status = self.security.SecItemDelete(query)
        finally:
            self._release(refs)
        self._raise_status(status, allow_missing=True)

    def _raise_status(self, status, *, allow_missing=False, allow_duplicate=False):
        if status == 0 or (allow_missing and status == self.ERR_ITEM_NOT_FOUND):
            return
        if allow_duplicate and status == self.ERR_DUPLICATE_ITEM:
            raise FileExistsError
        if status == self.ERR_ITEM_NOT_FOUND:
            raise FileNotFoundError
        raise PermissionError("Keychain item is unavailable")


class LocalCredentialStore:
    """Read oMLX's persistent API key; retain Keychain only for legacy commands."""

    def __init__(self, adapter=None, platform=None, *, settings_path=None,
                 environ=None, home=None, bootstrap_path=None):
        self._platform = platform or sys.platform
        self._adapter = adapter
        self._settings_path = Path(settings_path).expanduser() if settings_path else None
        self._environ = environ
        self._home = Path(home).expanduser() if home else Path.home()
        self._bootstrap_path = Path(bootstrap_path) if bootstrap_path else (
            self._home / "Library" / "Application Support" / "oMLX" / "base-path"
        )

    def _active_settings_path(self) -> Path:
        if self._settings_path is not None:
            return self._settings_path
        environ = os.environ if self._environ is None else self._environ
        bootstrap_readable = False
        try:
            base_path = self._bootstrap_path.read_text(encoding="utf-8").strip()
            bootstrap_readable = True
        except OSError:
            base_path = ""
        if base_path:
            base = Path(base_path).expanduser().resolve()
        elif bootstrap_readable:
            # The installed wrapper assigns the empty bootstrap value before
            # launching Python, so an inherited OMLX_BASE_PATH is cleared.
            base = self._home / ".omlx"
        else:
            base_path = environ.get("OMLX_BASE_PATH", "")
            base = Path(base_path).expanduser().resolve() if base_path else self._home / ".omlx"
        return base / "settings.json"

    def _keychain(self):
        if self._platform != "darwin":
            raise UnsupportedCredentialPlatform("Local Keychain credentials require macOS")
        if self._adapter is None:
            self._adapter = _SecurityKeychain()
        return self._adapter

    def import_from_environment(self, environ: Mapping[str, str], *, replace: bool = False) -> None:
        value = environ.get("OPENAI_API_KEY", "").strip()
        if not value:
            raise CredentialUnavailable("OPENAI_API_KEY is not set")
        keychain = self._keychain()
        try:
            if replace:
                try:
                    keychain.update(SERVICE, ACCOUNT, value.encode("utf-8"), "WhenUnlockedThisDeviceOnly")
                except FileNotFoundError:
                    keychain.add(SERVICE, ACCOUNT, value.encode("utf-8"), "WhenUnlockedThisDeviceOnly")
            else:
                keychain.add(SERVICE, ACCOUNT, value.encode("utf-8"), "WhenUnlockedThisDeviceOnly")
        except FileExistsError as exc:
            raise CredentialUnavailable("credential already exists; use --replace to change it") from exc
        except Exception as exc:
            if isinstance(exc, CredentialError):
                raise
            raise CredentialUnavailable("Keychain is unavailable") from None

    def get(self) -> str:
        try:
            with self._active_settings_path().open(encoding="utf-8") as stream:
                settings = json.load(stream)
            auth = settings.get("auth") if isinstance(settings, dict) else None
            value = auth.get("api_key") if isinstance(auth, dict) else None
            if not isinstance(value, str) or not value.strip():
                raise CredentialUnavailable("oMLX settings API key is not configured")
            return value
        except Exception as exc:
            if isinstance(exc, CredentialError):
                raise
            raise CredentialUnavailable("oMLX settings credential is unavailable") from None

    def delete(self) -> None:
        try:
            self._keychain().delete(SERVICE, ACCOUNT)
        except FileNotFoundError:
            return
        except UnsupportedCredentialPlatform:
            raise
        except Exception as exc:
            if isinstance(exc, CredentialError):
                raise
            raise CredentialUnavailable("Keychain credential is unavailable") from None

    def is_configured(self) -> bool:
        try:
            self.get()
            return True
        except CredentialUnavailable:
            return False
