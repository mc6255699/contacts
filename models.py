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
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone_number = db.Column(db.String(20), unique=False, nullable=True)
    job_title = db.Column(db.String(50), unique=False, nullable=True)
    organization = db.Column(db.String(50), unique=False, nullable=True)
    notes = db.Column(db.Text)
    # contact_lists = db.relationship(
    #     'ContactList',
    # )
    def __repr__(self):
        return f"<Contact {self.first_name} {self.last_name} ({self.email})>"

class ContactList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    # owner = db.Column(db.String(120), nullable=False)
    owner_id = db.Column(db.String(64), db.ForeignKey('user.id'), nullable=True)
    owner = db.relationship('User', back_populates='contact_lists')

    contacts = db.relationship(
        'Contact',
        secondary=contact_list_membership,
        backref=db.backref('contact_lists', lazy='dynamic')
    )


class User(db.Model):
    id = db.Column(db.String(64), primary_key=True)  # Azure AD OID
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # relationships -- example for later
    contact_lists = db.relationship('ContactList', back_populates='owner')

