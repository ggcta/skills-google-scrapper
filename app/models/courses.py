from typing import Any

from models.collection import Collection
from config.settings import DEFAULT_PORTAL, portal_config
from models.course import Course


class Courses(Collection):
    """
    Class representing a collection of courses.
    """

    def __init__(self,
                 name: str | None = None,
                 url: str | None = None,
                 collection: dict[str, Any] | None = None,
                 driver=None,
                 portal: str = DEFAULT_PORTAL):
        super().__init__(name, url or portal_config(portal)["courses"], collection, portal=portal)
        self.driver = driver

    def fetch_courses(self, force: bool = False) -> bool:
        """
        Gather all courses from the CloudSkillsBoost Courses page using the API.
        Returns a Boolean to check status.
        """
        if not self.driver:
            print("(Courses.fetch_courses) Error: Webdriver is required to fetch courses.")
            return False

        if not force and self.collection:
            print("(Courses.fetch_courses) Collection not empty. Skipping fetch.")
            return True

        import json

        api_url_courses = portal_config(self.portal)["api_courses"]
        print(f"Fetching courses from API: {api_url_courses}")
        
        all_courses = {}
        page = 1
        has_more = True
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

        try:
            while has_more:
                url = f"{api_url_courses}&page={page}"
                print(f"Fetching page {page}...", end='\r')
                
                self.driver.get(url)

                try:
                    pre_element = self.driver.find_element("tag name", "pre")
                    json_text = pre_element.text
                except Exception:
                    # Fallback to body if <pre> isn't where JSON is rendered
                    body_element = self.driver.find_element("tag name", "body")
                    json_text = body_element.text

                try:
                    data = json.loads(json_text)
                except json.JSONDecodeError:
                    print(f"\nFailed to decode JSON on page {page}")
                    break
                
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                     items = data.get("searchResults", [])
                
                if not items:
                    # No more items
                    has_more = False
                    break
                
                # Process items
                for item in items:
                    title = item.get("title")
                    path_url = item.get("path")
                    if title and path_url:
                        # Extract ID from path (e.g. /course_templates/72?...)
                        clean_path = path_url.split('?')[0]
                        course_id = clean_path.split('/')[-1]
                        
                        if course_id:
                            all_courses[course_id] = title.strip()
                
                page += 1
                if page > 100: 
                    print("\nReached safety limit of 100 pages.")
                    break

            print(f"\nTotal courses found: {len(all_courses)}")

            if all_courses:
                self.collection = all_courses
                self.save_json()
                return True
            else:
                print("(Courses.fetch_courses) No courses found.")
                return False

        except Exception as error:
            print(f"(Courses.fetch_courses) Error occurred: {error}")
            return False

    # TODO: fetch_data() method to refresh all the courses' data.
    def fetch_data(self):        
        """
        Fetch data for all courses in the collection.
        """
        for course_id, course_name in self.collection.items():
            # Print out the course id and name as a heading title
            heading = f"{course_id} - {course_name.upper()}"
            print(f"\n\033[45m[{heading:<85}]\033[0m")

            # Start to fetch the course data (same portal as this collection)
            a_course = Course(id=course_id, portal=self.portal)
            a_course.extract_transcript()
