from models.collection import Collection
from config.settings import BASE_URL


class Topics(Collection):
    """
    Class representing a collection of topics.
    """

    def __init__(self,
                 name: str = None,
                 url: str = BASE_URL,
                 date: str = None,
                 collection: dict = None):
        super().__init__(name, url, date, collection)

    def to_dict(self):
        """
        Convert the Topics object to a dictionary representation.\n
        Sort the collection by keys.\n
        """

        # Sort the collection by keys
        if self.collection:
            self.collection = dict(sorted(self.collection.items()))

        return {
            "name": self.name,
            "url": self.url,
            "date": self.date,
            "collection": self.collection
        }
