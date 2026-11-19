import os, time, requests, psutil, docker
from flask import Flask, jsonify, render_template
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
REQUESTS = Counter("dashboard_requests_total", "Total API requests")
PROJECT = os.getenv("COMPOSE_PROJECT", "devops-dashboard")
REPO = os.getenv("GITHUB_REPO", "prerit09/devops-dashboard")
TOKEN = os.getenv("GITHUB_TOKEN")  # optional, raises rate limit
START = time.time()

try:
    dclient = docker.from_env()
except Exception:
    dclient = None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/system")
def system():
    REQUESTS.inc()
    return jsonify(
        cpu=psutil.cpu_percent(interval=0.2),
        memory=psutil.virtual_memory().percent,
        disk=psutil.disk_usage("/").percent,
        uptime_min=round((time.time() - START) / 60),
    )

@app.route("/api/containers")
@app.route("/api/containers")
def containers():
    REQUESTS.inc()
    if not dclient:
        return jsonify(error="Docker not reachable"), 503
    result = []
    for c in dclient.containers.list(
            all=True,
            filters={"label": f"com.docker.compose.project={PROJECT}"}):
        image = c.attrs.get("Config", {}).get("Image", "unknown")
        result.append({"name": c.name, "status": c.status, "image": image})
    return jsonify(result)

@app.route("/api/pipelines")
def pipelines():
    REQUESTS.inc()
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    r = requests.get(
        f"https://api.github.com/repos/{REPO}/actions/runs?per_page=5",
        headers=headers, timeout=5)
    runs = r.json().get("workflow_runs", [])
    return jsonify([
        {"id": x["run_number"], "branch": x["head_branch"], "name": x["name"],
         "status": x["conclusion"] or x["status"], "url": x["html_url"]}
        for x in runs
    ])

@app.route("/health")
def health():
    return jsonify(status="ok")

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)