from models.collection import Collection
from config.settings import DEFAULT_PORTAL, portal_config
import json
from typing import Any

class Paths(Collection):
    """
    Class representing a collection of paths.
    """

    def __init__(self,
                 name: str | None = None,
                 url: str | None = None,
                 collection: dict[str, Any] | None = None,
                 driver=None,
                 portal: str = DEFAULT_PORTAL):
        super().__init__(name, url or portal_config(portal)["paths"], collection, portal=portal)
        self.driver = driver

    def fetch_paths(self, base_url: str | None = None, force: bool = False) -> bool:
        """
        Gather all paths from the CloudSkillsBoost Paths page using the API.\n
        Returns a Boolean to check status.

        :param base_url: CloudSkillsBoost Paths page URL (unused in API method, kept for signature).
        :param force: If True, fetch even if collection is not empty.
        """
        if not self.driver:
            print("(Paths.fetch_paths) Error: Webdriver is required to fetch paths.")
            return False

        if not force and self.collection:
            print("(Collection.fetch_paths) Collection not empty. Skipping fetch.")
            return True

        api_url_paths = portal_config(self.portal)["api_paths"]
        print(f"Fetching paths from API: {api_url_paths}")
        
        all_paths = {}
        page = 1
        has_more = True
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

        try:
            while has_more:
                url = f"{api_url_paths}&page={page}"
                print(f"Fetching page {page}...", end='\r')
                
                self.driver.get(url)

                # The browser will likely display raw JSON. We can extract it from the <body> or <pre>
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
                        # Extract ID from path (e.g. /paths/16?...)
                        # Split by '?' first to remove query params, then '/'
                        clean_path = path_url.split('?')[0]
                        path_id = clean_path.split('/')[-1]
                        
                        if path_id:
                            all_paths[path_id] = title.strip()
                
                page += 1
                # Safety break to avoid infinite loops if API changes behavior
                if page > 50: 
                    print("\nReached safety limit of 50 pages.")
                    break

            print(f"\nTotal paths found: {len(all_paths)}")

            # Check if the collection is not empty
            if all_paths:
                self.collection = all_paths
                self.save_json()
                return True
            else:
                print("(Collection.fetch_paths) No paths found.")
                return False

        except Exception as error:
            print(f"(Collection.get_paths) Error occurred: {error}")
            return False