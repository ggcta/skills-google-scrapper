from models.collection import Collection
from config.settings import BASE_URL_PATHS


class Paths(Collection):
    """
    Class representing a collection of paths.
    """

    def __init__(self,
                 name: str = None,
                 url: str = BASE_URL_PATHS,
                 date: str = None,
                 collection: dict = None):
        super().__init__(name, url, date, collection)

