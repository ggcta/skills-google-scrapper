from models.collection import Collection
from config.settings import BASE_URL_PATHS
import requests
from bs4 import BeautifulSoup

class Paths(Collection):
    """
    Class representing a collection of paths.
    """

    def __init__(self,
                 name: str = None,
                 url: str = BASE_URL_PATHS,
                 collection: dict = None):
        super().__init__(name, url, collection)

    def fetch_paths(self, base_url: str = BASE_URL_PATHS) -> bool:
        """
        Gather all paths from the CloudSkillsBoost Paths page.\n
        Returns a Boolean to check status.

        :param base_url: CloudSkillsBoost Paths page URL.
        """

        try:
            # Fetch the page content
            response = requests.get(base_url, timeout=10)
            response.raise_for_status()

            # Parse the content with BeautifulSoup
            path_html = BeautifulSoup(response.text, "html.parser")

            # Find all ql-activity-card elements
            path_elements = path_html.find_all("ql-activity-card", attrs={"path": True, "name": True})

            # Extract path data using a dictionary comprehension
            collection = {
                # "id": "name"
                path_element["path"].split('/')[-1]: path_element["name"].strip()
                for path_element in path_elements
                if path_element.get("path") and path_element.get("name")
            }

            # Check if the collection is not empty
            if collection:
                self.collection = collection
                self.save_json()
                return True
            else:
                print("(Collection.fetch_paths) Uh, something is wrong here.")
                return False

        except requests.RequestException as req_err:
            print(f"(Collection.get_paths) Network error: {req_err}")
            return False
        except Exception as error:
            print(f"(Collection.get_paths) Error occurred: {error}")
            return False