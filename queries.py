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
    return "INSERT INTO users (username, is_project_lead, requested_lead_status) VALUES (?, ?, ?)"

def set_project_lead():
    """Sets a user to be a project lead by their username"""
    return "UPDATE users SET is_project_lead = 1 WHERE username=?"

def request_project_lead():
    """Sends in a request to ask to be a project lead by username"""
    return "UPDATE users SET requested_lead_status = 1 WHERE username=?"

def unrequest_project_lead():
    """Removes request for project lead request by username"""
    return "UPDATE users SET requested_lead_status = 0 WHERE username=?"

def get_request_status():
    """Returns if a specificed user has request project lead status by username"""
    return "SELECT requested_lead_status from users WHERE username=?"

def get_all_project_lead_requests():
    """Returns all of the users that have requested to be a project lead"""
    return "SELECT username FROM users WHERE requested_lead_status = 1"

def add_statement():
    """Adds a statement into the statements table"""
    return "INSERT INTO statements (item_id, property_id, value_id, snaktype, username) VALUES (?, ?, ?, ?, ?)"

def add_statement_with_reference():
    """Adds a statement into the statements table that includes references"""
    return "INSERT INTO statements (item_id, property_id, value_id, snaktype, username, reference_type, reference_value) VALUES (?, ?, ?, ?, ?, ?, ?)"

def delete_statement():
    """Deletes a statement by statement id from the statements table"""
    return "DELETE FROM statements WHERE statement_id=?"

def get_statement():
    """Queries a statement by statement id from the statements table"""
    return """SELECT * from statements WHERE statement_id=?"""

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

def delete_qualifier():
    """Deletes a qualifier based on statement_id"""
    return "DELETE FROM qualifiers WHERE statement_id=?"

def get_qualifier_for_statement():
    """Queries the qualifier assocatied with a statement based on statement id"""
    return "SELECT * from qualifiers WHERE statement_id=?"

def get_all_annotated_objects():
    """Returns all of the item_id, username pair tuple for locally annotated objects"""
    return "SELECT statement_id, item_id, username from statements"

def get_comments():
    """Returns comment associated with an item_id, username tuple"""
    return "SELECT statement_id, comment, project_lead_username FROM comments WHERE item_id=? and username=?"

def add_comment():
    """Adds a comment to the comment database"""
    return "INSERT INTO comments (statement_id, comment, project_lead_username, item_id, username) VALUES (?, ?, ?, ?, ?)"

def delete_all_comments():
    """Deletes all comments with a certain item_id, username pair"""
    return "DELETE FROM comments WHERE item_id=? and username=?"