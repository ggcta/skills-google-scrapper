# app.py
import json
from flask import Flask, render_template, jsonify
from pathlib import Path

app = Flask(__name__)

# load once at startup
with open('data/courses.json') as f: courses = json.load(f)['collection']
with open('data/labs.json')    as f: labs    = json.load(f)['collection']
with open('data/paths.json')   as f: paths   = json.load(f)['collection']

def build_graph():
    nodes = []
    links = []
    # helper to append nodes
    for coll, label in [(courses,'course'), (labs,'lab'), (paths,'path')]:
        for id_, title in coll.items():
            nodes.append({
                "id": id_,
                "group": label,
                "title": title
            })
    # connect any duplicate IDs across collections
    from collections import defaultdict
    seen = defaultdict(list)
    for n in nodes:
        seen[n['id']].append(n['group'])
    for id_, groups in seen.items():
        # if appears in multiple types, fully connect them
        if len(groups) > 1:
            for i in range(len(groups)):
                for j in range(i+1, len(groups)):
                    links.append({
                        "source": id_ + "_" + groups[i],
                        "target": id_ + "_" + groups[j]
                    })
    # however D3 needs numeric or unique ids, so we’ll mangle node IDs:
    # e.g. "1281_course", etc.
    for n in nodes:
        n['uid'] = f"{n['id']}_{n['group']}"
    return {"nodes": nodes, "links": links}

@app.route('/graph-data')
def graph_data():
    return jsonify(build_graph())

@app.route('/')
def index():
    return render_template('graph.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
