import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)
load_dotenv()
CORS(app)

# Load environment variables
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME")

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
events_col = db["events"]

@app.route("/")
def home():
    return "✅ Webhook backend is running!"
from flask import request

@app.route("/events/latest", methods=["GET"])
def get_latest_events():
    """Fetch new events after a given timestamp"""
    since = request.args.get("since")
    try:
        if since:
            since_dt = datetime.strptime(since, "%Y-%m-%d %H:%M:%S")
        else:
            since_dt = datetime.utcnow()
    except Exception as e:
        print("Timestamp parse error:", e)
        since_dt = datetime.utcnow()

    events = list(events_col.find({"timestamp": {"$gt": since_dt}}).sort("timestamp", -1))
    for e in events:
        e["_id"] = str(e["_id"])
        e["timestamp"] = e["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
    return jsonify(events)

@app.route("/webhook", methods=["POST"])
def github_webhook():
    try:
        event_type = request.headers.get("X-GitHub-Event")
        data = request.get_json(force=True)

        event_doc = None

        if event_type == "push":
            author = data.get("pusher", {}).get("name") or data.get("pusher", {}).get("login")
            to_branch = data.get("ref", "").split("/")[-1]
            timestamp = parse_iso(data.get("head_commit", {}).get("timestamp"))
            event_doc = {
                "type": "push",
                "author": author,
                "from_branch": None,
                "to_branch": to_branch,
                "timestamp": timestamp
            }

        elif event_type == "pull_request":
            action = data.get("action")
            pr = data.get("pull_request", {})
            author = pr.get("user", {}).get("login")
            from_branch = pr.get("head", {}).get("ref")
            to_branch = pr.get("base", {}).get("ref")

            if action == "opened":
                timestamp = parse_iso(pr.get("created_at"))
                event_doc = {
                    "type": "pull_request",
                    "author": author,
                    "from_branch": from_branch,
                    "to_branch": to_branch,
                    "timestamp": timestamp
                }

            elif action == "closed" and pr.get("merged"):
                timestamp = parse_iso(pr.get("merged_at"))
                event_doc = {
                    "type": "merge",
                    "author": author,
                    "from_branch": from_branch,
                    "to_branch": to_branch,
                    "timestamp": timestamp
                }

        if event_doc:
            events_col.insert_one(event_doc)
            return jsonify({"message": f"{event_doc['type']} event saved"}), 200
        else:
            return jsonify({"message": "Event ignored or unsupported"}), 200

    except Exception as e:
        print("Webhook error:", e)
        return jsonify({"error": "Server error"}), 500

def parse_iso(timestr):
    """Parses ISO 8601 with or without timezone"""
    if timestr:
        try:
            return datetime.fromisoformat(timestr.replace("Z", "+00:00"))
        except:
            pass
    return datetime.utcnow()

@app.route("/events", methods=["GET"])
def get_events():
    """Return the 10 most recent events for frontend"""
    events = list(events_col.find().sort("timestamp", -1).limit(10))
    for e in events:
        e["_id"] = str(e["_id"])
        if isinstance(e["timestamp"], datetime):
            e["timestamp"] = e["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
    return jsonify(events)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
