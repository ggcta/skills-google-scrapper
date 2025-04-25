import threading
import time
from flask import Flask, request, jsonify, render_template, url_for
from config.settings import BASE_URL, BASE_URL_COURSES, BASE_URL_LAB, BASE_URL_PATHS
from models.labs import Labs
from models.courses import Courses
from models.paths import Paths
from models.topics import Topics
from models.course import Course
from models.lab import Lab
from models.path import Path


# Initialize collections
paths_collection = Paths(name='Paths')
courses_collection = Courses(name='Courses')
labs_collection = Labs(name='Labs')
topics_collection = Topics(name='Topics')


# Load data into collections
paths_collection.load_json()
courses_collection.load_json()
labs_collection.load_json()
topics_collection.load_json()

# Initialize topics and topics_to_courses as empty data structures
# topics_collection.collection = {}

# --- New: Add a lock for thread safety ---
topics_lock = threading.Lock()

# TODO: save topics to a file, load them from a file next run, and save them to a file after every refresh.
def extract_topics(courses_collection):
    """
    Gather all unique topics from the downloaded courses in the 'data/courses/' folder.

    :param courses_collection: The collection of courses.
    :return: A sorted list of unique topics.
    """

    if not isinstance(courses_collection.collection, dict):
        raise TypeError("courses_collection.collection must be a dictionary")

    for course_id, course_name in courses_collection.collection.items():  # Updated to use items()
        # course_file = courses_folder / f"{course_id}.json"  # Construct the file path
        course = Course(id=course_id)  # Create a new Course instance

        # Check if the course JSON file exists
        if course._json_path.exists():
            course.load_json()  # Load the JSON file

            # If course.topics is not None/empty
            if course.topics:
                for topic in course.topics:
                    # Ensure the topic is a string
                    if not isinstance(topic, str):
                        raise ValueError(f"Topic '{topic}' is not a string")
                    if topic not in topics_collection.collection:
                        topics_collection.collection[topic] = {}
                    topics_collection.collection[topic][course_id] = course_name  # Map topic to course name directly

        # Skip if the file does not exist
        else:
            continue

        # Save the topics collection to file.
        topics_collection.save_json()


def refresh_topics(interval=300):
    """
    Periodically refresh the topics every 5 minutes (300 seconds).
    """
    # This function runs in a separate thread to refresh topics
    # every hour without blocking the main thread

    # Set the interval for refreshing topics
    while True:
        print("Refreshing topics...")
        time.sleep(interval)  # Wait for the specified interval
        extract_topics(courses_collection)  # Refresh topics


def initialize_app():
    """
    Initialize the Flask app, including loading data and extracting initial topics.
    """

    print("Initializing app...")
    extract_topics(courses_collection)
    print("App initialized.")

# Initialize the app before creating the Flask instance
initialize_app()

app = Flask(__name__)

# Define the context processor AFTER topics is updated
@app.context_processor
def inject_global_data():
    """
    Inject global data into all templates.
    """
    # --- New: Acquire the lock before accessing shared data ---
    with topics_lock:
        current_topics = topics_collection.collection.keys()
        current_labs = labs_collection.collection.copy()
        current_courses = courses_collection.collection.copy()
        current_paths = paths_collection.collection.copy()

    return {
        'labs': current_labs,
        'courses': current_courses,
        'paths': current_paths,
        'topics': current_topics,
        'BASE_URL_LAB': BASE_URL_LAB,
        'BASE_URL_COURSES': BASE_URL_COURSES,
        'BASE_URL_PATHS': BASE_URL_PATHS,
        'BASE_URL': BASE_URL
    }

@app.route('/')
def home():
    """
    Home page for the Cloud Skills Boost Helper.
    """

    return render_template(
        'search.html'
    )

@app.route('/courses')
def courses():
    """
    Display all courses available in the collection.
    """

    # Get all courses
    courses = courses_collection.collection

    # Generate breadcrumbs for navigation
    breadcrumbs = generate_breadcrumbs()

    return render_template(
        'courses.html',
        courses=courses,
        breadcrumbs=breadcrumbs
    )

@app.route('/courses/<course_id>')
def course(course_id):
    """
    Display details of a specific course.
    """

    # Ensure the course does exist
    course = courses_collection.collection.get(course_id)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    # Get the course's data
    course = Course(id=course_id)
    course.load_json()

    # Generate breadcrumbs for navigation
    breadcrumbs = generate_breadcrumbs()

    return render_template(
        'course.html',
        course=course,
        breadcrumbs=breadcrumbs
    )

@app.route('/paths')
def paths():
    """
    Display all paths available in the collection.
    """

    # Get all paths
    paths = paths_collection.collection

    # Generate breadcrumbs for navigation
    breadcrumbs = generate_breadcrumbs()

    return render_template(
        'paths.html',
        paths=paths,
        breadcrumbs=breadcrumbs
    )

