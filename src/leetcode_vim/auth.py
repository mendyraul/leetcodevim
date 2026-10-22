from __future__ import annotations

from dataclasses import dataclass
import json

from .config import Config, save_config

SERVICE_NAME = "leetcode-vim"


@dataclass
class AuthResult:
    session: str | None
    csrf: str | None


class AuthImportError(RuntimeError):
    pass


def _keyring():
    try:
        import keyring
    except Exception:
        return None
    return keyring


def import_from_browser(browser: str, domain: str) -> AuthResult:
    try:
        import browser_cookie3
    except Exception as exc:
        raise AuthImportError("browser-cookie3 is not available.") from exc

    browser = browser.lower()
    loaders = {
        "chrome": browser_cookie3.chrome,
        "chromium": browser_cookie3.chromium,
        "brave": browser_cookie3.brave,
        "edge": browser_cookie3.edge,
        "firefox": browser_cookie3.firefox,
    }
    if browser not in loaders:
        raise AuthImportError(f"Unsupported browser: {browser}")
    try:
        jar = loaders[browser](domain_name=domain)
    except Exception as exc:
        raise AuthImportError("Failed to read browser cookies.") from exc

    session = None
    csrf = None
    for cookie in jar:
        if cookie.name == "LEETCODE_SESSION":
            session = cookie.value
        elif cookie.name == "csrftoken":
            csrf = cookie.value
    if not session:
        raise AuthImportError("LEETCODE_SESSION not found in browser cookies.")
    return AuthResult(session=session, csrf=csrf)


def load_auth(config: Config) -> AuthResult:
    keyring = _keyring()
    session = None
    csrf = None
    if keyring:
        try:
            bundle = keyring.get_password(SERVICE_NAME, 'AUTH_BUNDLE')
            if bundle:
                data = json.loads(bundle)
                return AuthResult(session=data['session'], csrf=data.get('csrf'))
            session = keyring.get_password(SERVICE_NAME, "LEETCODE_SESSION")
            csrf = keyring.get_password(SERVICE_NAME, "LEETCODE_CSRF")
        except Exception:
            session = None
            csrf = None
    return AuthResult(session=session or config.session, csrf=csrf or config.csrf)


def save_auth(config: Config, session: str, csrf: str | None, allow_file: bool = False) -> None:
    keyring = _keyring()
    if keyring:
        try:
            keyring.set_password(SERVICE_NAME, 'AUTH_BUNDLE', json.dumps({'session': session, 'csrf': csrf}))
            config.session = config.csrf = None
            save_config(config)
            return
        except Exception:
            pass
    if not allow_file:
        raise AuthImportError('Secure credential storage unavailable. Use the editor session or --allow-file explicitly.')
    config.session, config.csrf = session, csrf
    save_config(config)


def clear_auth(config: Config) -> None:
    keyring = _keyring()
    if keyring:
        for name in ("AUTH_BUNDLE", "LEETCODE_SESSION", "LEETCODE_CSRF"):
            try:
                keyring.delete_password(SERVICE_NAME, name)
            except Exception:
                pass
    config.session = None
    config.csrf = None
    save_config(config)
