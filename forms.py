from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp
from wtforms import StringField, TextAreaField, SubmitField

class ContactForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    job_title = StringField('Job Title', validators=[DataRequired()])
    organization = StringField('Organization', validators=[DataRequired()])
    notes = TextAreaField('Notes')
    phone_number = StringField(
        'Phone Number',
        validators=[
            Optional(),
            Length(max=20),
            Regexp(
                r'^\+?[\d\s().-]+$',
                message='Enter a valid phone number.'
            )
        ]
    )

    submit = SubmitField('Submit')

class ContactListForm(FlaskForm):
    name = StringField('List Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description')
    owner = StringField('Owner', validators=[DataRequired(), Length(max=120)])
    submit = SubmitField('Save List')
