from selenium.webdriver.chrome.webdriver import WebDriver
from models.collection import Collection
from config.settings import DEFAULT_PORTAL, portal_config


class Labs(Collection):
    """
    Class representing a collection of labs.
    """

    def __init__(self,
                 name: str | None = None,
                 url: str | None = None,
                 collection: dict[str, str] | None = None,
                 driver: WebDriver | None = None,
                 portal: str = DEFAULT_PORTAL):
        super().__init__(name, url or portal_config(portal)["lab"], collection, portal=portal)
        self.driver: WebDriver | None = driver

    def fetch_labs(self, force: bool = False) -> bool:
        """
        Gather all labs from the CloudSkillsBoost Labs page using the API.
        Returns a Boolean to check status.
        """
        if not self.driver:
            print("(Labs.fetch_labs) Error: Webdriver is required to fetch labs.")
            return False

        if not force and self.collection:
            print("(Labs.fetch_labs) Collection not empty. Skipping fetch.")
            return True

        import json

        api_url_labs = portal_config(self.portal)["api_labs"]
        print(f"Fetching labs from API: {api_url_labs}")

        all_labs = {}
        page = 1
        has_more = True

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

        try:
            while has_more:
                url = f"{api_url_labs}&page={page}"
                print(f"Fetching page {page}...", end='\r')

                self.driver.get(url)

                try:
                    pre_element = self.driver.find_element("tag name", "pre")
                    json_text = pre_element.text
                except Exception:
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
                        # Extract ID from path (e.g. /catalog_lab/123?...)
                        clean_path = path_url.split('?')[0]
                        lab_id = clean_path.split('/')[-1]

                        if lab_id:
                            all_labs[lab_id] = title.strip()

                page += 1
                if page > 100:
                    print("\nReached safety limit of 100 pages.")
                    break

            print(f"\nTotal labs found: {len(all_labs)}")

            if all_labs:
                self.collection = all_labs
                self.save_json()
                return True
            else:
                print("(Labs.fetch_labs) No labs found.")
                return False

        except Exception as error:
            print(f"(Labs.fetch_labs) Error occurred: {error}")
            return False
