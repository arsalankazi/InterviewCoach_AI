import sqlite3
from flask import current_app, g


def get_db():
    """
    Establish and return a SQLite database connection for the current application context.
    The connection is cached in Flask's `g` object for the lifetime of the request.
    """
    if 'db' not in g:
        db_path = current_app.config['DATABASE_PATH']
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        # Enable row access by column name
        g.db.row_factory = sqlite3.Row
        # Enable foreign key constraint support in SQLite
        g.db.execute("PRAGMA foreign_keys = ON;")

    return g.db


def close_db(e=None):
    """
    Close the database connection at the end of the request context.
    Registered as a teardown handler.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_app(app):
    """
    Register database connection hooks with the Flask application instance.
    """
    app.teardown_appcontext(close_db)
