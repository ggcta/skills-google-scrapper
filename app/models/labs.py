from models.collection import Collection
from config.settings import BASE_URL_LAB


class Labs(Collection):
    """
    Class representing a collection of labs.
    """

    def __init__(self,
                 name: str = None,
                 url: str = BASE_URL_LAB,
                 date: str = None,
                 collection: dict = None):
        super().__init__(name, url, date, collection)
