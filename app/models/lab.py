# Description: This file contains the Lab class which is a subclass of BaseEntity.
import re
from bs4 import BeautifulSoup
from .base_entity import BaseEntity
from utils.utils import util_ensure_authenticated

# Selectors for extracting a lab's data from its page.
# The sidebar outline (LAB_CONTENT_OUTLINE) was removed in a site update;
# steps are now rendered as <h2 id="stepN">Title</h2> headings inside the
# lab instructions container.
LAB_CONTENT_OUTLINE = "ul.lab-content__outline"
LAB_STEP_HEADINGS = ".lab-content__renderable-instructions h2[id^='step']"
LAB_OG_TITLE = "meta[property='og:title']"
LAB_META_DESCRIPTION = "meta[name='description']"


# Lab entity based on BaseEntity
class Lab(BaseEntity):
    """
    Class representing a Lab entity.
    """

    def __init__(self,
                 id: str,
                 name: str | None = None,
                 description: str | None = None,
                 steps: dict[str, str] | None = None,
                 driver=None,
                 title: str | None = None,
                 portal: str | None = None):
        super().__init__(id=id,
                         name=name,
                         description=description,
                         title=title,
                         portal=portal)
        self.steps = steps or {}
        self.driver = driver

    # MARK: parse_steps
    @staticmethod
    def parse_steps(lab_page_html) -> dict[str, str]:
        """
        Extract a lab's table of contents (steps) from its parsed page.

        The site historically exposed a sidebar outline
        (``ul.lab-content__outline``) with ``<a href="#stepN">`` anchors. That
        element was removed in a site update; the steps are now rendered as
        ``<h2 id="stepN">Title</h2>`` headings inside the lab instructions
        container. Try the old outline first, then fall back to the headings.

        :param lab_page_html: Parsed BeautifulSoup of the lab page.
        :return: Mapping of step number (str) to step title (str).
        """

        lab_steps = {}

        # Old structure: sidebar outline with anchor links.
        outline_element = lab_page_html.select_one(LAB_CONTENT_OUTLINE)
        if outline_element:
            for a_tag in outline_element.find_all('a'):
                step = a_tag['href'].strip('#step')
                lab_steps[step] = a_tag.text
            if lab_steps:
                return lab_steps

        # New structure: step headings inside the rendered instructions.
        step_headings = lab_page_html.select(LAB_STEP_HEADINGS)
        # Fallback in case the container class changes again.
        if not step_headings:
            step_headings = lab_page_html.select("h2[id^='step']")

        for heading in step_headings:
            # Turn the "stepN" id into just the number, e.g. "step1" -> "1".
            step = heading.get('id', '').replace('step', '', 1)
            if step:
                lab_steps[step] = heading.get_text(strip=True)

        return lab_steps

    # MARK: fetch_data
    def fetch_data(self, force: bool = False, fetch_url: str | None = None) -> bool:
        """
        Fetch this lab's data (name, description, steps).

        By default it loads the lab's own catalog page (self.url). The partner
        portal instead serves labs from a focus URL that references the parent
        path/course (e.g. /focuses/104653?parent=catalog&path=4343); callers
        with that context pass it via ``fetch_url``. The page structure is the
        same, so parsing is identical either way.

        :param force: If True, re-fetch even if the lab already exists locally.
        :param fetch_url: Explicit URL to load instead of self.url.
        :return: True if the lab was fetched, False if skipped or failed.
        """

        if not self.driver:
            print("(Lab.fetch_data) Error: Webdriver is required to fetch lab data.")
            return False

        # Skip if the lab already exists locally, unless forced.
        self.load_json()
        if self.name and not force:
            print(f"(Lab.fetch_data) •-• [+] Existed: {self.id} - {self.name}")
            return False

        target_url = fetch_url or self.url
        try:
            print(f"(Lab.fetch_data) Fetching: {target_url}")
            self.driver.get(target_url)

            if not util_ensure_authenticated(self.driver, target_url, f"lab {self.id}"):
                return False

            lab_page_html = BeautifulSoup(self.driver.page_source, "html.parser")

            # Name: prefer the Open Graph title, stripping the site suffix
            # (e.g. "... | Google Skills"). Fall back to the <title> tag.
            name = None
            og_title = lab_page_html.select_one(LAB_OG_TITLE)
            if og_title and og_title.get('content'):
                name = og_title['content']
            elif lab_page_html.title and lab_page_html.title.string:
                name = lab_page_html.title.string
            if name:
                name = re.sub(r'\s*\|\s*Google.*$', '', name).strip()

            if not name:
                print(f"(Lab.fetch_data) [!] Could not determine lab name for {self.id}.")
                return False

            # Description from the meta description tag.
            description = ''
            meta_description = lab_page_html.select_one(LAB_META_DESCRIPTION)
            if meta_description and meta_description.get('content'):
                description = self.clean_text(meta_description['content'])

            # Steps (table of contents).
            steps = self.parse_steps(lab_page_html)

            self.name = name
            self.description = description
            self.steps = steps

            print(f"(Lab.fetch_data) •-• [+] {self.id} - {self.name} ({len(steps)} steps)")
            return True
        except Exception as error:
            print(f"(Lab.fetch_data) Error: {error}")
            return False

    def generate_markdown(self, toc_only: bool = False, **kwargs):
        """
        Generate the Markdown content for the Lab entity.
        :param toc_only: If True, only generate table of contents (structure).
        """

        markdown = []
        markdown.append(self.generate_front_matter())

        markdown.append(f"# [{self.name}]({self.url})")

        if not toc_only:
            if hasattr(self, 'description') and self.description:
                markdown.append(f"{self.description}")

        if hasattr(self, 'steps') and self.steps:
            for step_number, step_text in self.steps.items():
                markdown.append(f"## Step {step_number}: {step_text}")

        return "\n\n".join(markdown) + "\n"
