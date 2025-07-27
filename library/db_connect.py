import sqlalchemy
from sqlalchemy.orm import sessionmaker
from typing import Generator
from contextlib import contextmanager
from src.common import get_config


def get_connector(schema="mysql_local"):
    """ database connection creds """

    config = get_config(schema)

    connect_url = sqlalchemy.engine.URL.create(drivername='mysql+pymysql',
                                               username=config["userName"],
                                               password=config["password"],
                                               host=config["host"],
                                               port=config["port"],
                                               database=config["schema"])
    return connect_url


engine = sqlalchemy.create_engine(get_connector(), pool_size=15,
                                  max_overflow=20,
                                  pool_recycle=300,
                                  pool_pre_ping=True,
                                  pool_use_lifo=True)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def session_scope() -> Generator:
    """ Provide a transactional scope around a series of operations. """

    session = None
    try:
        session = Session()
        yield session
    finally:
        session.close()


def receive_query(query):
    """ result dict formatter """
    return [row._asdict() for row in query]