from flask import Flask, request, jsonify, render_template, make_response
from datetime import datetime, timedelta
import os
import json

app = Flask(__name__)

LOCK_FILE = "hw_locks.json"
DEFAULT_TIMEOUT = 60  # Default timeout in minutes
MACHINES = ["Machine 1", "Machine 2", "Machine 3", "Machine 4"]
USERS = ["Ahmed", "Mohamed", "Sara", "Youssef"]  # Add your user list here

def load_locks():
    if not os.path.exists(LOCK_FILE):
        return {}
    with open(LOCK_FILE, "r") as f:
        return json.load(f)

def save_locks(data):
    with open(LOCK_FILE, "w") as f:
        json.dump(data, f)

def check_and_cleanup(machine, lock):
    if lock["start_time"]:
        start_time = datetime.strptime(lock["start_time"], "%Y-%m-%d %H:%M:%S")
        timeout = int(lock.get("timeout", DEFAULT_TIMEOUT))
        elapsed = datetime.now() - start_time
        if elapsed > timedelta(minutes=timeout):
            return {"in_use": False, "user": None, "start_time": None, "timeout": timeout, "remaining": 0}
        else:
            remaining = max(0, int((timedelta(minutes=timeout) - elapsed).total_seconds()))
            lock["remaining"] = remaining
    else:
        lock["remaining"] = 0
    return lock

@app.route("/")
def index():
    locks = load_locks()
    updated_locks = {}
    for machine in MACHINES:
        lock = locks.get(machine, {"in_use": False, "user": None, "start_time": None, "timeout": DEFAULT_TIMEOUT})
        updated_locks[machine] = check_and_cleanup(machine, lock)
    save_locks(updated_locks)

    username = request.cookies.get("username")
    return render_template("index.html", locks=updated_locks, users=USERS, selected_user=username)

@app.route("/set_user", methods=["POST"])
def set_user():
    user = request.json.get("user")
    resp = make_response(jsonify({"message": "User set", "user": user}))
    resp.set_cookie("username", user)
    return resp

@app.route("/status")
def status():
    locks = load_locks()
    updated_locks = {}
    for machine in MACHINES:
        lock = locks.get(machine, {"in_use": False, "user": None, "start_time": None, "timeout": DEFAULT_TIMEOUT})
        updated_locks[machine] = check_and_cleanup(machine, lock)
    return jsonify(updated_locks)

@app.route("/take", methods=["POST"])
def take():
    data = request.json
    machine = data.get("machine")
    user = request.cookies.get("username")
    timeout = int(data.get("timeout", DEFAULT_TIMEOUT))

    if not user:
        return jsonify({"error": "User not set"}), 400

    locks = load_locks()
    lock = locks.get(machine, {"in_use": False, "user": None, "start_time": None, "timeout": timeout})

    lock = check_and_cleanup(machine, lock)
    if lock["in_use"]:
        return jsonify({"error": f"{machine} is already in use by {lock['user']}"}), 403

    new_lock = {
        "in_use": True,
        "user": user,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timeout": timeout,
        "remaining": timeout * 60
    }
    locks[machine] = new_lock
    save_locks(locks)
    return jsonify({"message": f"{machine} locked by {user} for {timeout} minutes", **new_lock})

@app.route("/release", methods=["POST"])
def release():
    data = request.json
    machine = data.get("machine")
    user = request.cookies.get("username")

    if not user:
        return jsonify({"error": "User not set"}), 400

    locks = load_locks()
    lock = locks.get(machine)
    if not lock:
        return jsonify({"error": "Machine not found."}), 404

    if not lock["in_use"]:
        return jsonify({"message": f"{machine} is already free"})

    if lock["user"] != user:
        return jsonify({"error": "Only the locker can release it."}), 403

    locks[machine] = {"in_use": False, "user": None, "start_time": None, "timeout": lock.get("timeout", DEFAULT_TIMEOUT), "remaining": 0}
    save_locks(locks)
    return jsonify({"message": f"{machine} released successfully"})

@app.route("/extend", methods=["POST"])
def extend():
    data = request.json
    machine = data.get("machine")
    extra_minutes = int(data.get("extra", DEFAULT_TIMEOUT))  # Use provided or default timeout
    user = request.cookies.get("username")

    if not user:
        return jsonify({"error": "User not set"}), 400

    locks = load_locks()
    lock = locks.get(machine)
    if not lock:
        return jsonify({"error": "Machine not found."}), 404

    if not lock["in_use"] or lock["user"] != user:
        return jsonify({"error": "Only the locker can extend the time."}), 403

    lock = check_and_cleanup(machine, lock)
    start_time = datetime.strptime(lock["start_time"], "%Y-%m-%d %H:%M:%S")
    timeout = lock["timeout"] + extra_minutes

    elapsed = datetime.now() - start_time
    remaining = max(0, int((timedelta(minutes=timeout) - elapsed).total_seconds()))

    lock["timeout"] = timeout
    lock["remaining"] = remaining
    locks[machine] = lock
    save_locks(locks)

    return jsonify({"message": f"Time extended by {extra_minutes} minutes", **lock})