@app.route('/paths/<path_id>')
def path(path_id):
    """
    Display details of a specific path.
    """
    path = paths_collection.collection.get(path_id)
    if not path:
        return jsonify({"error": "Path not found"}), 404

    # Load path data
    path_data = Path(id=path_id)
    path_data.load_json()

    # Generate breadcrumbs for navigation
    breadcrumbs = generate_breadcrumbs()

    return render_template(
        'path.html',
        path=path_data,
        breadcrumbs=breadcrumbs
    )


@app.route('/labs')
def labs():
    """
    Display all labs available in the collection.
    """

    # Get all labs
    labs = labs_collection.collection

    # Generate breadcrumbs for navigation
    breadcrumbs = generate_breadcrumbs()

    return render_template(
        'labs.html',
        labs=labs,
        breadcrumbs=breadcrumbs
    )

@app.route('/labs/<lab_id>')
def lab(lab_id):
    # Logic to fetch and display lab details

    lab = labs_collection.collection.get(lab_id)
    if not lab:
        return jsonify({"error": "Lab not found"}), 404

    # Load lab data
    lab_data = Lab(id=lab_id)
    lab_data.load_json()

    # Generate breadcrumbs for navigation
    breadcrumbs = generate_breadcrumbs()

    return render_template(
        'lab.html',
        lab=lab_data,
        breadcrumbs=breadcrumbs
    )


@app.route('/course/<course_id>/extract_transcript', methods=['POST'])
def extract_transcript(course_id):
    """
    Extract the transcript for a course.
    """
    course = Course(id=course_id)
    course.extract_transcript()
    return jsonify({"message": f"Transcript for course {course_id} extracted."})


@app.route('/topics')
def topics():
    """
    Display all available topics.
    """

    # Generate breadcrumbs for navigation
    breadcrumbs = generate_breadcrumbs()

    return render_template(
        'topics.html',
        # topics=,
        breadcrumbs=breadcrumbs
    )

@app.route('/topics/<topic>')
def topic(topic):
    """
    filtered_courses = topics_to_courses.get(topic, [])

    This route filters and displays courses associated with the given topic.
    """
    # Filter courses, paths, and labs by the selected topic
    topic_to_courses = topics_collection.collection.get(topic, {})

    # Generate breadcrumbs for navigation
    breadcrumbs = generate_breadcrumbs()

    return render_template(
        'topic.html',
        topic=topic,
        filtered_courses=topic_to_courses,
        breadcrumbs=breadcrumbs
    )

@app.route('/search')
def search():
    """
    Search page for the Cloud Skills Boost Helper.
    This page allows users to search for courses, paths, and
    any keywords.
    """
    return render_template('search.html')

@app.route('/search_for')
def search_for():
    """
    Search for a certain keyword.
    """
    query = request.args.get('q', '')
    if not query or len(query.strip()) < 2:
        return jsonify([])

    results = []
    query_lower = query.lower()

    for course_id, course_name in courses_collection.collection.items():
        if query_lower in course_id or query_lower in course_name.lower():
            results.append({
                "id": course_id,
                "name": course_name,
                "url": url_for('course', course_id=course_id),
                "type": "Course"
            })

    for lab_id, lab_name in labs_collection.collection.items():
        if query_lower in lab_id or query_lower in lab_name.lower():
            results.append({
                "id": lab_id,
                "name": lab_name,
                "url": url_for('lab', lab_id=lab_id),
                "type": "Lab"
            })

    for path_id, path_name in paths_collection.collection.items():
        if query_lower in path_id or query_lower in path_name.lower():
            results.append({
                "id": path_id,
                "name": path_name,
                "url": url_for('path', path_id=path_id),
                "type": "Path"
            })
    for topic in topics_collection.collection.keys():
        if query_lower in topic.lower():
            results.append({
                "id": None,
                "name": topic,
                "url": url_for('topic', topic=topic),
                "type": "Topic"
            })

    # results = search_items(query)
    return jsonify(results)

@app.route('/about')
def about():
    """About page for the Cloud Skills Boost Helper.
    This page provides information about the application, its purpose, and how to use it.
    It may also include links to documentation, support, or contact information.
    The about page is typically static and does not require any dynamic data from the database.
    It serves as a reference for users to understand the application better.

    Returns:
        str: Rendered HTML template for the about page.
    """
    # Generate breadcrumbs for navigation
    breadcrumbs = generate_breadcrumbs()
    return render_template('about.html', breadcrumbs=breadcrumbs)


def generate_breadcrumbs():
    """
    Generate breadcrumb segments based on the current path.
    """
    path = request.path.strip('/').split('/')
    breadcrumbs = []
    current_path = ''
    for segment in path:
        current_path += f'/{segment}'
        breadcrumbs.append({
            'name': segment.capitalize(),  # Capitalize the segment for display
            'url': current_path
        })
    return breadcrumbs


# Test layout with Materialize
@app.route('/layout')
def layout():
    return render_template('layout.html')

# Start the background thread for periodic refresh
refresh_thread = threading.Thread(target=refresh_topics, daemon=True)
refresh_thread.start()

if __name__ == '__main__':
    # Run the Flask app
    app.run(host='0.0.0.0', port=8080, debug=True)
