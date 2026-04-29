from . import app
import os
import json
import pymongo
from flask import jsonify, request, make_response, abort, url_for  # noqa; F401
from pymongo import MongoClient
from bson import json_util
from pymongo.errors import OperationFailure
from pymongo.results import InsertOneResult
from bson.objectid import ObjectId
import sys

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
json_url = os.path.join(SITE_ROOT, "data", "songs.json")
songs_list: list = json.load(open(json_url))

# client = MongoClient(
#     f"mongodb://{app.config['MONGO_USERNAME']}:{app.config['MONGO_PASSWORD']}@localhost")
mongodb_service = os.environ.get('MONGODB_SERVICE')
mongodb_username = os.environ.get('MONGODB_USERNAME')
mongodb_password = os.environ.get('MONGODB_PASSWORD')
mongodb_port = os.environ.get('MONGODB_PORT')

print(f'The value of MONGODB_SERVICE is: {mongodb_service}')

if mongodb_service == None:
    app.logger.error('Missing MongoDB server in the MONGODB_SERVICE variable')
    # abort(500, 'Missing MongoDB server in the MONGODB_SERVICE variable')
    sys.exit(1)

if mongodb_username and mongodb_password:
    url = f"mongodb://{mongodb_username}:{mongodb_password}@{mongodb_service}"
else:
    url = f"mongodb://{mongodb_service}"


print(f"connecting to url: {url}")

try:
    client = MongoClient(url)
except OperationFailure as e:
    app.logger.error(f"Authentication error: {str(e)}")

db = client.songs
db.songs.drop()
db.songs.insert_many(songs_list)

def parse_json(data):
    return json.loads(json_util.dumps(data))

######################################################################
# INSERT CODE HERE
######################################################################

@app.route("/health", methods=["GET"])
def health():
    """
    Health check endpoint to verify the server is running.
    """
    return {"status": "OK"}, 200

@app.route("/song", methods=["GET"])
def songs():
    """
    Retrieves all songs from the MongoDB database and returns them as a JSON list.
    """
    # Call db.songs.find({}) to get all documents from the collection
    all_songs = db.songs.find({})
    
    # Use the provided parse_json helper to handle BSON serialization (like ObjectIds)
    decoded_songs = parse_json(all_songs)
    
    # Return the data as a dictionary with a list of songs and HTTP 200 OK
    return {"songs": decoded_songs}, 200

@app.route("/count", methods=["GET"])
def count_songs():
    """
    Returns the total number of songs in the collection.
    """
    # 1. Get the count of documents in the songs collection
    # The empty curly braces {} match all documents
    count = db.songs.count_documents({})
    
    # 2. Return the data as {"count": <number>} with HTTP 200 OK
    return {"count": count}, 200

@app.route("/song/<int:id>", methods=["GET"])
def get_song_by_id(id):
    """
    Finds a song by its custom 'id' field and returns it.
    """
    # 1. Search the database for the song with the specific id
    song = db.songs.find_one({"id": id})
    
    # 2. If the song is not found, return 404 with the error message
    if not song:
        return {"message": f"song with id {id} not found"}, 404
    
    # 3. If found, parse into JSON and return with 200 OK
    return parse_json(song), 200

@app.route("/song", methods=["POST"])
def create_song():
    """
    Creates a new song record if the ID does not already exist.
    """
    # 1. Extract the song data from the request body
    new_song = request.get_json()
    
    # 2. Check if the song with the given 'id' already exists in the database
    existing_song = db.songs.find_one({"id": new_song["id"]})
    
    if existing_song:
        # If found, return HTTP 302 with the specific message
        return {"Message": f"song with id {new_song['id']} already present"}, 302

    # 3. If it doesn't exist, insert the new song into the database
    insert_result = db.songs.insert_one(new_song)
    
    # 4. Return the new song data (with the new MongoDB _id) and 201 Created
    # We use parse_json to handle the BSON ObjectId from the insertion result
    return parse_json(insert_result.inserted_id), 201

@app.route("/song/<int:id>", methods=["PUT"])
def update_song(id):
    """
    Updates an existing song's details based on the provided ID.
    """
    # 1. Extract the updated song data from the request body
    song_data = request.get_json()

    # 2. Find the song in the database
    song = db.songs.find_one({"id": id})

    # 3. If the song does not exist, return 404
    if song is None:
        return {"message": "song not found"}, 404

    # 4. Update the song with the incoming request data
    # Use "$set" to update only the fields provided in the request body
    result = db.songs.update_one({"id": id}, {"$set": song_data})

    # 5. If the update was successful but nothing changed (e.g., same data sent)
    # or if it was modified, return the message and 201 per common project requirements
    if result.modified_count == 0:
        return {"message": "song found, but nothing updated"}, 200

    return parse_json(db.songs.find_one({"id": id})), 201

@app.route("/song/<int:id>", methods=["DELETE"])
def delete_song(id):
    """
    Deletes a song from the database based on the provided ID.
    """
    # 1. Attempt to delete the document with the matching custom 'id'
    delete_result = db.songs.delete_one({"id": id})

    # 2. Check if a document was actually deleted
    if delete_result.deleted_count == 0:
        # If no document matched the ID, return 404
        return {"message": "song not found"}, 404

    # 3. If deleted_count is 1, return an empty body with 204 No Content
    # Using an empty string or None with 204 is standard practice
    return "", 204