from models.collection import Collection
from config.settings import BASE_URL_COURSES


class Courses(Collection):
    """
    Class representing a collection of courses.
    """

    def __init__(self,
                 name: str = None,
                 url: str = BASE_URL_COURSES,
                 date: str = None,
                 collection: dict = None):
        super().__init__(name, url, date, collection)
