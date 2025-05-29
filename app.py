from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_migrate import Migrate
from models import db, Contact, ContactList
from forms import ContactForm, ContactListForm

import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///contacts.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

@app.route('/')
def index():
    contacts = Contact.query.all()
    return render_template('home.html', contacts=contacts)

@app.route('/add', methods=['GET', 'POST'])
def add_contact():
    form = ContactForm()
    if form.validate_on_submit():
        new_contact = Contact(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
        )
        db.session.add(new_contact)
        try:
            db.session.commit()
            flash('Contact added successfully!', 'success')
        except Exception:
            db.session.rollback()
            flash('Error: Could not add contact (maybe duplicate email).', 'danger')
        return redirect(url_for('index'))
    return render_template('add_contact.html', form=form)

@app.route('/edit/<int:contact_id>', methods=['GET', 'POST'])
def edit_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    form = ContactForm(obj=contact)
    if form.validate_on_submit():
        contact.first_name = form.first_name.data
        contact.last_name = form.last_name.data
        contact.email = form.email.data
        try:
            db.session.commit()
            flash('Contact updated!', 'success')
        except Exception:
            db.session.rollback()
            flash('Error: Could not update contact.', 'danger')
        return redirect(url_for('index'))
    return render_template('edit_contact.html', form=form, contact=contact)

@app.route('/delete/<int:contact_id>', methods=['POST'])
def delete_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    flash('Contact deleted.', 'info')
    return redirect(url_for('index'))

@app.route('/list_contacts')
def list_contacts():
    contacts = Contact.query.order_by(Contact.last_name.asc()).all()
    return render_template('contact_list.html', contacts=contacts)

@app.route('/search_contacts')
def search_contacts():
    q = request.args.get('q', '', type=str)
    if len(q) < 3:
        return jsonify([])
    matches = Contact.query.filter(
        (Contact.first_name.ilike(f'%{q}%')) |
        (Contact.last_name.ilike(f'%{q}%')) |
        (Contact.email.ilike(f'%{q}%'))
    ).all()
    return jsonify([
        {"id": c.id, "first_name": c.first_name, "last_name": c.last_name, "email": c.email}
        for c in matches
    ])


@app.route('/lists', methods=['GET'])
def lists():
    lists = ContactList.query.order_by(ContactList.name.asc()).all()
    return render_template('lists.html', lists=lists)

@app.route('/lists/new', methods=['GET', 'POST'])
def add_list():
    form = ContactListForm()
    if form.validate_on_submit():
        new_list = ContactList(
            name=form.name.data,
            description=form.description.data,
            owner=form.owner.data
        )
        db.session.add(new_list)
        db.session.commit()
        flash('Contact list created!', 'success')
        return redirect(url_for('lists'))
    return render_template('add_list.html', form=form)


@app.route('/search_lists')
def search_lists():
    q = request.args.get('q', '', type=str)
    if len(q) < 3:
        return jsonify([])
    # Performs a case-insensitive LIKE search by list name
    results = ContactList.query.filter(
        ContactList.name.ilike(f"%{q}%")
    ).order_by(ContactList.name.asc()).all()
    return jsonify([
        {
            "id": l.id,
            "name": l.name,
            "owner": l.owner,
            "description": l.description
        }
        for l in results
    ])

@app.route('/lists/edit/<int:list_id>', methods=['GET', 'POST'])
def edit_list(list_id):
    list_obj = ContactList.query.get_or_404(list_id)
    form = ContactListForm(obj=list_obj)
    if form.validate_on_submit():
        list_obj.name = form.name.data
        list_obj.description = form.description.data
        list_obj.owner = form.owner.data
        try:
            db.session.commit()
            flash('Contact list updated!', 'success')
        except Exception:
            db.session.rollback()
            flash('Error: Could not update list.', 'danger')
        return redirect(url_for('lists'))
    return render_template('edit_list.html', form=form, list_obj=list_obj)


@app.route('/lists/delete/<int:list_id>', methods=['POST'])
def delete_list(list_id):
    list_obj = ContactList.query.get_or_404(list_id)
    db.session.delete(list_obj)
    try:
        db.session.commit()
        flash('Contact list deleted.', 'info')
    except Exception:
        db.session.rollback()
        flash('Error: Could not delete list.', 'danger')
    return redirect(url_for('lists'))

@app.route('/lists/<int:list_id>/add_contacts', methods=['POST'])
def add_contacts_to_list(list_id):
    list_obj = ContactList.query.get_or_404(list_id)
    data = request.get_json()
    contact_ids = data.get('contact_ids', [])
    if not contact_ids:
        return jsonify(success=False, message="No contacts selected"), 400

    contacts_to_add = Contact.query.filter(Contact.id.in_(contact_ids)).all()
    # Prevent duplicates
    for contact in contacts_to_add:
        if contact not in list_obj.contacts:
            list_obj.contacts.append(contact)
    try:
        db.session.commit()
        return jsonify(success=True, message=f"Added {len(contacts_to_add)} contact(s) to the list.")
    except Exception:
        db.session.rollback()
        return jsonify(success=False, message="Could not add contacts."), 500



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)