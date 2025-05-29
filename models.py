from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Association table for many-to-many relationship
contact_list_membership = db.Table(
    'contact_list_membership',
    db.Column('contact_id', db.Integer, db.ForeignKey('contact.id'), primary_key=True),
    db.Column('contact_list_id', db.Integer, db.ForeignKey('contact_list.id'), primary_key=True)
)

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)


class ContactList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    owner = db.Column(db.String(120), nullable=False)
    contacts = db.relationship(
        'Contact',
        secondary=contact_list_membership,
        backref=db.backref('contact_lists', lazy='dynamic')
    )
