# holds all queries and functions that help with queries for the sqlite table
import sqlite3
from contextlib import closing
from consts import *

# utility functions
def jsonify_rows(rows):
    """jsonifies output from sqlite table"""
    return [] if not rows else [dict(result) for result in rows]

def query_db(query, params=None, database_url=DATABASE_URL):
    """Queries the sqlite database with specified query and parameters"""
    results = []
    with sqlite3.connect(database_url, isolation_level=None, uri=True) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.row_factory = sqlite3.Row
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
    return results

# sqlite queries
def is_project_lead():
    """Returns true or false (1 or 0) for if the given username is a project lead"""
    return "SELECT is_project_lead FROM users WHERE username = ?"

def add_user():
    """Adds a user into the users table as a contributor by default"""
    return "INSERT INTO users (username, is_project_lead) VALUES (?, ?)"

def add_statement():
    """Adds a statement into the statements table"""
    return "INSERT INTO statements (item_id, property_id, value_id, snaktype, username) VALUES (?, ?, ?, ?, ?)"

def get_latest_statement():
    """Gets the last row in the statements table (usually the one you just inserted)"""
    return "SELECT statement_id FROM statements ORDER BY rowid DESC LIMIT 1"

def get_object_statements():
    """Selects all locally saved statements for an object based on what user is logged in"""
    return "SELECT * FROM statements WHERE item_id=? and username=?"

def add_qualifier():
    """Adds a qualifier (associated with some statement) into the qualifiers table with qualifier hash"""
    return '''INSERT INTO qualifiers (statement_id, iiif_region, qualifier_hash) VALUES (?, ?, ?)
              ON CONFLICT(statement_id) DO UPDATE
              SET iiif_region = EXCLUDED.iiif_region,
                  qualifier_hash = EXCLUDED.qualifier_hash;'''

def get_qualifier_for_statement():
    """Queries the qualifier assocatied with a statement based on statement id"""
    return "SELECT * from qualifiers WHERE statement_id=?"