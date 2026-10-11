from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    EmailField,
    FloatField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])
    remember = BooleanField("Remember me")
    submit = SubmitField("Login")


class RegisterForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField("Phone", validators=[Length(max=30)])
    role = SelectField(
        "Role",
        choices=[
            ("customer", "Customer"),
            ("restaurant_owner", "Restaurant Owner"),
            ("delivery_partner", "Delivery Partner"),
        ],
        validators=[DataRequired()],
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    submit = SubmitField("Create account")


class RestaurantProfileForm(FlaskForm):
    name = StringField("Restaurant name", validators=[DataRequired(), Length(min=2, max=120)])
    description = TextAreaField("Description", validators=[Length(max=500)])
    address = StringField("Address", validators=[Length(max=255)])
    lat = FloatField("Latitude")
    lng = FloatField("Longitude")
    hero_image_url = StringField("Hero image URL", validators=[Length(max=500)])
    submit = SubmitField("Save")


class MenuItemForm(FlaskForm):
    name = StringField("Item name", validators=[DataRequired(), Length(min=2, max=120)])
    description = TextAreaField("Description", validators=[Length(max=500)])
    price_cents = IntegerField("Price (paise)", validators=[DataRequired()])
    image_url = StringField("Image URL", validators=[Length(max=500)])
    is_available = BooleanField("Available", default=True)
    submit = SubmitField("Save item")


class CheckoutForm(FlaskForm):
    delivery_address = StringField("Delivery address", validators=[DataRequired(), Length(min=3, max=255)])
    delivery_lat = FloatField("Delivery latitude")
    delivery_lng = FloatField("Delivery longitude")
    notes = TextAreaField("Notes to restaurant/rider", validators=[Length(max=500)])
    payment_method = SelectField(
        "Payment method",
        choices=[
            ("cod", "Cash on Delivery"),
            ("upi", "UPI (Simulated)"),
            ("card", "Card (Simulated)"),
        ],
        validators=[DataRequired()],
        default="cod",
    )
    submit = SubmitField("Place order")


class PaymentForm(FlaskForm):
    upi_id = StringField("UPI ID", validators=[Length(max=120)])
    card_number = StringField("Card number", validators=[Length(max=30)])
    submit = SubmitField("Pay now (Simulated)")
