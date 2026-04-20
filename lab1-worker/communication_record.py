from datetime import datetime
from typing import Literal, TypedDict

from bson import ObjectId


class ToRelation(TypedDict):
    relationTo: str
    value: str | ObjectId


class TextNode(TypedDict):
    text: str


class BodyElement(TypedDict):
    children: list[TextNode]


class CommunicationRecord(TypedDict):
    _id: ObjectId
    subject: str
    status: Literal["pending", "processing", "sent", "failed"]
    sendToAll: bool | None
    createdAt: datetime
    updatedAt: datetime
    __v: int
