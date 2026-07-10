import os
import tempfile
from selenium.webdriver.chrome.webdriver import WebDriver
from typing_extensions import override
from html.parser import HTMLParser
from urllib.parse import urlparse
from pathlib import Path as PathlibPath


def util_atomic_write_text(path: str | PathlibPath, text: str, encoding: str = 'utf-8', newline: str = '\n') -> None:
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
            _ = f.write(text)
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
        self.fed: list[str] = []

    @override
    def handle_data(self, data: str) -> None:
        self.fed.append(data)

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


def util_ensure_authenticated(driver: WebDriver | None, url: str, entity_desc: str = "") -> bool:
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
            _ = input("Press Enter after you have signed in and the page is loaded to continue... ")
        except (KeyboardInterrupt, EOFError):
            print("\n\033[91mAborted authentication.\033[0m")
            return False
        driver.get(url)

        if "sign_in" in driver.current_url:
            print("\n\033[91m[!] Still on sign-in page. Please ensure login is complete before pressing Enter.\033[0m")
    return True
