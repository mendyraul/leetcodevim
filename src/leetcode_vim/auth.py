from __future__ import annotations

from dataclasses import dataclass

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
            session = keyring.get_password(SERVICE_NAME, "LEETCODE_SESSION")
            csrf = keyring.get_password(SERVICE_NAME, "LEETCODE_CSRF")
        except Exception:
            session = None
            csrf = None
    return AuthResult(session=session or config.session, csrf=csrf or config.csrf)


def save_auth(config: Config, session: str, csrf: str | None) -> None:
    keyring = _keyring()
    if keyring:
        try:
            keyring.set_password(SERVICE_NAME, "LEETCODE_SESSION", session)
            if csrf:
                keyring.set_password(SERVICE_NAME, "LEETCODE_CSRF", csrf)
            return
        except Exception:
            pass
    config.session = session
    if csrf:
        config.csrf = csrf
    save_config(config)


def clear_auth(config: Config) -> None:
    keyring = _keyring()
    if keyring:
        for name in ("LEETCODE_SESSION", "LEETCODE_CSRF"):
            try:
                keyring.delete_password(SERVICE_NAME, name)
            except Exception:
                pass
    config.session = None
    config.csrf = None
    save_config(config)
