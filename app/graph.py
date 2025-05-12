# app.py
import json
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# load data once
with open('data/courses.json') as f: courses = json.load(f)['collection']
with open('data/labs.json')    as f: labs    = json.load(f)['collection']
with open('data/paths.json')   as f: paths   = json.load(f)['collection']

def build_cyto_graph():
    elements = []
    # add nodes
    for coll, typ in [(courses,'course'), (labs,'lab'), (paths,'path')]:
        for id_, title in coll.items():
            elements.append({
                "data": {
                    "id": f"{typ}_{id_}",
                    "label": title,
                    "group": typ
                }
            })
    # add edges between any shared IDs
    from collections import defaultdict
    seen = defaultdict(list)
    for el in elements:
        gid, grp = el['data']['id'], el['data']['group']
        seen[gid.split('_',1)[1]].append(gid)
    edge_id = 0
    for id_, uids in seen.items():
        if len(uids) > 1:
            for i in range(len(uids)):
                for j in range(i+1, len(uids)):
                    edge_id += 1
                    elements.append({
                        "data": {
                            "id": f"e{edge_id}",
                            "source": uids[i],
                            "target": uids[j]
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
