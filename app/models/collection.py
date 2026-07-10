from datetime import datetime
import json

from typing_extensions import override
from config.settings import BASE_URL_PATHS, DATA_FOLDER_NAME, OUTPUT_FOLDER_NAME, DEFAULT_PORTAL, portal_config
from models.serialize import Serialize
from pathlib import Path as PathlibPath


# Base entity for collection: Courses, Paths, Labs. Always stores {id: name}.
# Topics has a different (nested) shape and is its own class, see topics.py.
class Collection(Serialize):
    """
    Base entity for collection: Courses, Paths, Lab.
    """

    # Only set inside save_json(), so it's absent until the first save;
    # declared here (not assigned) so hasattr()/to_dict() reflect that.
    scrapedTime: int  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(self,
                 name: str | None = None,
                 url: str | None = None,
                 collection: dict[str, str] | None = None,
                 portal: str = DEFAULT_PORTAL):
        self.name: str | None = name
        # Which portal this collection belongs to (public / partner).
        self.portal: str = portal or DEFAULT_PORTAL
        self.url: str = url or portal_config(self.portal)["base"]
        self.date: str | None = str(datetime.today().date())
        self.collection: dict[str, str] = collection or {}

    @property
    def type(self):
        """
        Override the type property to return the class name.
        """
        return self.__class__.__name__

    # Properties to get the JSON and Markdown file names and paths
    @property
    def _json_name(self):
        return f"{self.type.lower()}.json"

    # Properties to get the JSON and Markdown file names and paths
    @property
    def _json_path(self):
        return PathlibPath(DATA_FOLDER_NAME) / self.portal / self._json_name

    # Properties to get the JSON and Markdown file names and paths
    @property
    def _md_name(self):
        return f"{self.type.lower()}.md"

    # Properties to get the JSON and Markdown file names and paths
    @property
    def _md_path(self):
        return PathlibPath(OUTPUT_FOLDER_NAME) / self.portal / self._md_name

    # Convert the entity's data to a dictionary without private attributes
    @override
    def to_dict(self) -> dict[str, object]:
        """
        Convert the entity's data to a dictionary.
        """
        # `__dict__` is typed dict[str, Any] by typeshed; see Serialize.to_dict.
        collection_dict = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}  # pyright: ignore[reportAny]
        collection_dict['type'] = self.type

        return collection_dict

    # Load the collection from a JSON file
    def load_json(self):
        """
        Load the collection from the Database (TinyDB).
        """
        from services.database import Database

        db = Database(self.portal)
        # Use plural table name
        table_name = f"{self.type.lower()}"
        if self.type.lower() == 'path':
            table_name = 'paths' # just in case

        # Collection usually stores a dict of {id: name}
        # But TinyDB stores documents {id: ..., name: ..., type: ...}
        # We need to reconstruction the collection dict {id: name} from DB docs

        docs = db.all(table_name)
        self.collection = {}
        for doc in docs:
            doc_id = doc.get('id')
            # Entities are stored with 'title'; collection listings with 'name'.
            # Accept either so both sources render.
            doc_name = doc.get('name') or doc.get('title') or ''
            if doc_id:
                self.collection[doc_id] = doc_name

    # Save the collection to a JSON file
    def save_json(self):
        """
        Save the collection to the Database (TinyDB).
        This will UPSERT items.
        """
        import time
        # Update scrapedTime
        self.scrapedTime = int(time.time() * 1000)

        # Sync items to TinyDB
        try:
            from services.database import Database
            db = Database(self.portal)

            # Determine table name (Plural: Paths, Courses, Labs)
            # self.type is usually plural e.g. 'Paths'
            table_name = self.type.lower()

            if self.collection:
                for item_id, name in self.collection.items():
                    # We need to fetch existing doc to preserve other fields if any?
                    # Or just upsert id/name/type?
                    # If we only have ID and Name in collection, we might overwrite other details if we are not careful
                    # But Collection.save_json is usually called after fetching a list of items (id, name).
                    # If we upsert {id, name, type}, it matches TinyDB upsert logic which updates fields.

                    doc = {
                        'id': item_id,
                        'name': name,
                        'type': table_name,
                        'portal': self.portal
                    }
                    db.upsert(table_name, doc)

        except Exception as e:
            print(f"(Collection.save_json) Error syncing to DB: {e}")

    def _fetch_status(self, item_id):
        """
        Return (fetched, scraped_date) for an item, read from its per-item JSON.

        The per-item JSON file is written only by a real fetch — a catalog reload
        writes collection/DB stubs only — so its presence is the source of truth
        for whether the item has been downloaded. scraped_date is a YYYY-MM-DD
        string when a scrapedTime is present, else None.
        """
        item_path = PathlibPath(DATA_FOLDER_NAME) / self.portal / self.type.lower() / f"{item_id}.json"
        try:
            with open(item_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, ValueError, OSError):
            return False, None
        ms = data.get("scrapedTime")
        if ms:
            try:
                return True, datetime.fromtimestamp(ms / 1000.0).strftime("%Y-%m-%d")
            except (ValueError, OSError, OverflowError):
                return True, None
        return True, None

    def _fetch_status_text(self, item_id):
        """Colorized fetch-status suffix for list output (matches the Go CLI)."""
        fetched, date = self._fetch_status(item_id)
        if not fetched:
            return "\033[2m— not fetched\033[0m"
        if date:
            return f"\033[32m✓ {date}\033[0m"
        return "\033[32m✓ fetched\033[0m"

    def print_list(self, sort_by: str = 'name'):
        """
        Print out the collection prior to prompting user for a selection.
        :param sort_by: 'name' or 'id'
        """

        # Sort the collection by name and convert to a list
        if sort_by == 'id':
            # Sort by keys (id)
            a_sorted_list = sorted(self.collection.items(), key=lambda item: item[0])
        else:
            # Defaults to name
            a_sorted_list = sorted(self.collection.items(), key=lambda item: item[1])
        if self.name:
            print(f"\n"
                  f"\033[45m[{self.name.upper():^85}]\033[0m"
                  "\n")
        else:
             print("\n")

        # Print the sorted list
        for an_item in a_sorted_list:
            item_id = an_item[0]
            item_name = an_item[1] if an_item[1] is not None else ''
            print(f"+|-• \033[35m[{item_id:>5} - {item_name:<72}]\033[0m {self._fetch_status_text(item_id)}")

    def write_md(self):
        """
        Write out the paths collect into a Markdown file.
        """

        # Sort the collection by name
        if self.collection:
            self.collection = dict(sorted(self.collection.items(), key=lambda item: item[1]))

        # Create the Markdown file (ensure the portal folder exists)
        self._md_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_list = self.md_helper()
        with open(self._md_path, 'w', encoding='utf-8', newline='\n') as md_file:
            md_file.write(markdown_list)

    def md_helper(self):
        markdown = []
        import time

        # Get scraped_date
        scraped_ts = getattr(self, 'scrapedTime', None)
        if scraped_ts:
             dt = datetime.fromtimestamp(scraped_ts / 1000.0)
             scraped_date = dt.strftime('%Y-%m-%d')
        else:
             now = datetime.now()
             scraped_date = now.strftime('%Y-%m-%d')

        # Add front matter
        front_matter_lines = ["---",
                              f"type: {self.type}",
                              f"name: '{self.name}'",
                              f"url: {self.url}",
                              f"date: {self.date}",
                              f"scraped_date: {scraped_date}",
                              "---"]
        markdown.append("\n".join(front_matter_lines))

        # The # main heading
        markdown.append(f"# [{self.name}]({self.url})")

        item_list = []
        if self.type == 'Paths' or self.type == 'paths':
            for item_id, item_name in self.collection.items():
                item_url = f"{BASE_URL_PATHS}/{item_id}"
                item_list.append(f"- [ ] `{item_id:>5}`: [(Web Link)]({item_url}) | {item_name}")
        markdown.append("\n".join(item_list))

        return "\n\n".join(markdown) + "\n"
