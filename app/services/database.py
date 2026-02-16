import json
import os
import shutil
import tempfile
import datetime
from config.settings import DATA_FOLDER_NAME

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the database by loading from file or creating default structure."""
        self.db_path = os.path.join(DATA_FOLDER_NAME, 'database.json')
        self.data = {
            "metadata": {},
            "courses": {},
            "paths": {},
            "labs": {}
        }
        self._load()
        # Ensure metadata exists
        if not self.data.get("metadata"):
            self.update_metadata()

    def _load(self):
        """Load data from the JSON file."""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # Merge loaded data with default structure to ensure all keys exist
                    self.data.update(loaded_data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading database: {e}. Starting with empty database.")

    def save(self):
        """Save data to the JSON file atomically."""
        # Update metadata timestamp before saving
        # But we handle metadata update separately in update_metadata usually.
        # However, to ensure last_modified is accurate on every save, we could update it here.
        # For now, let's rely on explicit calls or just update the timestamp.
        # Refactoring note: user wanted simple structure.
        
        try:
            # Atomic write: write to temp file then rename
            with tempfile.NamedTemporaryFile('w', dir=os.path.dirname(self.db_path), delete=False, encoding='utf-8') as tf:
                json.dump(self.data, tf, ensure_ascii=False, indent=2)
                tempname = tf.name
            
            os.replace(tempname, self.db_path)
        except IOError as e:
            print(f"Error saving database: {e}")
            if os.path.exists(tempname):
                os.remove(tempname)

    def update_metadata(self):
        """Update the metadata table with app info and timestamp."""
        info = {
            'app_name': 'CSBHelper',
            'description': 'Google Cloud Skills Boost Helper and Scraper',
            'version': '1.0.0',
            'site_url': 'https://www.skills.google/',
            'last_modified': datetime.datetime.now().isoformat()
        }
        self.data['metadata'] = info
        self.save()

    def upsert(self, table_name: str, data: dict):
        """
        Update or insert a document into the specified table.
        Uses 'id' as the unique key.
        """
        if table_name not in self.data:
            self.data[table_name] = {}
            
        doc_id = str(data.get('id'))
        if not doc_id:
            print(f"Error: Cannot upsert item without ID into {table_name}")
            return

        self.data[table_name][doc_id] = data
        
        # Update metadata whenever we modify data
        # We don't call update_metadata() to avoid double save, just update the timestamp
        # But for simplicity, let's just call update_metadata() which saves.
        # Or better: update dict and save once.
        self.data['metadata']['last_modified'] = datetime.datetime.now().isoformat()
        self.save()

    def search(self, table_name: str, query_str: str, field: str = None):
        """
        Search for documents in the specified table matching the query string.
        Returns a list of matching documents (values).
        """
        if table_name not in self.data:
            return []
            
        table_data = self.data[table_name]
        results = []
        
        query_str_lower = query_str.lower()
        
        for item in table_data.values():
            if field:
                val = item.get(field)
                if val and query_str_lower in str(val).lower():
                    results.append(item)
            else:
                # Search across the whole document
                if query_str_lower in str(item).lower():
                    results.append(item)
                    
        return results

    def get(self, table_name: str, doc_id: str):
        """Get a document by ID."""
        if table_name in self.data:
            return self.data[table_name].get(str(doc_id))
        return None

    def all(self, table_name: str):
        """Get all documents from a table."""
        if table_name in self.data:
            return list(self.data[table_name].values())
        return []
