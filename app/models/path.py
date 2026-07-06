import json
from bs4 import BeautifulSoup
from utils.utils import util_replace_special_chars, util_ensure_authenticated
from config.settings import *
from models.base_entity import BaseEntity

# Constants for the extraction of the course data
LD_JSON = "script[type='application/ld+json']"
# Partner portal path pages do not embed ld+json; they render the plan title
# as an <h1> and each course/lab as a <ql-activity-card>.
PARTNER_TITLE = "h1.learning-plan-title"
PARTNER_ACTIVITY_CARD = "ql-activity-card"

# Path entity
class Path(BaseEntity):
    """
    Class representing a Path entity.
    """

    def __init__(self,
                 id: str,
                 name: str = None,
                 description: str = None,
                 datePublished: str = None,
                 courses: dict = None,
                 driver=None,
                 title: str = None,
                 portal: str = None):
        super().__init__(id=id,
                         name=name,
                         description=description,
                         title=title,
                         portal=portal)
        self.datePublished = datePublished
        self.courses = courses or {}
        self.driver = driver

    # Fetch the Path data from the website
    def fetch_data(self):
        """
        Fetch Path data from the website and populate this entity.

        The public portal embeds an ld+json blob; the partner portal does not
        and instead renders the plan as <ql-activity-card> elements. Try the
        ld+json first, then fall back to parsing the partner DOM.
        """

        try:
            if not self.driver:
                print("(fetch_data) Error: Webdriver is required to fetch path data.")
                return {}

            # Navigate to the path URL
            self.driver.get(self.url)

            if not util_ensure_authenticated(self.driver, self.url, f"path {self.id}"):
                return {}

            path_html = BeautifulSoup(self.driver.page_source, "html.parser")
        except Exception as error:
            print(f"(fetch_data) Error loading path page: {error}")
            return {}

        # Prefer the ld+json blob (public portal); fall back to partner DOM.
        script_element = path_html.select_one(LD_JSON)
        if script_element and script_element.string:
            self._parse_ld_json(script_element.string)
        else:
            self._parse_partner_html(path_html)

    # MARK: _parse_ld_json
    def _parse_ld_json(self, json_content: str) -> None:
        """Populate path data from the public portal's ld+json blob."""
        path_data = json.loads(json_content)

        # A Path JSON element should and must have 'hasPart' key
        courses_list: dict[str, dict] = {}
        for course in path_data['hasPart']:
            course_id = course['url'].split('/')[-1]
            courses_list[course_id] = {
                "id": course_id,
                "type": course["@type"],
                "name": course["name"].strip(),
                "url": course["url"].strip()
            }

        self.name = path_data['name'].strip()
        self.description = self.clean_text(path_data['description'])
        self.datePublished = path_data.get('datePublished', '').strip()
        self.courses = courses_list

    # MARK: _parse_partner_html
    def _parse_partner_html(self, path_html) -> None:
        """
        Populate path data from a partner portal path page, which uses an
        <h1 class="learning-plan-title"> and <ql-activity-card> elements
        (each carrying name/description/type and a 'path' href) instead of
        an ld+json blob. Partner plans list both courses and standalone labs.
        """
        title_element = path_html.select_one(PARTNER_TITLE)
        if title_element:
            self.name = title_element.get_text(strip=True)

        # Partner path pages expose neither a plan-level description nor a
        # machine-readable publish date; leave them empty.
        self.description = self.description or ""
        self.datePublished = self.datePublished or ""

        activities: dict[str, dict] = {}
        for card in path_html.select(PARTNER_ACTIVITY_CARD):
            href = (card.get('path') or '').split('?')[0].rstrip('/')
            if not href:
                continue
            activity_id = href.split('/')[-1]
            activities[activity_id] = {
                "id": activity_id,
                "type": (card.get('type') or 'course').strip(),
                "name": (card.get('name') or '').strip(),
                "url": f"{self.base_url}{href}",
            }

        self.courses = activities

    # Print out the courses list of a certain Path
    def courses_list(self):
        """
        Print out the courses list of a certain Path.
        """

        # Show the Path Title
        heading = f"{self.id} - {self.name.upper()}"
        print(f"\n\033[45m[{heading:^85}]\033[0m\n")

        # Print out each course in the Path
        for course in self.courses.values():
            course_id = course['id']
            course_name = course['name']
            print(f"+|-• \033[35m[{course_id:>5} - {course_name:<72}]\033[0m")

    def generate_markdown(self, toc_only: bool = False, **kwargs) -> str:
        """
        Generate the Markdown representation of the Path.
        :param toc_only: If True, only generate table of contents (structure).
        """

        # Convert the Path object to a dictionary
        markdown = []
        markdown.append(self.generate_front_matter())

        # Add the main heading
        markdown.append(f"# [{self.name}]({self.url})")
        
        # Add the description
        if not toc_only:
            if hasattr(self, 'description') and self.description:
                markdown.append(f"{self.description}")
        
        # Add the courses list
        if hasattr(self, 'courses') and self.courses:
            markdown.append("## Courses & Progress")
            # Add each course in the Path
            course_list = []
            for course_id, course in self.courses.items():
                course_md_name = f"{util_replace_special_chars(course['name'])}.md"
                course_list.append(f"* [ ] [{course['name']} ({course_id})](../courses/{course_md_name})")
            markdown.append("\n".join(course_list))

        return "\n\n".join(markdown) + "\n"

# TODO: Make Path() matches the json file structure from the website
