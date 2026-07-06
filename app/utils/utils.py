import re
from html.parser import HTMLParser

class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)

def util_replace_special_chars(text_to_replace: str) -> str:
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
        driver.get(url)
        
        if "sign_in" in driver.current_url:
            print("\n\033[91m[!] Still on sign-in page. Please ensure login is complete before pressing Enter.\033[0m")
    return True
