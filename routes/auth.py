import random

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Message

from extensions import limiter, mail, db
from models import User, Account
from forms import RegisterForm, LoginForm, ResetRequestForm, ResetPasswordForm


auth_bp = Blueprint("auth", __name__)

def unique_customer_id():
    while True:
        customer_id = f"NS-{random.randint(10000000, 99999999)}"
        if not User.query.filter_by(customer_id=customer_id).first():
            return customer_id


def unique_account_number():
    while True:
        number = f"AC-{random.randint(1000000000, 9999999999)}"
        if not Account.query.filter_by(account_number=number).first():
            return number


def generate_token(email, salt):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(email, salt=salt)


def verify_token(token, salt, max_age=3600):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.loads(token, salt=salt, max_age=max_age)


def send_email(subject, recipient, body):
    """
    Production-safe email sender:
    - Falls back to console logging if SMTP fails
    """
    try:
        msg = Message(subject=subject, recipients=[recipient], body=body)
        mail.send(msg)
    except Exception as e:
        current_app.logger.warning(f"Email failed: {e}")
        print(f"\n--- EMAIL FALLBACK ---\nTo: {recipient}\n{subject}\n{body}\n")

@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        full_name = form.full_name.data.strip()
        email = form.email.data.strip().lower()
        password = form.password.data

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "warning")
            return redirect(url_for("auth.register"))

        user = User(
            customer_id=unique_customer_id(),
            full_name=full_name,
            email=email,
            password_hash=generate_password_hash(password),
            email_verified=False
        )

        db.session.add(user)
        db.session.flush()

        account = Account(
            user_id=user.id,
            bank_name="JOINT",
            account_number=unique_account_number(),
            balance_cents=0
        )

        db.session.add(account)
        db.session.commit()

        token = generate_token(email, "email-verify")
        verify_link = url_for("auth.verify_email", token=token, _external=True)

        send_email(
            "Verify your email",
            email,
            f"""Welcome to JOINT!

Your User ID is: {user.customer_id}

Verify your email:
{verify_link}

This link expires in 1 hour."""
        )

        flash(
            f"Account created successfully. Your User ID is {user.customer_id}. "
            "Check your email to verify your account.",
            "success"
        )
        return redirect(url_for("main.home"))

    return render_template("register.html", form=form)



@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user_id = form.user_id.data.strip()
        password = form.password.data

        print("LOGIN ATTEMPT:", user_id)

        user = User.query.filter_by(customer_id=user_id).first()

        print("USER FOUND:", user)

        if not user:
            print("No user found in DB")

        if user:
            print("Stored hash:", user.password_hash)
            print("Password matches:", check_password_hash(user.password_hash, password))

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid User ID or password.", "danger")
            return redirect(url_for("auth.login"))

        login_user(user, remember=form.remember.data)
        return redirect(url_for("main.dashboard"))

    return render_template("home.html", login_form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))



@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    try:
        email = verify_token(token, "email-verify", max_age=3600)
    except SignatureExpired:
        flash("Verification link expired. Please request a new one.", "warning")
        return redirect(url_for("auth.login"))
    except BadSignature:
        flash("Invalid verification link.", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()

    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.login"))

    user.email_verified = True
    db.session.commit()

    flash("Email verified successfully. You can now log in.", "success")
    return redirect(url_for("auth.login"))



@auth_bp.route("/resend-verification", methods=["POST"])
@limiter.limit("3 per minute")
def resend_verification():
    email = request.form.get("email", "").strip().lower()
    user = User.query.filter_by(email=email).first()

    if user and not user.email_verified:
        token = generate_token(email, "email-verify")
        verify_link = url_for("auth.verify_email", token=token, _external=True)

        send_email(
            "Verify your email",
            email,
            f"Verify your email here:\n{verify_link}\n\nExpires in 1 hour."
        )

    flash("If the email exists, a verification link has been sent.", "info")
    return redirect(url_for("auth.login"))



@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per minute")
def forgot_password():
    form = ResetRequestForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            token = generate_token(email, "password-reset")
            reset_link = url_for("auth.reset_password", token=token, _external=True)

            send_email(
                "Reset your password",
                email,
                f"Reset your password:\n{reset_link}\n\nExpires in 1 hour."
            )

        flash("If the email exists, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html", form=form)



@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    form = ResetPasswordForm()

    try:
        email = verify_token(token, "password-reset", max_age=3600)
    except SignatureExpired:
        flash("Reset link expired. Request a new one.", "warning")
        return redirect(url_for("auth.forgot_password"))
    except BadSignature:
        flash("Invalid reset link.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()

    if not user:
        flash("Account not found.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if form.validate_on_submit():
        user.password_hash = generate_password_hash(form.password.data)
        db.session.commit()

        flash("Password reset successful. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", form=form)