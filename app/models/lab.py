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

    def generate_markdown(self):
        """
        Generate the Markdown content for the Lab entity.
        """
        markdown = []
        markdown.append(self.generate_front_matter())

        markdown.append(f"# [{self.name}]({self.url})")

        if hasattr(self, 'description') and self.description:
            markdown.append(f"{self.description}")

        if hasattr(self, 'steps') and self.steps:
            for step_number, step_text in self.steps.items():
                markdown.append(f"## Step {step_number}: {step_text}")
        return "\n\n".join(markdown) + "\n"

    # Save the Lab data to a Markdown file
    def save_markdown(self):
        """
        Save the Lab data to a Markdown file.
        """

        lab_md = self.generate_markdown()

        # Create the folder if it doesn't exist
        if not self._md_path.parent.exists():
            self._md_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the markdown content to a file, overwrite if exists
        with open(self._md_path, "w", encoding="utf-8", newline='\n') as mdfile:
            mdfile.write(lab_md)

        print(f"(Lab.save_markdown) Markdown file saved: {self._md_path}")
