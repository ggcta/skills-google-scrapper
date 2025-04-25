# Description: This file contains the Lab class which is a subclass of BaseEntity.
from services.md_helper import MDHelper
from .base_entity import BaseEntity

# Lab entity based on BaseEntity
class Lab(BaseEntity):
    def __init__(self,
                 id: str,
                 name: str = None,
                 description: str = None,
                 steps: dict = None):
        super().__init__(id,
                         name,
                         description
                         )
        self.steps = steps or {}

    # TODO: fetch_data() for fetching a lab's data

    # Save the Lab data to a Markdown file
    def save_markdown(self):
        """
        Write the {self.to_dict()} into a Markdown files for each path.
        """
        # Until we extract the lab content, for time being,
        # can use the same helper for Path
        md_helper = MDHelper()
        # Generate the markdown content
        path_md = md_helper.md_helper_lab(self.to_dict())

        # Create the folder if it doesn't exist
        if not self._md_path.parent.exists():
            self._md_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the markdown content to a file, overwrite if exists
        with open(self._md_path, "w", encoding="utf-8", newline='\n') as md_file:
            md_file.write(path_md)
