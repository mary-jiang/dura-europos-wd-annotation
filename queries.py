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
    return "SELECT isprojectlead FROM users WHERE username = ?"

def add_user():
    """Adds a user into the users table as a contributor by default"""
    return "INSERT INTO users (username, isprojectlead) VALUES (?, ?)"
