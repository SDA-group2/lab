import os
from time import sleep

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from communication_record import CommunicationRecord


def connect_to_db() -> MongoClient[CommunicationRecord] | None:
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise ValueError('error: "MONGODB_URI" has not been defined.')

    try:
        client: MongoClient[CommunicationRecord] = MongoClient(uri)
        return client
    except ConnectionFailure as e:
        print(f"error: couldn't connect to db. ({e})")
        return None


if __name__ == "__main__":
    _ = load_dotenv()
    seconds = os.getenv("POLL_INTERVAL_SECONDS")
    POLL_INTERVAL_SECONDS = int(seconds) if seconds is not None else 3

    client = connect_to_db()
    if not client:
        exit(1)

    db = client.get_database("mzinga")
    collection = db.get_collection("communications")
    print(f"Opened {db.name} > {collection.name}.")

    query = {"status": "pending"}
    pending_communications = collection.find(query)
    nof_pending_communications = collection.count_documents(query)
    print(f"Found {nof_pending_communications} pending communications.")

    while nof_pending_communications <= 0:
        print(
            f"No pending communications are available, retrying in {POLL_INTERVAL_SECONDS} seconds."
        )
        sleep(POLL_INTERVAL_SECONDS)
