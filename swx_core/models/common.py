"""
Common Schemas
--------------
This module contains common response schemas used across the API.
"""

from sqlmodel import SQLModel


class Message(SQLModel):
    """
    Generic message response schema.

    Attributes:
        message (str): The message to return in the response.
    """

    message: str
