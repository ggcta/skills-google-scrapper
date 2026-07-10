# Description: Configuration file for the project
from pathlib import Path as PathlibPath

# Determine the project root directory
# This to ensure the app can work with relative paths
PROJECT_ROOT = PathlibPath(__file__).parent.parent.parent

# Output: Folder for Markdown files
# Data: Folder for JSON files.
# You can specific path or use the relateve paths here.
OUTPUT_FOLDER_NAME: PathlibPath = PathlibPath (PROJECT_ROOT) / "csbmdvault"
DATA_FOLDER_NAME: PathlibPath = PathlibPath (PROJECT_ROOT) / "data"

# Base URL for the Google Skills website
BASE_URL: str = "https://www.skills.google"
BASE_URL_PATHS: str = f"{BASE_URL}/paths"
API_URL_PATHS: str = f"{BASE_URL}/catalog/list?format%5B%5D=learning_plans"
API_URL_COURSES: str = f"{BASE_URL}/catalog/list?format%5B%5D=courses"
API_URL_LABS: str = f"{BASE_URL}/catalog/list?format%5B%5D=labs"
BASE_URL_LAB: str = f"{BASE_URL}/catalog_lab"
BASE_URL_COURSES: str = f"{BASE_URL}/course_templates"
BASE_URL_PARTNERS: str = "https://partner.skills.google/"

# ---------------------------------------------------------------------------
# Multi-portal support
# ---------------------------------------------------------------------------
# The same content is served from two independent portals with SEPARATE id
# sequences (e.g. partner path 85 == public path 16). An entity's true identity
# is therefore the pair (portal, id), never id alone. Each portal is scoped to
# its own storage root so the two catalogs can never overwrite each other.
DEFAULT_PORTAL: str = "public"

# Shared, portal-agnostic folder for downloaded binaries (documents, etc.),
# organised as materials/<type>/<id>/<files> (type = courses/labs/paths).
# Entity ids are global across portals, so one copy is kept for all portals.
MATERIALS_DIR: str = "materials"

PORTALS: dict[str, dict[str, str]] = {
    "public": {
        "host": "www.skills.google",
        "base": "https://www.skills.google",
        "paths": "https://www.skills.google/paths",
        "courses": "https://www.skills.google/course_templates",
        "lab": "https://www.skills.google/catalog_lab",
        "api_paths": "https://www.skills.google/catalog/list?format%5B%5D=learning_plans",
        "api_courses": "https://www.skills.google/catalog/list?format%5B%5D=courses",
        "api_labs": "https://www.skills.google/catalog/list?format%5B%5D=labs",
    },
    "partner": {
        "host": "partner.skills.google",
        "base": "https://partner.skills.google",
        "paths": "https://partner.skills.google/paths",
        "courses": "https://partner.skills.google/course_templates",
        "lab": "https://partner.skills.google/catalog_lab",
        "api_paths": "https://partner.skills.google/catalog/list?format%5B%5D=learning_plans",
        "api_courses": "https://partner.skills.google/catalog/list?format%5B%5D=courses",
        "api_labs": "https://partner.skills.google/catalog/list?format%5B%5D=labs",
    },
}


def portal_config(portal: str = DEFAULT_PORTAL) -> dict[str, str]:
    """Return the URL config for a portal, falling back to the default."""
    return PORTALS.get(portal, PORTALS[DEFAULT_PORTAL])


def portal_from_host(host: str) -> str:
    """Map a hostname to a portal key. Defaults to the public portal."""
    host = (host or "").lower()
    for portal, cfg in PORTALS.items():
        if cfg["host"] in host:
            return portal
    return DEFAULT_PORTAL

# Webdriver configuration
WEBDRIVER_PROFILE_FOLDER_NAME: PathlibPath = PROJECT_ROOT / '.webdriver_profiles'
WEBDRIVER_OPTIONS_HEADLESS: bool = True

# Constants for the extraction of the course data
COURSE_OUTLINE = "ql-course-outline"
LAB_CONTENT_OUTLINE = "ul.lab-content__outline"
LAB_REVIEW_LAB_ID = "#lab_review_lab_id"
LAB_TITLE = "ql-title-medium"
LD_JSON = "script[type='application/ld+json']"
LINK_URL_A_TAG = "ql-card.document-link a"
META_DESCRIPTION = "meta[name='description']"
PATH_CARDS = "ql-activity-card"
QL_IFRAME = "ql-iframe"
QL_QUIZ = "ql-quiz"
QL_YOUTUBE_VIDEO = "ql-youtube-video"
QUIZ_ITEMS = "quizItems"
QUIZ_VERSION = "quizVersion"
XPATH_QUIZ = "//ql-quiz"
XPATH_START_BUTTON = "//a[@class='start-button button button--positive']"
