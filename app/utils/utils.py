import os
import re
import tempfile
import time
from html.parser import HTMLParser
from urllib.parse import urlparse


# Chrome/Selenium net-stack error tokens that indicate a lost or broken internet
# connection (not a page- or app-level failure), so a navigation that hits one is
# worth retrying once connectivity returns. Mirrors the Go browser connErrCodes.
UTIL_CONN_ERR_CODES = (
    "ERR_INTERNET_DISCONNECTED",
    "ERR_NETWORK_CHANGED",
    "ERR_CONNECTION_TIMED_OUT",
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_CLOSED",
    "ERR_CONNECTION_REFUSED",
    "ERR_CONNECTION_ABORTED",
    "ERR_CONNECTION_FAILED",
    "ERR_NAME_NOT_RESOLVED",
    "ERR_NAME_RESOLUTION_FAILED",
    "ERR_ADDRESS_UNREACHABLE",
    "ERR_PROXY_CONNECTION_FAILED",
    "ERR_QUIC_PROTOCOL_ERROR",
    "ERR_SOCKET_NOT_CONNECTED",
    "ERR_TIMED_OUT",
)

# How long a navigation keeps retrying while the connection is down before the run
# gives up (a period of time, not a fixed count), and the wait between attempts.
UTIL_CONN_RETRY_BUDGET = 180  # seconds (3 minutes)
UTIL_CONN_RETRY_INTERVAL = 5  # seconds


class UtilConnectionLostError(BaseException):
    """
    Raised by util_safe_get once the internet connection has stayed down past
    UTIL_CONN_RETRY_BUDGET.

    It subclasses BaseException (like KeyboardInterrupt) on purpose: the fetch
    loops wrap each item in a broad `except Exception`, and this must NOT be
    swallowed there. Instead it propagates up to main(), which stops the run
    cleanly — every completed item is already saved atomically — rather than
    pushing on to the next item against a dead connection.
    """


def util_is_connection_error(message: str) -> bool:
    """Return True if message looks like a transient internet-connectivity error."""
    if not message:
        return False
    return any(code in message for code in UTIL_CONN_ERR_CODES)


def util_safe_get(driver, url: str) -> None:
    """
    driver.get(url) that survives a flaky internet connection.

    While the navigation fails with a connectivity error (one of
    UTIL_CONN_ERR_CODES), it keeps retrying until the connection recovers or
    UTIL_CONN_RETRY_BUDGET elapses, then raises UtilConnectionLostError so the run
    stops gracefully. Any other error (a real page/app failure) is re-raised at
    once. A Ctrl+C during the wait aborts immediately (KeyboardInterrupt).
    """
    deadline = time.monotonic() + UTIL_CONN_RETRY_BUDGET
    warned = False
    while True:
        try:
            driver.get(url)
            return
        except UtilConnectionLostError:
            raise
        except Exception as error:
            if not util_is_connection_error(str(error)):
                raise
            if not warned:
                print(f"Internet connection error ({error}) — retrying for up to {UTIL_CONN_RETRY_BUDGET}s…")
                warned = True
            if time.monotonic() >= deadline:
                print(f"Internet connection still down after {UTIL_CONN_RETRY_BUDGET}s — giving up.")
                raise UtilConnectionLostError(str(error))
            time.sleep(UTIL_CONN_RETRY_INTERVAL)


def util_atomic_write_text(path, text: str, encoding: str = 'utf-8', newline: str = '\n') -> None:
    """
    Write text to path atomically.

    Writes to a temp file in the same directory, fsyncs it, then os.replace()s
    it over the target. The replace is atomic on POSIX, so an interrupt (Ctrl+C)
    or crash can never leave a half-written file — the path always holds either
    its previous contents or the complete new contents. Parent directories are
    created as needed.
    """
    path = os.fspath(path)
    directory = os.path.dirname(path) or '.'
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix='.tmp-')
    try:
        with os.fdopen(fd, 'w', encoding=encoding, newline=newline) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def util_portal_and_id(value: str):
    """
    Resolve a fetch target into a (portal, id) pair.

    Accepts either a bare id ("53") or a full URL
    ("https://partner.skills.google/paths/85"). For a URL, the portal is
    inferred from the host and the id is the last path segment. For a bare id,
    the portal is returned as None so the caller can apply its own default.

    :return: (portal_or_None, id_str)
    """
    from config.settings import portal_from_host

    if not value:
        return None, value

    # Treat anything with a scheme or a skills.google host as a URL.
    looks_like_url = "://" in value or "skills.google" in value.lower()
    if looks_like_url:
        parsed = urlparse(value if "://" in value else f"https://{value}")
        portal = portal_from_host(parsed.netloc)
        # Last non-empty path segment is the id.
        segments = [seg for seg in parsed.path.split('/') if seg]
        entity_id = segments[-1] if segments else ""
        return portal, entity_id

    return None, value.strip()

class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)

def util_replace_special_chars(text_to_replace: str | None) -> str:
    """
    Remove special characters from the given text.
    This to make sure when a path is created, it doesn't contain any special characters.

    :param text_to_replace: The text to process.
    :return str: The processed text without special characters.
    """
    if not text_to_replace:
        return ""
    return (text_to_replace
            .replace(',', '')
            .replace('/', ' ')
            .replace(':', '')
            .replace(' - ', ' ')
            .replace(' ', '-'))


def util_replace_quote_marks(text_to_replace: str) -> str:
    """
    Replace the common quotation marks with their Unicode equivalents.

    :rtype: str
    :param text_to_replace: The text to process.
    :return: The processed text with quotation marks replaced.
    :note: This function replaces the following characters:
        - “ (U+201C) with " (U+0022)
        - ” (U+201D) with " (U+0022)
        - ’ (U+2019) with ' (U+0027)
        - ‘ (U+2018) with ' (U+0027)
    Reference: https://www.babelstone.co.uk/Unicode/whatisit.html
    """

    if not text_to_replace:
        return ""
    return (text_to_replace
            .replace(u'\u201C', u"\u0022")  # “ to "
            .replace(u'\u201D', u'\u0022')  # ” to "
            .replace(u'\u2019', u"\u0027")  # ’ to '
            .replace(u'\u2018', u"\u0027")  # ‘ to '
            )


def util_strip_html_tags(text: str) -> str:
    """
    Strip out HTML tags from the given text.\n

    :param text: The text to process.
    :return: The text without HTML tags.
    """
    stripper = HTMLStripper()
    stripper.feed(text)
    return stripper.get_data()


def util_ensure_authenticated(driver, url: str, entity_desc: str = "") -> bool:
    """
    Check if the current webdriver page redirected to sign-in, and prompt user until authenticated.
    Returns True if authenticated, False if aborted or webdriver missing.
    """
    if not driver:
        return False

    while "sign_in" in driver.current_url:
        msg = f" for {entity_desc}" if entity_desc else ""
        print(f"\n\033[93m[!] Authentication required{msg}.\033[0m")
        print("Please sign in to the browser window if you haven't.")
        try:
            input("Press Enter after you have signed in and the page is loaded to continue... ")
        except (KeyboardInterrupt, EOFError):
            print("\n\033[91mAborted authentication.\033[0m")
            return False
        util_safe_get(driver, url)
        
        if "sign_in" in driver.current_url:
            print("\n\033[91m[!] Still on sign-in page. Please ensure login is complete before pressing Enter.\033[0m")
    return True
