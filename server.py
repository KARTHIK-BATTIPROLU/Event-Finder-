"""
server.py — EventRadar Web Application Server (Flask).

Provides:
  - GET /               : Web UI dashboard
  - GET /api/events     : JSON list of events with query/filter params
  - GET /api/stats      : JSON aggregate stats
  - POST /api/run       : Trigger background scrape run
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

from flask import Flask, jsonify, render_template, request

from eventradar import config, db
from eventradar.runner import run_pipeline

app = Flask(__name__, template_folder="templates", static_folder="static")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eventradar.server")

# Global background run lock
_run_lock = threading.Lock()
_run_status = {"running": False, "last_result": None}


def _clean_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert MongoDB _id to string for JSON serialization."""
    doc["_id"] = str(doc.get("_id", ""))
    return doc


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/events")
def get_events():
    scope = request.args.get("scope")
    category = request.args.get("category")
    city = request.args.get("city")
    event_type = request.args.get("event_type")
    search = request.args.get("q")
    limit = int(request.args.get("limit", "200"))

    query: dict[str, Any] = {}

    if scope and scope != "all":
        query["scope"] = scope.lower()
    if category and category != "all":
        query["category"] = category.lower()
    if city and city != "all":
        query["city"] = city.lower()
    if event_type and event_type != "all":
        query["event_type"] = event_type.lower()
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"organizer": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
            {"venue": {"$regex": search, "$options": "i"}},
        ]

    try:
        col = db.get_events_col()
        cursor = col.find(query).sort("start_date", 1).limit(limit)
        events = [_clean_doc(d) for d in cursor]
        return jsonify({"count": len(events), "events": events})
    except Exception as exc:
        logger.error("Error fetching events: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/stats")
def get_stats():
    try:
        db.ensure_indexes()
        data = db.stats()
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/run", methods=["POST"])
def trigger_run():
    global _run_status
    if not _run_lock.acquire(blocking=False):
        return jsonify({"message": "A scrape run is already in progress.", "running": True}), 409

    def _async_run():
        global _run_status
        try:
            _run_status["running"] = True
            results = run_pipeline()
            _run_status["last_result"] = [
                {
                    "name": r.name,
                    "found": r.items_found,
                    "stored": r.items_stored,
                    "status": r.status,
                }
                for r in results
            ]
        finally:
            _run_status["running"] = False
            _run_lock.release()

    t = threading.Thread(target=_async_run, daemon=True)
    t.start()
    return jsonify({"message": "Scrape run started in background.", "running": True})


if __name__ == "__main__":
    db.ensure_indexes()
    print("\n" + "=" * 60)
    print(" EventRadar Web App running at: http://127.0.0.1:5000")
    print("=" * 60 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
