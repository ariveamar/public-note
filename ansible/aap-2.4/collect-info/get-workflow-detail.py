#!/usr/bin/env python3
import csv, os, sys, requests, urllib3
urllib3.disable_warnings()

if len(sys.argv) != 2 or not sys.argv[1].isdigit():
    sys.exit(f"Usage: {sys.argv[0]} <workflow template ID>")

WF_ID = int(sys.argv[1])

AAP  = os.environ.get("AAP_URL", "https://aap.example.com")  # controller URL
AUTH = (os.environ["AAP_USER"], os.environ["AAP_PASS"])
API  = f"{AAP}/api/v2"   # Controller 4.5.x (AAP 2.4): no /api/controller prefix

TYPE_MAP = {
    "job": "job_template",
    "workflow_job": "workflow_job_template",
    "project_update": "project_sync",
    "inventory_update": "inventory_source",
    "workflow_approval": "workflow_approval",
    "system_job": "system_job_template",
}

session = requests.Session()
session.auth = AUTH
session.verify = False

def get_one(path, params=None):
    r = session.get(path if path.startswith("http") else AAP + path, params=params)
    r.raise_for_status()
    return r.json()

def get_all(url, params=None):
    while url:
        d = get_one(url, params)
        yield from d["results"]
        url = d.get("next")
        params = None  # 'next' URL already carries the query string

_jt_cache = {}

def job_template(jt_id):
    if jt_id not in _jt_cache:
        _jt_cache[jt_id] = get_one(f"{API}/job_templates/{jt_id}/")
    return _jt_cache[jt_id]

# Fetch the workflow directly by ID
try:
    wf = get_one(f"{API}/workflow_job_templates/{WF_ID}/")
except requests.HTTPError as e:
    r = e.response
    sys.exit(f"HTTP {r.status_code} for {r.url}\n{r.text[:300]}")

w = csv.writer(sys.stdout)
w.writerow(["workflow_template", "node_alias", "node_type", "resource_name", "playbook"])

for n in get_all(f"{API}/workflow_job_templates/{WF_ID}/workflow_nodes/",
                 {"page_size": 200}):
    ujt = n.get("summary_fields", {}).get("unified_job_template", {})
    raw_type = ujt.get("unified_job_type", "")
    ntype = TYPE_MAP.get(raw_type, raw_type or "n/a")
    ujt_id = ujt.get("id")

    playbook = ""
    try:
        if ntype == "job_template" and ujt_id:
            playbook = job_template(ujt_id).get("playbook", "")
    except requests.HTTPError as e:
        print(f"WARN: {wf['name']} / {n.get('identifier')}: {e}", file=sys.stderr)

    w.writerow([wf["name"], n.get("identifier"), ntype,
                ujt.get("name", "n/a"), playbook])
