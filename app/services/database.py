import os
import json
import datetime
import tempfile
from tinydb import TinyDB, Query
from tinydb.storages import Storage, touch
from config.settings import DATA_FOLDER_NAME, DEFAULT_PORTAL


class AtomicJSONStorage(Storage):
    """
    A TinyDB storage backend that writes database.json atomically.

    TinyDB's default JSONStorage writes in place (seek/write/truncate), so a
    Ctrl+C or crash mid-write can corrupt the database. This backend instead
    writes each snapshot to a temp file in the same directory, fsyncs it, and
    os.replace()s it over the target — an atomic swap on POSIX. It reads the
    file fresh on every call (no persistent handle), so a replaced file is
    always seen correctly.
    """

    def __init__(self, path: str, create_dirs=False, encoding='utf-8', **kwargs):
        super().__init__()
        self.path = path
        self.encoding = encoding
        self.kwargs = kwargs  # json.dump options such as indent
        touch(path, create_dirs=create_dirs)

    def read(self):
        with open(self.path, encoding=self.encoding) as handle:
            data = handle.read()
        if not data.strip():
            return None
        return json.loads(data)

    def write(self, data):
        directory = os.path.dirname(self.path) or '.'
        fd, tmp = tempfile.mkstemp(dir=directory, prefix='.tmp-', suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding=self.encoding, newline='\n') as handle:
                json.dump(data, handle, **self.kwargs)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    def close(self):
        pass


class Database:
    # One cached instance (and one database file) per portal, so the public
    # and partner catalogs are physically isolated and cannot overwrite each
    # other. Keying stays id-only *within* a portal.
    _instances = {}

    def __new__(cls, portal: str = DEFAULT_PORTAL):
        if portal not in cls._instances:
            instance = super(Database, cls).__new__(cls)
            instance._initialize(portal)
            cls._instances[portal] = instance
        return cls._instances[portal]

    def _initialize(self, portal: str):
        """Initialize the database by loading from file or creating default structure."""
        self.portal = portal
        # Per-portal storage root: data/<portal>/database.json
        self.db_path = os.path.join(DATA_FOLDER_NAME, portal, 'database.json')
        # Ensure the portal data folder exists so TinyDB can create the file
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # Use the atomic storage so an interrupted write can't corrupt the DB.
        self.db = TinyDB(self.db_path, storage=AtomicJSONStorage, indent=2, encoding='utf-8')
        
        # Ensure metadata exists
        self.metadata_table = self.db.table('metadata')
        if not self.metadata_table.all():
            self.update_metadata()

    def update_metadata(self):
        """Update the metadata table with app info and timestamp."""
        info = {
            'app_name': 'CSBHelper',
            'description': 'Google Skills Scraper',
            'version': '1.0.0',
            'site_url': 'https://www.skills.google/',
            'last_modified': datetime.datetime.now().isoformat()
        }
        # Assuming metadata is a single document, we upsert based on a fixed ID or clear and insert
        # For simplicity, clear and insert
        self.metadata_table.truncate()
        self.metadata_table.insert(info)

    def upsert(self, table_name: str, data: dict):
        """
        Update or insert a document into the specified table.
        Uses 'id' as the unique key.
        """
        table = self.db.table(table_name)
        doc_id = str(data.get('id'))
        
        if not doc_id:
            print(f"Error: Cannot upsert item without ID into {table_name}")
            return

        # Use Query to find existing document
        Item = Query()
        table.upsert(data, Item.id == doc_id)
        
        # Update metadata timestamp
        # self.update_metadata() # Avoid frequent writes, maybe just on batch?
        # For now, let's update timestamp in metadata without full rewrite if possible, 
        # but TinyDB doesn't support partial update easily without query. 
        # Let's skip metadata update on every single upsert for performance, 
        # or do it if it's critical. 
        # User requested: "update will be saved back to the data/database.json"
        # So we should probably keep it up to date.
        
        # Optimization: Only update metadata if enough time passed? 
        # Or just update it.
        # self.update_metadata() 

    def search(self, table_name: str, query_str: str, field: str | None = None):
        """
        Search for documents in the specified table matching the query string.
        Returns a list of matching documents (values).
        """
        table = self.db.table(table_name)
        results = []
        
        query_str_lower = query_str.lower()
        
        # TinyDB search is robust but for free-text search across fields or specific field
        # we might need to iterate or use custom test.
        # Iterating all documents is similar to what we did before.
        
        all_items = table.all()
        for item in all_items:
            if field:
                val = item.get(field)
                if val:
                    # Handle list fields (e.g. topics)
                    if isinstance(val, list):
                         # check if query is in any of the list items
                         if any(query_str_lower in str(v).lower() for v in val):
                             results.append(item)
                    elif query_str_lower in str(val).lower():
                        results.append(item)
            else:
                # Search across the whole document
                if query_str_lower in str(item).lower():
                    results.append(item)
                    
        return results

    def get(self, table_name: str, doc_id: str):
        """Get a document by ID."""
        table = self.db.table(table_name)
        Item = Query()
        result = table.search(Item.id == str(doc_id))
        return result[0] if result else None

    def all(self, table_name: str):
        """Get all documents from a table."""
        table = self.db.table(table_name)
        return table.all()
    
    def close(self):
        self.db.close()
