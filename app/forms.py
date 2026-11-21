"""WTForms definitions (Flask-WTF adds CSRF protection to every form)."""
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    IntegerField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from .models import WEEKDAYS


class RegistrationForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=30),
            Regexp(r"^[A-Za-z0-9_.]+$", message="Use letters, numbers, dots or underscores only."),
        ],
    )
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create account")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Log in")


class BookingForm(FlaskForm):
    provider_id = SelectField("Healthcare provider", coerce=int, validators=[DataRequired()])
    date = DateField("Date", validators=[DataRequired()])
    slot = SelectField("Time slot", validators=[DataRequired(message="Please choose a time slot.")], validate_choice=False)
    reason = TextAreaField("Reason for visit (optional)", validators=[Optional(), Length(max=300)])
    submit = SubmitField("Book appointment")


class RescheduleForm(FlaskForm):
    date = DateField("New date", validators=[DataRequired()])
    slot = SelectField("New time slot", validators=[DataRequired(message="Please choose a time slot.")], validate_choice=False)
    submit = SubmitField("Reschedule")


class ActionForm(FlaskForm):
    """Empty form used for POST-only buttons (cancel, approve, logout) to carry the CSRF token."""


class ProviderForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=100)])
    specialty = StringField("Specialty", validators=[DataRequired(), Length(max=100)])
    start_hour = IntegerField("Start hour (0-23)", validators=[InputRequired(), NumberRange(0, 23)], default=9)
    end_hour = IntegerField("End hour (1-24)", validators=[InputRequired(), NumberRange(1, 24)], default=17)
    slot_minutes = SelectField(
        "Slot length",
        coerce=int,
        choices=[(15, "15 minutes"), (20, "20 minutes"), (30, "30 minutes"), (45, "45 minutes"), (60, "60 minutes")],
        default=30,
    )
    working_days = SelectMultipleField(
        "Working days",
        coerce=int,
        choices=list(enumerate(WEEKDAYS)),
        default=[0, 1, 2, 3, 4],
    )
    is_active = BooleanField("Accepting appointments", default=True)
    submit = SubmitField("Save provider")

    def validate_end_hour(self, field):
        if self.start_hour.data is not None and field.data is not None and field.data <= self.start_hour.data:
            raise ValidationError("End hour must be after the start hour.")

    def validate_working_days(self, field):
        if not field.data:
            raise ValidationError("Select at least one working day.")
