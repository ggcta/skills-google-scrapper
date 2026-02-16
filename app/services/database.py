from tinydb import TinyDB, Query
from config.settings import DATA_FOLDER_NAME
import os

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            # Initialize TinyDB
            db_path = os.path.join(DATA_FOLDER_NAME, 'database.json')
            cls._instance.db = TinyDB(db_path)
            # Initialize metadata if empty
            cls._instance.update_metadata()
        return cls._instance

    def update_metadata(self):
        """Update the metadata table with app info and timestamp."""
        import datetime
        metadata_table = self.db.table('metadata')
        
        info = {
            'app_name': 'CSBHelper',
            'description': 'Google Cloud Skills Boost Helper and Scraper',
            'version': '1.0.0',
            'site_url': 'https://www.skills.google/',
            'last_modified': datetime.datetime.now().isoformat()
        }
        
        # We only need one record for app info
        metadata_table.upsert(info, Query().app_name == 'CSBHelper')

    def upsert(self, table_name: str, data: dict):
        """
        Update or insert a document into the specified table.
        Uses 'id' as the unique key.
        auto-updates metadata.
        """
        table = self.db.table(table_name)
        User = Query()
        # Convert id to string just in case
        doc_id = str(data.get('id'))
        
        # Check if exists
        if table.search(User.id == doc_id):
            table.update(data, User.id == doc_id)
        else:
            table.insert(data)
            
        # Update metadata timestamp on every change
        
        # We should call update_metadata only if table_name != 'metadata' to be safe, 
        # though logic separates them.
        if table_name != 'metadata':
             self.update_metadata()

    def search(self, table_name: str, query_str: str, field: str = None):
        """
        Search for documents in the specified table matching the query string.
        If field is provided, searches only in that field.
        """
        table = self.db.table(table_name)
        User = Query()
        
        # Define a custom test function for case-insensitive partial match
        def match_func(val, query):
            return query.lower() in str(val).lower() if val else False

        if field:
            # Search in specific field
            results = table.search(User[field].test(match_func, query_str))
        else:
            # Search across the whole document using a lambda
            # table.search accepts a query OR a condition function
            results = table.search(lambda doc: query_str.lower() in str(doc).lower())
            
        return results

    def get(self, table_name: str, doc_id: str):
        """Get a document by ID."""
        table = self.db.table(table_name)
        User = Query()
        return table.get(User.id == str(doc_id))

    def all(self, table_name: str):
        """Get all documents from a table."""
        return self.db.table(table_name).all()
