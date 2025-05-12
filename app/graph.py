# app.py
import json
import os
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# load data once
with open('data/courses.json') as f: courses = json.load(f)['collection']
with open('data/labs.json')    as f: labs    = json.load(f)['collection']
with open('data/paths.json')   as f: paths   = json.load(f)['collection']

def build_cyto_graph():
    elements = []
    added_nodes = set()  # Set to track added node IDs

    # Base directory for standalone files
    base_dir = 'data'

    # Paths to Courses
    for path_id in paths.keys():
        path_file = os.path.join(base_dir, 'paths', f"{path_id}.json")
        if os.path.exists(path_file):
            with open(path_file) as f:
                path_details = json.load(f)
                # Add the path node
                if f"{path_id}" not in added_nodes:
                    # Add the path node
                    elements.append({
                        "data": {
                            "id": f"{path_id}",
                            "name": path_details.get('name', f"Path {path_id}"),
                            "type": path_details.get('type', 'Path'),
                        }
                    })
                    # Add the path node to the set
                    added_nodes.add(f"{path_id}")  # Mark the path node as added

                # Add edges to courses
                if 'courses' in path_details:
                    for course_id in path_details['courses'].keys():
                        course_file = os.path.join(base_dir, 'courses', f"{course_id}.json")
                        if os.path.exists(course_file):
                            with open(course_file) as f:
                                course_details = json.load(f)
                                # Add the course node
                                if f"{course_id}" not in added_nodes:
                                    elements.append({
                                        "data": {
                                            "id": f"{course_id}",
                                            "name": course_details.get('name', f"Course {course_id}"),
                                            "type": course_details.get('type', 'Course'),
                                        }
                                    })
                                    added_nodes.add(f"{course_id}")  # Mark the course node as added

                                # Create edge between path and course
                                elements.append({
                                    "data": {
                                        "id": f"p{path_id}_c{course_id}",
                                        "name": f"p{path_id}_c{course_id}",
                                        "source": f"{path_id}",
                                        "target": f"{course_id}"
                                    }
                                })

                                # Add edges to labs
                                for module in course_details['modules']:
                                    for step in module['steps']:
                                        for activity in step['activities']:
                                            if activity.get('type') == 'lab':  # Check for lab type
                                                lab_id = activity.get('id')
                                                lab_title = activity.get('title', f"Lab {lab_id}")
                                                if f"{lab_id}" not in added_nodes:
                                                    elements.append({
                                                        "data": {
                                                            "id": f"{lab_id}",
                                                            "name": lab_title,
                                                            "type": "Lab",
                                                        }
                                                    })
                                                    added_nodes.add(f"{lab_id}")  # Mark the lab node as added

                                                    # Create edge between course and lab
                                                    elements.append({
                                                        "data": {
                                                            "id": f"c{course_id}_l{lab_id}",
                                                            "name": f"c{course_id}_l{lab_id}",
                                                            "source": f"{course_id}",
                                                            "target": f"{lab_id}"
                                                        }
                                                    })

    with open('data/graph.json', 'w') as f:
        json.dump(elements, f, indent=2)

    return {"elements": elements}

@app.route('/graph-data')
def graph_data():
    return jsonify(build_cyto_graph())

@app.route('/')
def index():
    return render_template('graph.html')

if __name__ == '__main__':
    # Run the Flask app
    app.run(host='0.0.0.0', port=8080, debug=True)
