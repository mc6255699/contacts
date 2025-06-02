from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_migrate import Migrate
from models import db, Contact, ContactList
from forms import ContactForm, ContactListForm
from werkzeug.utils import secure_filename
import csv
import io
from models import Contact
from sqlalchemy import or_
from config import Config


import os
app = Flask(__name__)
app.config.from_object(Config)

#app.config['SECRET_KEY'] = os.urandom(24)
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///contacts.db'
#app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

@app.route('/')
def index():
    contacts = Contact.query.all()
    return render_template('home.html', contacts=contacts)


@app.route('/contacts')
def contacts():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str).strip()
    per_page = 10

    query = db.session.query(Contact)
    if search:
        search_pattern = f"%{search}%"
        # Search by first name, last name, or email (case-insensitive)
        query = query.filter(
            or_(
                Contact.first_name.ilike(search_pattern),
                Contact.last_name.ilike(search_pattern),
                Contact.email.ilike(search_pattern)
            )
        )

    contacts_pagination = query.order_by(Contact.last_name, Contact.first_name).paginate(page=page, per_page=per_page)
    return render_template(
        'contact_list.html',
        contacts=contacts_pagination.items,
        pagination=contacts_pagination
    )


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
        return redirect(url_for('list_contacts'))  # Redirect to the contact list page
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

@app.route('/contacts')
def list_contacts():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = Contact.query.order_by(Contact.last_name, Contact.first_name).paginate(page=page, per_page=per_page, error_out=False)
    contacts = pagination.items
    total_pages = pagination.pages

    return render_template(
        'contact_list.html',
        contacts=contacts,
        page=page,
        total_pages=total_pages
    )

