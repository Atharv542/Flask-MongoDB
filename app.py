from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime
from urllib.parse import quote_plus
import os

app = Flask(__name__)

def build_mongo_uri():
    # 1. Full URI override (useful for local testing)
    if os.environ.get("MONGODB_URI"):
        return os.environ["MONGODB_URI"]
    host = os.environ.get("MONGODB_HOST", "localhost")
    port = os.environ.get("MONGODB_PORT", "27017")
    user = os.environ.get("MONGODB_USERNAME")
    pwd = os.environ.get("MONGODB_PASSWORD")
    # 2. Authenticated connection (Kubernetes)
    if user and pwd:
        return f"mongodb://{quote_plus(user)}:{quote_plus(pwd)}@{host}:{port}/?authSource=admin"
    # 3. Unauthenticated (local dev)
    return f"mongodb://{host}:{port}/"

client = MongoClient(build_mongo_uri())
db = client.flask_db
collection = db.data

@app.route('/')
def index():
    return f"Welcome to the Flask app! The current time is: {datetime.now()}"

@app.route('/data', methods=['GET', 'POST'])
def data():
    if request.method == 'POST':
        data = request.get_json()
        collection.insert_one(data)
        return jsonify({"status": "Data inserted"}), 201
    elif request.method == 'GET':
        data = list(collection.find({}, {"_id": 0}))
        return jsonify(data), 200
    if __name__ == ' __main__ ':
        app.run(host='0.0.0.0', port=5000)