from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_migrate import Migrate
from models import db, Contact, ContactList, User
from forms import ContactForm, ContactListForm
from werkzeug.utils import secure_filename
import csv
import io
from io import TextIOWrapper
from models import Contact
from sqlalchemy import or_
from config import Config
from sqlalchemy import asc, desc
from dotenv import load_dotenv
from flask import session
import os
import uuid
import msal
from auth import _build_msal_app, _build_auth_url
from auth import get_token_from_code
from flask_session import Session
import pprint
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # It's fine if dotenv isn't installed on production

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AUTHORITY = os.getenv("AUTHORITY")
REDIRECT_PATH = os.getenv("REDIRECT_PATH")
SCOPE = os.getenv("SCOPE").split(',')
SESSION_TYPE = os.getenv("SESSION_TYPE", "filesystem")


import os


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

app.config["SESSION_TYPE"] = "filesystem"

Session(app)



@app.route("/debug_session")
def debug_session():
    pretty_session = pprint.pformat(dict(session))
    return f"<pre>{pretty_session}</pre>"

@app.route("/debug_users")
def debug_users():
    users = User.query.all()
    users_list = [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
        for user in users
    ]
    pretty = pprint.pformat(users_list, indent=2)
    return f"<pre>{pretty}</pre>"



@app.route('/')
def index():
    contacts = Contact.query.all()
    return render_template('home.html', contacts=contacts)


@app.route("/login")
def login_microsoft():
    session["state"] = str(uuid.uuid4())

    msal_app = _build_msal_app(CLIENT_ID, AUTHORITY, CLIENT_SECRET)
    auth_url = _build_auth_url(
        msal_app,
        url_for("auth_callback", _external=True),
        scopes=SCOPE,
        state=session["state"]  # ✅ pass the state to Azure
    )

    return redirect(auth_url)

@app.route('/logout')
def logout():
    session.clear()  # or session.pop('user', None) for more granular
    return redirect(url_for('login_microsoft'))  # or your login route



@app.route("/getAToken")
def auth_callback():
    returned_state = request.args.get("state")
    original_state = session.pop("state", None)

    print("Returned state:", returned_state)
    print("Original session state:", original_state)

    if returned_state != original_state:
        flash("Invalid session state. Try logging in again.", "danger")
        session.clear()
        return redirect(url_for("index"))

    code = request.args.get('code')
    msal_app = _build_msal_app(CLIENT_ID, AUTHORITY, CLIENT_SECRET)

    result = get_token_from_code(
        msal_app,
        code,
        SCOPE,
        url_for("auth_callback", _external=True)
    )

    if "id_token_claims" in result:
        # Store Azure claims in session
        session["user"] = result["id_token_claims"]

        # ----- Store or update user in local database -----
        from models import db, User

        claims = result["id_token_claims"]
        oid = claims.get("oid")
        name = claims.get("name")
        email = claims.get("preferred_username") or claims.get("email")

        user = User.query.filter_by(id=oid).first()
        if user:
            # Optionally update if profile info has changed
            user.name = name
            user.email = email
        else:
            user = User(id=oid, name=name, email=email)
            db.session.add(user)
        db.session.commit()
        # Optionally store local user ID in the session
        session["user_id"] = user.id

        flash("You are now logged in!", "success")
        return redirect(url_for("index"))
    else:
        flash("Authentication failed. Please try again.", "danger")
        return redirect(url_for("login"))


@app.route('/contacts')
def list_contacts():
    sort = request.args.get('sort', 'last_name')
    direction = request.args.get('direction', 'asc')
    search = request.args.get('search', '').strip()

    # Columns allowed for sorting
    sort_options = {
        "first_name": Contact.first_name,
        "last_name": Contact.last_name,
        "organization": Contact.organization
    }
    sort_column = sort_options.get(sort, Contact.last_name)
    order_by = desc(sort_column) if direction == 'desc' else asc(sort_column)

    # Begin query
    contacts_query = Contact.query

    # Filtering for search
    if search and len(search) >= 3:
        search_pattern = f"%{search}%"
        contacts_query = contacts_query.filter(
            or_(
                Contact.first_name.ilike(search_pattern),
                Contact.last_name.ilike(search_pattern),
                Contact.organization.ilike(search_pattern)
            )
        )

    # Sorting and pagination
    contacts_query = contacts_query.order_by(order_by)
    page = request.args.get('page', 1, type=int)
    pagination = contacts_query.paginate(page=page, per_page=25, error_out=False)
    contacts = pagination.items

    # Render
    return render_template(
        'list_contacts.html',
        contacts=contacts,
        pagination=pagination,
        sort=sort,
        direction=direction,
        search=search
    )
#

