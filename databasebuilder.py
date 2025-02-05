from sys import stderr, exit
from sqlite3 import connect as sqlite_connect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Users, Statements, Qualifiers
from consts import *

if __name__ == "__main__":
    try:
        # set up session
        engine = create_engine('sqlite://', creator=lambda: sqlite_connect('file:' + FILENAME + '.sqlite?mode=rwc', uri=True))
        Session = sessionmaker(bind=engine)
        session = Session()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        engine.dispose()
    except Exception as ex:
        print(ex, file=stderr)
        exit(1)