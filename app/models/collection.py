from datetime import datetime
import json

from bs4 import BeautifulSoup
import requests
from config.settings import BASE_URL, BASE_URL_PATHS, DATA_FOLDER_NAME, OUTPUT_FOLDER_NAME
from models.serialize import Serialize
from pathlib import Path as PathlibPath


# Base entity for collection: Courses, Paths, Labs.
class Collection(Serialize):
    """
    Base entity for collection: Courses, Paths, Lab.
    """

    def __init__(self,
                 type: str = None,
                 name: str = None,
                 url: str = BASE_URL,
                 date: str = None,
                 collection: dict = None):
        self.type = type
        self.name = name
        self.url = url
        self.date = date or str(datetime.today().date())
        self.collection = collection or {}

    # Properties to get the JSON and Markdown file names and paths
    @property
    def _json_name(self):
        return f"{self.type.lower()}.json"
    
    # Properties to get the JSON and Markdown file names and paths
    @property
    def _json_path(self):
        return PathlibPath(DATA_FOLDER_NAME) / self._json_name

    # Properties to get the JSON and Markdown file names and paths
    @property
    def _md_name(self):
        return f"{self.type.lower()}.md"
    
    # Properties to get the JSON and Markdown file names and paths
    @property
    def _md_path(self):
        return PathlibPath(OUTPUT_FOLDER_NAME) / self._md_name

    # Convert the entity's data to a dictionary without private attributes
    def to_dict(self):
        """
        Convert the entity's data to a dictionary.
        """

        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
    
    # Load the collection from a JSON file
    def load_json(self):
        """
        Load the collection from a JSON file.
        """

        # Create the folder if it doesn't exist
        if not self._json_path.parent.exists():
            self._json_path.parent.mkdir(parents=True, exist_ok=True)

        # Create the JSON file if it doesn't exist
        if not self._json_path.exists():
            with open(self._json_path, 'w', encoding='utf-8', newline='\n') as json_file:
                json_file.write('{}')

        # Load the JSON file even if it's empty and update the entity's data
        try:

            with open(self._json_path, 'r', encoding='utf-8', newline='\n') as jsonfile:
                data = json.load(jsonfile)
                self.__dict__.update(data)
        except FileNotFoundError:
            print(f"\033[33m(Collection.load_json) The Collections data is not cached. Please fetch from website first.\033[0m\n")
        except json.JSONDecodeError:
            print(f"(Collection.load_json) Error decoding JSON from file: {self._json_path}")

    # Save the collection to a JSON file
    def save_json(self):
        """
        Save the collection to a JSON file.\n
        This will overwrite the existing contents of the file.
        """

        # TODO: Trigger self.collection sorting everytime it gets updated.
        # Sort the collection based on the type of values
        if self.collection and all(isinstance(value, str) for value in self.collection.values()):
            # If all values are strings, sort by values
            self.collection = dict(sorted(self.collection.items(), key=lambda item: item[1]))
        elif self.collection and all(isinstance(value, dict) for value in self.collection.values()):
            # If all values are dictionaries, sort by keys
            self.collection = dict(sorted(self.collection.items(), key=lambda item: item[0]))
        else:
            # Handle mixed types or empty collection (optional)
            print(f"(Collection.save_json) Warning: Mixed value types in collection or empty collection. Skipping sorting for {self.name}.")

        data = self.to_dict()

        json_paths_folder = self._json_path.parent

        # Create the folder if it doesn't exist
        if not json_paths_folder.exists():
            json_paths_folder.mkdir(parents=True, exist_ok=True)

        # This will overwrite the existing contents of the file
        with open(self._json_path, 'w', encoding='utf-8', newline='\n') as jsonfile:
            json.dump(data, jsonfile, ensure_ascii=False, indent=2)

    def print_list(self):
        """
        Print out the collection prior to prompting user for a selection.
        """

        # Sort the collection by name and convert to a list
        if self.collection and all(isinstance(value, str) for value in self.collection.values()):
            # If all values are strings, sort by values
            a_sorted_list = sorted(self.collection.items(), key=lambda item: item[1])
        elif self.collection and all(isinstance(value, dict) for value in self.collection.values()):
            # If all values are dictionaries, sort by keys
            a_sorted_list = sorted(self.collection.items(), key=lambda item: item[0])
        else:
            a_sorted_list = list(self.collection.items())
        print(f"\n"
              f"\033[45m[{self.name.upper():^85}]\033[0m"
              "\n")

        # Print the sorted list
        for an_item in a_sorted_list:
            item_id = an_item[0]
            item_name = an_item[1]
            print(f"+|-• \033[35m[{item_id:>5} - {item_name:<72}]\033[0m")

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

    def write_md(self):
        """
        Write out the paths collect into a Markdown file.
        """

        # Sort the collection by name
        if self.collection and all(isinstance(value, str) for value in self.collection.values()):
            # If all values are strings, sort by values
            self.collection = dict(sorted(self.collection.items(), key=lambda item: item[1]))
        elif self.collection and all(isinstance(value, dict) for value in self.collection.values()):
            # If all values are dictionaries, sort by keys
            self.collection = dict(sorted(self.collection.items(), key=lambda item: item[0]))
        else:
            print(f"(Collection.write_md) Warning: Mixed value types in collection or empty collection. Skipping sorting for {self.name}.")

        # Create the Markdown file
        markdown_list = self.md_helper()
        with open(self._md_path, 'w', encoding='utf-8', newline='\n') as md_file:
            md_file.write(markdown_list)

    def md_helper(self):
        markdown = []

        # Add front matter
        front_matter_lines = ["---",
                              f"type: {self.type}",
                              f"name: '{self.name}'",
                              f"url: {self.url}",
                              f"date: {self.date}",
                              "---"]
        markdown.append("\n".join(front_matter_lines))

        # The # main heading
        markdown.append(f"# [{self.name}]({self.url})")

        item_list = []
        if self.type == 'paths':
            for item_id, item_name in self.collection.items():
                item_url = f"{BASE_URL_PATHS}/{item_id}"
                item_list.append(f"- [ ] `{item_id:>5}`: [(Web Link)]({item_url}) | {item_name}")
        markdown.append("\n".join(item_list))

        return "\n\n".join(markdown) + "\n"
