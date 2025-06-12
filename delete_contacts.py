#from app import app
from models import db, Contact

with app.app_context():
    num_deleted = Contact.query.delete()
    db.session.commit()
    print(f"Deleted {num_deleted} contacts.")