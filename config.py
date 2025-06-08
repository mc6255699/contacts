import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))





class Config:
    # Get secret key from environment variable with a fallback for development
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # Use DATABASE_URL if set (Render sets this), otherwise fallback to SQLite (for local dev)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(BASE_DIR, 'instance/contacts.db')
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Block SQLite in production for safety
    if "sqlite" in SQLALCHEMY_DATABASE_URI and os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("SQLite should not be used in production!")