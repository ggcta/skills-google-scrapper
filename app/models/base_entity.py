import json
from config.settings import BASE_URL_COURSES, BASE_URL_LAB, BASE_URL_PATHS, DATA_FOLDER_NAME, OUTPUT_FOLDER_NAME
from pathlib import Path as PathlibPath

from services.md_helper import MDHelper
from utils.utils import util_replace_special_chars
from models.serialize import Serialize


class BaseEntity(Serialize):
    """
    Base class for all entities including Path, Course, and Lab.
    """
    def __init__(self,
                 id: str,
                 name: str,
                 description: str):
        self.id = id
        self.name = name
        self.description = description

    @property
    def type(self):
        """
        Dynamically determine the type based on the class name.
        """
        return self.__class__.__name__

    @property
    def url(self):
        """
        Dynamically generate the URL based on the type.
        """
        base_url = {
            "Path": BASE_URL_PATHS,
            "Course": BASE_URL_COURSES,
            "Lab": BASE_URL_LAB
        }.get(self.type, None)

        if not base_url:
            raise ValueError(f"Invalid entity type: {self.type}")

        return f"{base_url}/{self.id}"

    # Properties to get the JSON and Markdown file names and paths
    @property
    def _json_name(self):
        """
        Generate the JSON file name based on the entity ID.
        """
        return f'{self.id}.json'
    
    # Properties to get the JSON and Markdown file names and paths
    @property
    def _md_name(self):
        """
        Generate the Markdown file name based on the entity name.
        """
        # Replace special characters in the name for the Markdown file name
        # and ensure it ends with .md
        return f'{util_replace_special_chars(self.name)}.md'

    # Properties to get the JSON and Markdown file names and paths
    @property
    def _json_path(self):
        """
        Get the JSON file path based on the entity type.
        """
        return PathlibPath(DATA_FOLDER_NAME) / f'{self.type.lower()}s' / self._json_name

    # Properties to get the JSON and Markdown file names and paths
    @property
    def _md_path(self):
        """
        Get the Markdown file path based on the entity type.
        """
        return PathlibPath(OUTPUT_FOLDER_NAME) / f'{self.type.lower()}s' / self._md_name

    # Convert the entity's data to a dictionary without private attributes
    def to_dict(self):
        """
        Convert the entity's data to a dictionary.
        """
        # Convert the entity data to a dictionary, excluding private attributes
        # and adding the type and URL
        the_dict = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        the_dict['type'] = self.type
        the_dict['url'] = self.url
        return the_dict

    # Load the entity data from a JSON file
    def load_json(self):
        """
        Load the entity data from a JSON file.
        If the file doesn't exist yet, load an empty {}.
        If the file does exist, load it with json.load and update the entity's data.
        """

        # Don't load the JSON file if it doesn't exist
        # Don't create the folder if it doesn't exist
        if not self._json_path.parent.exists() or not self._json_path.exists():
            self.__dict__.update({})
            return

        # And update the entity's data
        try:
            with open(self._json_path,
                      'r',
                      encoding='utf-8') as jsonfile:
                data = json.load(jsonfile)
                self.__dict__.update(data)
        except FileNotFoundError:
            print(f"\033[33m(BaseEntity.load_json) The BaseEntity's data is not cached. Fetching... from website.\033[0m\n")
        except json.JSONDecodeError:
            print(f"(BaseEntity.load_json) Error decoding JSON from file: {self._json_path}")

    def save_json(self):
        """
        Save the entity data to a JSON file.
        """

        # Convert the entity data to a dictionary, consider to sort the values
        entity_data = self.to_dict()

        # Create the folder if it doesn't exist
        if not self._json_path.parent.exists():
            self._json_path.parent.mkdir(parents=True, exist_ok=True)

        # Create the JSON file if it doesn't exist
        # Save the data to a JSON file with UTF-8 encoding and Unix line endings
        try:
            with open(self._json_path, 'w',
                    encoding='utf-8',
                    newline='\n') as jsonfile:
                json.dump(entity_data,
                        jsonfile,
                        ensure_ascii=False,
                        indent=2)
        except IOError as e:
            print(f"(BaseEntity.save_json) Error writing JSON to file: {self._json_path}")
            print(e)
        except json.JSONDecodeError:
            print(f"(BaseEntity.save_json) Error decoding JSON from file: {self._json_path}")
        except Exception as e:
            print(f"(BaseEntity.save_json) An unexpected error occurred: {e}")

    # Save the entity data to a Markdown file
    def save_markdown(self):
        """
        Save the entity data to a Markdown file.
        """

        md_helper = MDHelper()
    
        # Generate the Markdown content
        # TODO: Use case statement to handle different entity types
        match self.type:
            case 'Path':
                entity_md = md_helper.md_helper_path(self.to_dict())
            case 'Course':
                entity_md = md_helper.md_helper_course(self.to_dict())
            case 'Lab':
                entity_md = md_helper.md_helper_lab(self.to_dict())
            case _:
                raise ValueError(f"Unsupported entity type: {self.type}")
        
        # Create the folder if it doesn't exist
        if not self._md_path.parent.exists():
            self._md_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the entity data to a Markdown file with UTF-8 encoding and Unix line endings
        with open(self._md_path,
                  "w",
                  encoding="utf-8",
                  newline='\n') as md_file:
            md_file.write(entity_md)
