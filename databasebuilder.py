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

        # hardcode test usernames for testing of users database
        session.add(Users(username="testlead", isProjectLead=True))
        session.add(Users(username="testcontributor", isProjectLead=False))
        session.commit()

        # hardcode test items for testing of statements database
        session.add(Statements(item_id="itemid", property_id="propertyid", value_id="valueid", snaktype="snaktype", username="testcontributor"))
        session.commit()

        # hardcode test items for testting of qualifiers database
        session.add(Qualifiers(statement_id="statementid", iiff_region="iiffregion", qualifier_hash="qualifierhash"))
        session.commit()

        # clean up session
        session.close()
        engine.dispose()
    except Exception as ex:
        print(ex, file=stderr)
        exit(1)