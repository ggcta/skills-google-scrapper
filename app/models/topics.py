from datetime import datetime

from typing_extensions import override

from models.course import Course
from models.serialize import Serialize
from config.settings import BASE_URL, DEFAULT_PORTAL


# A topics collection has a different shape than Collection's {id: name}:
# {topic: {course_id: course_name}}. Kept as its own class rather than
# forcing Collection to be generic just for this one nested case.
class Topics(Serialize):
    """
    Class representing a collection of topics.
    """

    # Only set inside save_json(), so it's absent until the first save;
    # declared here (not assigned) so hasattr()/to_dict() reflect that.
    scrapedTime: int  # pyright: ignore[reportUninitializedInstanceVariable]

    def __init__(self,
                 name: str | None = None,
                 url: str = BASE_URL,
                 collection: dict[str, dict[str, str]] | None = None):
        self.name = name
        self.portal = DEFAULT_PORTAL
        self.url = url
        self.date = str(datetime.today().date())
        self.collection: dict[str, dict[str, str]] = collection or {}

    @property
    def type(self):
        """
        Override the type property to return the class name.
        """
        return self.__class__.__name__

    @override
    def to_dict(self):
        """
        Convert the Topics object to a dictionary representation.\n
        Sort the collection by keys.\n
        """

        # Sort the collection by keys
        if self.collection:
            self.collection = dict(sorted(self.collection.items()))

        return {
            "type": self.type,
            "name": self.name,
            "url": self.url,
            "date": self.date,
            "collection": self.collection
        }

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

            table_name = self.type.lower()

            if self.collection:
                for topic, courses in self.collection.items():
                    doc = {
                        'id': topic,
                        'name': courses.get('name', 'Unknown'),
                        'type': table_name,
                        'portal': self.portal
                    }
                    db.upsert(table_name, doc)

        except Exception as e:
            print(f"(Topics.save_json) Error syncing to DB: {e}")

    def extract_topics(self, course_collection: dict[str, str]):
        """
        Gather all unique topics from the downloaded courses.

        :param courses_collection: `Courses.collection`.
        """

        # Runtime guard for callers that bypass the type hint (e.g. dynamic
        # or external callers); statically always true given the signature.
        if not isinstance(course_collection, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("The course_collection must be of type dict.")  # pyright: ignore[reportUnreachable]

        for course_id, course_name in course_collection.items():
            course = Course(id=course_id)

            if course._json_path.exists():
                course.load_json()

                if course.topics:
                    for topic in course.topics:
                        if topic not in self.collection:
                            self.collection[topic] = {}
                        self.collection[topic][course_id] = course_name

        self.save_json()
