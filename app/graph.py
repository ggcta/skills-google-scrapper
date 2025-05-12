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

    # Base directory for standalone files
    base_dir = 'data'

    # Add nodes for paths, courses, and labs
    for collection, coll_type in [(paths, 'path'), (courses, 'course'), (labs, 'lab')]:
        for item_id, title in collection.items():
            elements.append({
                "data": {
                    "id": f"{item_id}",
                    "name": title,
                    "group": coll_type
                }
            })

    # Add edges for relationships
    edge_id = 0

    # Paths to Courses
    for path_id, path_data in paths.items():
        path_file = os.path.join(base_dir, 'paths', f"{path_id}.json")
        if os.path.exists(path_file):
            with open(path_file) as f:
                path_details = json.load(f)
                # Add the path node
                elements.append({
                    "data": {
                        "id": f"{path_id}",
                        "label": path_details.get('name', f"Path {path_id}"),
                        "description": path_details.get('description', ''),
                        "datePublished": path_details.get('datePublished', ''),
                        "url": path_details.get('url', ''),
                        "type": path_details.get('type', 'path'),
                        "group": path_details.get('type', 'path')
                    }
                })
                # Add edges to courses
                if 'courses' in path_details:
                    for course_id in path_details['courses'].keys():
                        edge_id += 1
                        elements.append({
                            "data": {
                                "id": f"{edge_id}",
                                "source": f"{path_id}",
                                "target": f"{course_id}"
                            }
                        })
                else:
                    print(f"Warning: Path {path_id} does not have associated courses.")

    # Courses to Labs
    for course_id, course_name in courses.items():
        course_file = os.path.join(base_dir, 'courses', f"{course_id}.json")
        if os.path.exists(course_file):
            with open(course_file) as f:
                course_details = json.load(f)
                if 'modules' in course_details:  # Check for modules
                    for module in course_details['modules']:
                        if 'activities' in module:
                            for activity in module['activities']:
                                if activity.get('type') == 'lab':  # Check for lab type
                                    lab_id = activity.get('id')
                                    edge_id += 1
                                    elements.append({
                                        "data": {
                                            "id": f"{edge_id}",
                                            "source": f"{course_id}",
                                            "target": f"{lab_id}"
                                        }
                                    })

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
