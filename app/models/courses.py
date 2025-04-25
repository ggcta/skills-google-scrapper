from models.collection import Collection
from config.settings import BASE_URL_COURSES


class Courses(Collection):
    """
    Class representing a collection of courses.
    """

    def __init__(self,
                 name: str = None,
                 url: str = BASE_URL_COURSES,
                 collection: dict = None):
        super().__init__(name, url, collection)

    # TODO: fetch_data() method to refresh all the courses' data.
