# python
import secrets
import sqlite3
from .db import get_db
from .models import Member
from .config import COUNCIL_TITLE
from sqlalchemy.orm import Session
from fastapi import Depends

class AccessCode:
    def __init__(self, db: Session = Depends(get_db)):
        self.ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
        self.db = db

    def generate_unique_access_code(self, length: int = 6, max_attempts: int = 10000) -> str:
        """
        Generate a random `length`-char code from ALPHABET that does not exist
        in `members.access_code`. Raises RuntimeError if uniqueness cannot be found.
        """
        for _ in range(max_attempts):
            code = ''.join(secrets.choice(self.ALPHABET) for _ in range(length))
            member = (
                self.db.query(Member)
                .filter(Member.access_code.ilike(code.strip()))
                .first()
            )
            if member is None:
                return code

        raise RuntimeError(f"Failed to generate unique access_code after {max_attempts} attempts")

    def assign_access_code(self, member_id: int) -> str:
        """
        Generate a unique access code and set it on the member with `id = member_id`.
        Returns the new code.
        """
        code = self.generate_unique_access_code()
        self.db.member = (
            self.db.query(Member)
            .filter(Member.id == member_id)
            .first()
        )
        if self.db.member is None:
            raise ValueError(f"No member with id {member_id}")
        self.db.member.access_code = code
        self.db.commit()
        return code


# Example usage:
# conn = sqlite3.connect("data.sqlite3")
# new_code = assign_access_code(conn, 123)
# print("Assigned access_code:", new_code)
