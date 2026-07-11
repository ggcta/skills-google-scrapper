import html
import json
from config.settings import DATA_FOLDER_NAME, OUTPUT_FOLDER_NAME, DEFAULT_PORTAL, portal_config
from pathlib import Path as PathlibPath
from utils.utils import util_atomic_write_text, util_replace_quote_marks, util_replace_special_chars, util_strip_html_tags
from models.serialize import Serialize


class BaseEntity(Serialize):
    """
    Base class for all entities including Path, Course, and Lab.
    """

    # Declared (not assigned) so the type checker knows these can exist without
    # every subclass actually setting them: a bare annotation adds nothing to
    # instance.__dict__, so hasattr()/to_dict() still behave as if the
    # attribute were never set on subclasses (e.g. Lab) that don't assign it.
    datePublished: str | None
    topics: list | None

    def __init__(self,
                 id: str,
                 name: str | None = None,
                 description: str | None = None,
                 title: str | None = None,
                 portal: str | None = DEFAULT_PORTAL):
        self.id = id
        self.title = title or name
        self.description = description
        # Which portal this entity belongs to (public / partner). Part of the
        # entity's identity: the same id means different content per portal.
        self.portal = portal or DEFAULT_PORTAL

    @property
    def name(self):
        """Alias for title for backward compatibility."""
        return self.title

    @name.setter
    def name(self, value):
        self.title = value

    @property
    def type(self):
        """
        Dynamically determine the type based on the class name.
        """

        return self.__class__.__name__

    @property
    def base_url(self):
        """The root URL of this entity's portal (e.g. https://partner.skills.google)."""
        return portal_config(self.portal)["base"]

    @property
    def url(self):
        """
        Dynamically generate the URL based on the type and portal.
        """

        cfg = portal_config(self.portal)
        url_key = {
            "Path": "paths",
            "Course": "courses",
            "Lab": "lab"
        }.get(self.type, None)

        if not url_key:
            raise ValueError(f"Invalid entity type: {self.type}")

        return f"{cfg[url_key]}/{self.id}"

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

        # Replace special characters in the title for the Markdown file name
        # and ensure it ends with .md
        return f'{util_replace_special_chars(self.title)}.md'

    # Properties to get the JSON and Markdown file names and paths
    @property
    def _json_path(self):
        """
        Get the JSON file path based on the entity type, scoped by portal.
        """

        return PathlibPath(DATA_FOLDER_NAME) / self.portal / f'{self.type.lower()}s' / self._json_name

    # Properties to get the JSON and Markdown file names and paths
    @property
    def _md_path(self):
        """
        Get the Markdown file path based on the entity type, scoped by portal.
        """

        return PathlibPath(OUTPUT_FOLDER_NAME) / self.portal / f'{self.type.lower()}s' / self._md_name

    # Convert the entity's data to a dictionary without private attributes
    def to_dict(self):
        """
        Convert the entity's data to a dictionary.
        """
        import time

        # Convert the entity data to a dictionary, excluding private attributes
        # and adding the type and URL
        # Also exclude 'driver' and 'name' as they are not serialized directly
        the_dict = {k: v for k, v in self.__dict__.items() if not k.startswith('_') and k not in ('driver', 'name')}
        the_dict['type'] = self.type
        the_dict['url'] = self.url
        
        # Add scrapedTime (epoch in milliseconds)
        the_dict['scrapedTime'] = int(time.time() * 1000)
        
        return the_dict

    # Load the entity data from its per-item JSON file
    def load_json(self):
        """
        Load the entity data from its per-item JSON file — the single source of
        truth (backlog #9). Full entity data lives in
        data/<portal>/<type>s/<id>.json; the TinyDB is only a derived ledger.
        If the file doesn't exist, the entity stays empty (i.e. not fetched).
        """
        current_portal = self.portal
        try:
            with open(self._json_path, encoding='utf-8') as handle:
                data = json.load(handle)
        except (FileNotFoundError, ValueError, OSError):
            # No per-item file: nothing fetched yet — leave the entity as-is.
            return

        self.__dict__.update(data)
        # Backward compatibility: migrate 'name' to 'title' on load
        if 'name' in self.__dict__:
            self.title = self.__dict__.pop('name')
        # Never let stored data change which portal we're operating in
        # (legacy records may not carry a portal at all).
        self.portal = data.get('portal', current_portal)

    def _ledger_row(self, entity_data):
        """
        The compact index row stored in the TinyDB ledger. The full data lives in
        the per-item JSON file (the SSOT); this row only powers the browse
        catalog, list/search, and the last-known fetch status. Kept in step with
        the Go core's ledger schema (see go/internal/store/save.go).
        """
        return {
            'id': str(self.id),
            'name': self.title,
            'title': self.title,
            'type': self.type,
            'portal': self.portal,
            'scrapedTime': entity_data.get('scrapedTime'),
        }

    def save_json(self):
        """
        Save the entity: write the full per-item JSON file (the SSOT), then upsert
        a compact ledger row into the TinyDB index (backlog #9).
        """

        # Convert the entity data to a dictionary
        entity_data = self.to_dict()

        # 1. SAVE the full per-item JSON file (the single source of truth),
        # written atomically so a Ctrl+C or crash can never leave a truncated
        # file on disk.
        try:
            payload = json.dumps(entity_data, ensure_ascii=False, indent=2)
            util_atomic_write_text(self._json_path, payload)
        except IOError as e:
            print(f"(BaseEntity.save_json) Error writing JSON to file: {self._json_path}")
            print(e)
        except json.JSONDecodeError:
            print(f"(BaseEntity.save_json) Error decoding JSON from file: {self._json_path}")
        except Exception as e:
            print(f"(BaseEntity.save_json) An unexpected error occurred: {e}")

        # 2. UPSERT the compact ledger row into the TinyDB index (catalog +
        # list/search + status). Full data is in the file above, not here.
        try:
            from services.database import Database
            db = Database(self.portal)
            # Use plural table name (e.g. 'Course' -> 'courses')
            table_name = f"{self.type.lower()}s"
            if self.type.lower().endswith('s'):
                table_name = self.type.lower()

            db.upsert(table_name, self._ledger_row(entity_data))
        except Exception as e:
            print(f"(BaseEntity.save_json) Error syncing to DB: {e}")

    def generate_front_matter(self) -> str:
        """
        Generate the front matter for the Markdown file.

        Order:
        - id
        - title
        - type
        - url
        - date_published
        - topics
        - scraped_date
        """
        from datetime import datetime
        import time

        front_matter_lines = ["---"]
        if hasattr(self, 'id'):
            front_matter_lines.append(f"id: '{self.id}'")
        if hasattr(self, 'title') and self.title:
            front_matter_lines.append(f"title: '{self.title}'")
        if hasattr(self, 'type'):
            front_matter_lines.append(f"type: {self.type}")
        if getattr(self, 'portal', None):
            front_matter_lines.append(f"portal: {self.portal}")
        if hasattr(self, 'url'):
            front_matter_lines.append(f"url: {self.url}")
        if hasattr(self, 'datePublished'):
            front_matter_lines.append(f"date_published: {self.datePublished}")
        if hasattr(self, 'topics'):
            if self.topics:
                front_matter_lines.append("topics:\n" + "\n".join([f"  - {topic}" for topic in self.topics]))
            else:
                # No topics: emit a single bare 'topics:' line (no blank line).
                front_matter_lines.append("topics:")
            
        # Add scraped_date
        scraped_ts = getattr(self, 'scrapedTime', None)
        if scraped_ts:
             dt = datetime.fromtimestamp(scraped_ts / 1000.0)
             front_matter_lines.append(f"scraped_date: {dt.strftime('%Y-%m-%d')}")
        else:
             # If not present, use current time
             now = datetime.now()
             front_matter_lines.append(f"scraped_date: {now.strftime('%Y-%m-%d')}")

        front_matter_lines.append("---")
        return "\n".join(front_matter_lines)

    def generate_markdown(self, **kwargs) -> str:
        """
        Generate the Markdown representation of the entity.
        """

        # Convert the Path object to a dictionary
        markdown = []
        markdown.append(self.generate_front_matter())

        return "\n\n".join(markdown) + "\n"

    def save_markdown(self, **kwargs) -> None:
        """
        Save the Path data to a Markdown file.
        passes kwargs to generate_markdown
        """

        mdtext = self.generate_markdown(**kwargs)

        # Write atomically (temp file + os.replace) so an interrupted run never
        # leaves a half-written Markdown file in the vault.
        util_atomic_write_text(self._md_path, mdtext)

    def clean_text(self, text: str) -> str:
        """
        Utility method to clean and format text.
        """
        if not text:
            return ""

        text = util_strip_html_tags(html.unescape(text))
        text = text.replace('\r\n', '\n')
        return util_replace_quote_marks(text).strip()
