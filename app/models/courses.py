from models.collection import Collection
from config.settings import BASE_URL_COURSES
from models.course import Course


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
    def fetch_data(self):        
        """
        Fetch data for all courses in the collection.
        """
        for course_id, course_name in self.collection.items():
            # Print out the course id and name as a heading title
            heading = f"{course_id} - {course_name.upper()}"
            print(f"\n\033[45m[{heading:<85}]\033[0m")

            # Start to fetch the course data
            a_course = Course(id=course_id)
            a_course.extract_transcript()
