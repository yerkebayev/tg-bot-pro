# models.py
from typing import List

class Message:
    def __init__(self, ID: int, message_id: str, language: str, address_id: str,
                 from_phone: str, to_phone: str, msgGoodOrBad: str,
                 msg_type: str, text: str, file_id: str = "",
                 answer_for_message_id: str = "", date_time: str = ""):
        self.ID = ID
        self.message_id = message_id
        self.language = language
        self.address_id = address_id
        self.from_phone = from_phone
        self.to_phone = to_phone
        self.msgGoodOrBad = msgGoodOrBad
        self.type = msg_type
        self.text = text
        self.file_id = file_id
        self.answer_for_message_id = answer_for_message_id
        self.date_time = date_time

class Conversation:
    def __init__(self, client_phone: str, messages: List[Message]):
        self.client_phone = client_phone
        self.messages = messages
