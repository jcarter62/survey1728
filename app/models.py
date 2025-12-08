from sqlalchemy import Column, Integer, String, Float, Text, Date, DateTime, ForeignKey, Boolean, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True, index=True)
    member_number = Column(String, nullable=False)
    first_name = Column(String)
    last_name = Column(String, index=True)
    mobile_phone = Column(String)
    email = Column(String)
    is_admin = Column(Boolean, nullable=False, default=False)
    access_code = Column(String, nullable=True)

    activities = relationship("Activity", back_populates="member")
    submissions = relationship(
        "Submission",
        back_populates="member",
        foreign_keys="Submission.member_id",
        cascade="all, delete-orphan",
    )
    reviewed_submissions = relationship(
        "Submission",
        back_populates="reviewer",
        foreign_keys="Submission.reviewer_id",
    )

class EmailLog(Base):
    __tablename__ = "email_log"
    id = Column(Integer, primary_key=True, index=True)
    member_number = Column(String, nullable=False)
    to_address = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.now())

class Activity(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    category = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    hours = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("hours >= 0", name="hours_non_negative"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
    )

    member = relationship("Member", back_populates="activities")

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    total_hours = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="submitted")
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    reviewer_id = Column(Integer, ForeignKey("members.id"), nullable=True)

    member = relationship("Member", foreign_keys=[member_id], back_populates="submissions")
    reviewer = relationship("Member", foreign_keys=[reviewer_id], back_populates="reviewed_submissions")

class AdminFlag(Base):
    __tablename__ = "admin_flags"
    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    flag_type = Column(String, nullable=False)
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolver_id = Column(Integer, ForeignKey("members.id"), nullable=True)
