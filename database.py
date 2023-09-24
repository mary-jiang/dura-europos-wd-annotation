from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship

Base = declarative_base()

class Users(Base):
    """This table will hold information for users and their permissions (contributor vs project lead), keyed by Wikimedia username"""
    __tablename__ = 'users'

    username = Column(String, primary_key=True)
    isProjectLead = Column(Boolean, default=False)
