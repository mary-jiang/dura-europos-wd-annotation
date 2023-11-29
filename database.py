from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Boolean, Integer
from sqlalchemy.orm import relationship

Base = declarative_base()

class Users(Base):
    """This table will hold information for users and their permissions (contributor vs project lead), keyed by Wikimedia username"""
    __tablename__ = 'users'

    username = Column(String, primary_key=True)
    is_project_lead = Column(Boolean, default=False)
    requested_lead_status = Column(Boolean, default=False)

class Statements(Base):
    """This table will hold information for locally stored statements about wikidata objects"""
    __tablename__ = 'statements'

    statement_id = Column(Integer, primary_key=True, autoincrement=True)
    # wikidata statement: item property value
    item_id = Column(String) 
    property_id = Column(String) 
    value_id = Column(String)

    snaktype = Column(String)
    username = Column(String) # username of the person making this

    reference_type = Column(String, nullable=True)
    reference_value = Column(String, nullable=True)

    pages_value = Column(String, nullable=True)

class Qualifiers(Base):
    """This table holds information about the qualifiers (associates statement with the annotated region)"""
    __tablename__ = 'qualifiers'

    statement_id = Column(String, primary_key=True)
    iiif_region = Column(String)
    qualifier_hash = Column(String, nullable=True)

class Comments(Base):
    """This table holds information about the comments that project leads leave on specific statements."""
    __tablename__ = 'comments'

    comment_id = Column(Integer, primary_key=True, autoincrement=True)
    statement_id = Column(String)
    comment = Column(String)
    project_lead_username = Column(String)
    item_id = Column(String)
    username = Column(String)

class Approvals(Base):
    """This table holds information about what item_id and username pairs are approved"""
    __tablename__ = 'approvals'

    approval_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String)
    item_id = Column(String)
    approved = Column(Boolean)