@app.route('/contact/<int:contact_id>/lists')
def get_contact_lists(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    lists = [{'id': cl.id, 'name': cl.name, 'owner': cl.owner} for cl in contact.contact_lists]
    return jsonify(lists)

@app.route('/lists/search')
def ajax_search_lists():
    query = request.args.get('q', '').strip()
    exclude_ids = request.args.get('exclude_ids', '')
    if not query or len(query) < 3:
        return jsonify([])
    exclude_ids = [int(i) for i in exclude_ids.split(',') if i.strip().isdigit()]
    # Assuming List is your SQLAlchemy model for lists
    lists = ContactList.query.filter(ContactList.name.ilike(f"%{query}%"))
    if exclude_ids:
        lists = lists.filter(~ContactList.id.in_(exclude_ids))
    data = [{'id': l.id, 'name': l.name, 'owner': l.owner} for l in lists.limit(10)]
    return jsonify(data)

@app.route('/lists/add_contact', methods=['POST'])
def ajax_add_contact_to_list():
    data = request.get_json()
    contact_id = data['contact_id']
    list_id = data['list_id']
    contact = Contact.query.get(contact_id)
    lst = ContactList.query.get(list_id)
    if not contact or not lst:
        return jsonify({'success': False, 'message': 'Contact or List not found'})
    if contact not in lst.contacts:
        lst.contacts.append(contact)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/lists/remove_contact', methods=['POST'])
def ajax_remove_contact_from_list():
    data = request.get_json()
    contact_id = data['contact_id']
    list_id = data['list_id']
    contact = Contact.query.get(contact_id)
    lst = ContactList.query.get(list_id)
    if not contact or not lst:
        return jsonify({'success': False, 'message': 'Contact or List not found'})
    if contact in lst.contacts:
        lst.contacts.remove(contact)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/search_contacts')
def search_contacts():
    q = request.args.get('q', '').strip()
    exclude_ids_str = request.args.get('exclude_ids', '')
    exclude_ids = [int(i) for i in exclude_ids_str.split(',') if i.isdigit()]

    # If there's no query or query is too short, return empty list
    if len(q) < 3:
        return jsonify([])

    # Perform search (filter for name or email matches, and not in exclude_ids)
    contacts = Contact.query.filter(
        (Contact.first_name.ilike(f'%{q}%')) |
        (Contact.last_name.ilike(f'%{q}%')) |
        (Contact.email.ilike(f'%{q}%'))
    ).filter(~Contact.id.in_(exclude_ids)).all()

    contacts_data = [
        {
            'id': contact.id,
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'email': contact.email,
        }
        for contact in contacts
    ]
    return jsonify(contacts_data)

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

# @app.route('/lists/<int:list_id>/add_contacts', methods=['POST'])
# def add_contacts_to_list(list_id):
#     list_obj = ContactList.query.get_or_404(list_id)
#     data = request.get_json()
#     contact_ids = data.get('contact_ids', [])
#     if not contact_ids:
#         return jsonify(success=False, message="No contacts selected"), 400
#
#     contacts_to_add = Contact.query.filter(Contact.id.in_(contact_ids)).all()
#     # Prevent duplicates
#     for contact in contacts_to_add:
#         if contact not in list_obj.contacts:
#             list_obj.contacts.append(contact)
#     try:
#         db.session.commit()
#         return jsonify(success=True, message=f"Added {len(contacts_to_add)} contact(s) to the list.")
#     except Exception:
#         db.session.rollback()
#         return jsonify(success=False, message="Could not add contacts."), 500


@app.route('/lists/<int:list_id>/add_contacts', methods=['POST'])
def add_contacts_to_list(list_id):
    list_obj = ContactList.query.get_or_404(list_id)
    data = request.get_json()
    contact_ids = data.get('contact_ids', [])
    if not contact_ids:
        return jsonify(success=False, message="No contacts selected"), 400

    # We’ll only add contacts that aren’t already members
    new_contacts = []
    for contact in Contact.query.filter(Contact.id.in_(contact_ids)):
        if contact not in list_obj.contacts:
            list_obj.contacts.append(contact)
            new_contacts.append(contact)

    try:
        db.session.commit()
        # Return info for only the first new contact (since "+" adds one at a time)
        if new_contacts:
            c = new_contacts[0]
            return jsonify(
                success=True,
                message="Contact added.",
                new_contact={
                    "id": c.id,
                    "first_name": c.first_name,
                    "last_name": c.last_name,
                    "email": c.email
                }
            )
        else:
            # Already a member
            return jsonify(success=True, message="Contact already in the list.", new_contact=None)
    except Exception:
        db.session.rollback()
        return jsonify(success=False, message="Could not add contacts."), 500


@app.route('/lists/<int:list_id>/remove_contact/<int:contact_id>', methods=['POST'])
def remove_contact_from_list(list_id, contact_id):
    list_obj = ContactList.query.get_or_404(list_id)
    contact = Contact.query.get_or_404(contact_id)
    if contact in list_obj.contacts:
        list_obj.contacts.remove(contact)
        try:
            db.session.commit()
            return jsonify(success=True, message="Contact removed.")
        except Exception:
            db.session.rollback()
            return jsonify(success=False, message="Could not remove contact."), 500
    return jsonify(success=False, message="Contact not in list."), 400



@app.route('/contacts/upload', methods=['GET', 'POST'])
def upload_contacts():
    rejected_rows = []
    processed_count = 0

    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or not file.filename.lower().endswith('.csv'):
            flash("Please upload a CSV file.", "danger")
            return render_template('upload_contacts.html', rejected_rows=[])

        # Read the uploaded file as text
        stream = io.StringIO(file.stream.read().decode("utf-8"))
        reader = csv.reader(stream)
        header = next(reader, None)
        expected_header = ["First Name", "Last Name", "Email"]

        # Check header
        if [h.strip() for h in header] != expected_header:
            flash("CSV must have columns: First Name, Last Name, Email", "danger")
            return render_template('upload_contacts.html', rejected_rows=[])

        # Fetch all existing emails for quick lookup
        from models import Contact  # adjust import as needed
        existing_emails = {c.email.lower() for c in Contact.query.all()}

        for idx, row in enumerate(reader, start=2):  # start=2: header is row 1
            # Verify column count and row content
            if len(row) != 3 or any(cell.strip() == '' for cell in row):
                rejected_rows.append({'rownum': idx, 'reason': 'Invalid columns or missing field', 'data': row})
                continue

            first_name, last_name, email = row
            email = email.strip()
            if email.lower() in existing_emails:
                rejected_rows.append({'rownum': idx, 'reason': 'Duplicate email', 'data': row})
                continue

            if not first_name.strip() or not last_name.strip() or not email:
                rejected_rows.append({'rownum': idx, 'reason': 'One or more fields empty', 'data': row})
                continue

            # Create & add contact
            new_contact = Contact(
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                email=email
            )
            db.session.add(new_contact)
            existing_emails.add(email.lower())
            processed_count += 1

        db.session.commit()
        flash(f"Imported {processed_count} contacts.", "success")

    else:
        rejected_rows = []

    return render_template('upload_contacts.html', rejected_rows=rejected_rows)



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)