@app.route('/add_contact', methods=['GET', 'POST'])
def add_contact():
    form = ContactForm()
    if form.validate_on_submit():
        new_contact = Contact(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone_number=form.phone_number.data,
            job_title=form.job_title.data,
            organization=form.organization.data,
            notes=form.notes.data
        )
        db.session.add(new_contact)
        try:
            db.session.commit()
            flash('Contact added successfully!', 'success')
            return redirect(url_for('contacts'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding contact: {e}', 'danger')
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
    results = {"contacts": [], "lists": []}
    if len(q) >= 3:
        pattern = f"%{q}%"
        # Search contacts
        contacts = Contact.query.filter(
            or_(
                Contact.first_name.ilike(pattern),
                Contact.last_name.ilike(pattern),
                Contact.email.ilike(pattern),
                Contact.organization.ilike(pattern)
            )
        ).order_by(Contact.last_name.asc(), Contact.first_name.asc()).limit(25).all()
        results["contacts"] = [
            {
                'id': c.id,
                'first_name': c.first_name,
                'last_name': c.last_name,
                'email': c.email,
                'phone_number': c.phone_number,
                'job_title': c.job_title,
                'organization': c.organization
            } for c in contacts
        ]

        # Search contact lists
        lists = ContactList.query.filter(
            ContactList.name.ilike(pattern)
        ).order_by(ContactList.name.asc()).limit(25).all()

        # Handle getting owner name if available (adjust as necessary)
        results["lists"] = [
            {
                "id": lst.id,
                "name": lst.name,
                "description": lst.description,
                "owner": lst.owner.name if lst.owner else None
            } for lst in lists
        ]

    return jsonify(results)


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

# @app.route('/lists/edit/<int:list_id>', methods=['GET', 'POST'])
# def edit_list(list_id):
#     list_obj = ContactList.query.get_or_404(list_id)
#     form = ContactListForm(obj=list_obj)
#     if form.validate_on_submit():
#         list_obj.name = form.name.data
#         list_obj.description = form.description.data
#         list_obj.owner = form.owner.data
#         try:
#             db.session.commit()
#             flash('Contact list updated!', 'success')
#         except Exception:
#             db.session.rollback()
#             flash('Error: Could not update list.', 'danger')
#         return redirect(url_for('lists'))
#     return render_template('edit_list.html', form=form, list_obj=list_obj)

@app.route('/lists/edit/<int:list_id>', methods=['GET', 'POST'])
def edit_list(list_id):
    list_obj = ContactList.query.get_or_404(list_id)
    form = ContactListForm(obj=list_obj)
    users = User.query.order_by(User.name).all()
    form.owner.choices = [(user.id, user.name) for user in users]
    if form.validate_on_submit():
        list_obj.name = form.name.data
        list_obj.description = form.description.data
        list_obj.owner_id = form.owner.data  # assuming foreign key is owner_id
        try:
            db.session.commit()
            flash('Contact list updated!', 'success')
        except Exception:
            db.session.rollback()
            flash('Error: Could not update list.', 'danger')
        return redirect(url_for('lists'))
    # Set current owner value if GET request
    form.owner.data = list_obj.owner_id
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

@app.route("/lists/<int:list_id>/contacts")
def get_contacts_for_list(list_id):
    contact_list = ContactList.query.get_or_404(list_id)
    contacts = [
        {
            "id": c.id,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "email": c.email,
            "phone_number": c.phone_number,
            "job_title": c.job_title,
            "organization": c.organization,
            # "notes": c.notes,    # EXCLUDED!
        }
        for c in contact_list.contacts
    ]
    return jsonify(contacts)

@app.route('/upload_contacts', methods=['GET', 'POST'])
def upload_contacts():
    lists = ContactList.query.all()  # Get all lists for the dropdown
    rejected_rows = []
    if request.method == 'POST':
        list_id = request.form.get('list_id')
        target_list = ContactList.query.get(list_id)
        if not target_list:
            flash(('danger', 'Please select a valid list.'))
            return render_template('upload_contacts.html', lists=lists)
        file = request.files.get('csv_file')
        if not file:
            flash(('danger', 'Please upload a valid CSV file.'))
            return render_template('upload_contacts.html', lists=lists)
        f = TextIOWrapper(file, encoding="utf-8")
        reader = csv.reader(f)
        for idx, row in enumerate(reader, start=1):
            try:
                first_name = row[0].strip()
                last_name = row[1].strip()
                email = row[2].strip().lower()
                phone_number = row[3].strip()
                job_title = row[4].strip()
                organization = row[5].strip()
                notes = row[6].strip()
            except Exception:
                rejected_rows.append({
                    "rownum": idx,
                    "data": row,
                    "reason": "Invalid row format"
                })
                continue

            # Try to find by email only if email is present;
            # otherwise, always create a new contact (can't deduplicate)
            contact = None
            if email:
                contact = Contact.query.filter_by(email=email).first()

            if not contact:
                contact = Contact(
                    first_name=first_name,
                    last_name=last_name,
                    email=email if email else None,
                    phone_number=phone_number,
                    job_title=job_title,
                    organization=organization,
                    notes=notes
                )
                db.session.add(contact)
                db.session.commit()

            if contact not in target_list.contacts:
                target_list.contacts.append(contact)
        db.session.commit()
        flash(('success', 'Contacts uploaded and added to the list!'))
        return render_template('upload_contacts.html', lists=lists, rejected_rows=rejected_rows)
    return render_template('upload_contacts.html', lists=lists)

@app.route("/contacts/<int:contact_id>/lists")
def get_lists_for_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    lists = contact.contact_lists.all()
    return jsonify([{"id": l.id, "name": l.name} for l in lists])


#non route helper functions.

def get_or_create_user(azure_claims):
    user = User.query.filter_by(id=azure_claims["oid"]).first()
    if not user:
        user = User(
            id=azure_claims["oid"],
            name=azure_claims.get("name"),
            email=azure_claims.get("preferred_username")  # use email claim
        )
        db.session.add(user)
        db.session.commit()
    return user



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="localhost",debug=True, reloaders=False)