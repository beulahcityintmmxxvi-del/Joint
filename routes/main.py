import calendar
import csv
import random
from io import StringIO, BytesIO
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session, send_file
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from extensions import db
from forms import LoginForm
from models import Transaction, Notification, User, Account

main_bp = Blueprint("main", __name__)

from forms import LoginForm

@main_bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("home.html", login_form=LoginForm())

@main_bp.route("/dashboard")
@login_required
def dashboard():
    account = current_user.account
    txs = (
        Transaction.query
        .filter_by(account_id=account.id)
        .order_by(Transaction.created_at.desc())
        .limit(8)
        .all()
    )
    return render_template("dashboard.html", account=account, transactions=txs)

@main_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user
    account = user.account

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_profile":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()

            if not full_name or not email:
                flash("Full name and email are required.", "danger")
                return redirect(url_for("main.profile"))

            existing_user = User.query.filter(User.email == email, User.id != user.id).first()
            if existing_user:
                flash("That email is already in use.", "warning")
                return redirect(url_for("main.profile"))

            user.full_name = full_name
            user.email = email
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("main.profile"))

        if action == "change_password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not current_password or not new_password or not confirm_password:
                flash("Please complete all password fields.", "danger")
                return redirect(url_for("main.profile"))

            if not check_password_hash(user.password_hash, current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("main.profile"))

            if new_password != confirm_password:
                flash("New passwords do not match.", "warning")
                return redirect(url_for("main.profile"))

            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash("Password changed successfully.", "success")
            return redirect(url_for("main.profile"))

    return render_template("profile.html", account=account)

@main_bp.route("/transactions")
@login_required
def transactions():
    account = current_user.account

    tx_type = request.args.get("type", "all").lower()
    status = request.args.get("status", "all").lower()
    q = request.args.get("q", "").strip()

    query = Transaction.query.filter_by(account_id=account.id)

    if tx_type in {"debit", "credit"}:
        query = query.filter(Transaction.tx_type == tx_type)

    if status in {"pending", "completed", "failed"}:
        query = query.filter(Transaction.status == status)

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Transaction.receiver.ilike(like),
                Transaction.purpose.ilike(like)
            )
        )

    txs = query.order_by(Transaction.created_at.desc()).all()
    all_txs = Transaction.query.filter_by(account_id=account.id).all()

    total_sent_cents = sum(
        tx.amount_cents for tx in all_txs
        if tx.tx_type == "debit" and tx.status == "completed"
    )

    total_received_cents = sum(
        tx.amount_cents for tx in all_txs
        if tx.tx_type == "credit" and tx.status == "completed"
    )

    pending_count = sum(1 for tx in all_txs if tx.status == "pending")
    completed_count = sum(1 for tx in all_txs if tx.status == "completed")

    now = datetime.utcnow()
    month_total_cents = sum(
        tx.amount_cents for tx in all_txs
        if tx.created_at.year == now.year and tx.created_at.month == now.month and tx.tx_type == "debit"
    )

    return render_template(
        "transactions.html",
        account=account,
        transactions=txs,
        total_sent_cents=total_sent_cents,
        total_received_cents=total_received_cents,
        pending_count=pending_count,
        completed_count=completed_count,
        month_total_cents=month_total_cents,
        filters={"type": tx_type, "status": status, "q": q}
    )

@main_bp.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    if request.method == "POST":
        receiver = request.form.get("receiver", "").strip()
        purpose = request.form.get("purpose", "").strip()
        amount_raw = request.form.get("amount", "").replace(",", "").strip()

        if not receiver or not purpose or not amount_raw:
            flash("Please complete all transfer fields.", "danger")
            return render_template("transfer.html")

        try:
            amount_decimal = Decimal(amount_raw)
            amount_cents = int((amount_decimal * 100).to_integral_value())
        except (InvalidOperation, ValueError):
            flash("Enter a valid amount.", "danger")
            return render_template("transfer.html")

        if amount_cents <= 0:
            flash("Transfer amount must be greater than zero.", "danger")
            return render_template("transfer.html")

        account = current_user.account
        if amount_cents > account.balance_cents:
            flash("Insufficient funds.", "warning")
            return render_template("transfer.html")

        session["draft_transfer"] = {
            "receiver": receiver,
            "purpose": purpose,
            "amount_cents": amount_cents,
            "amount_display": f"{amount_cents / 100:,.2f}"
        }

        return render_template("transfer_review.html", draft=session["draft_transfer"])

    return render_template("transfer.html")

@main_bp.route("/transfer/confirm", methods=["POST"])
@login_required
def transfer_confirm():
    draft = session.get("draft_transfer")
    if not draft:
        flash("Transfer session expired. Please try again.", "warning")
        return redirect(url_for("main.transfer"))

    account = current_user.account
    amount_cents = int(draft["amount_cents"])

    if amount_cents > account.balance_cents:
        flash("Insufficient funds.", "danger")
        session.pop("draft_transfer", None)
        return redirect(url_for("main.transfer"))

    otp = f"{random.randint(100000, 999999)}"

    tx = Transaction(
        account_id=account.id,
        amount_cents=amount_cents,
        tx_type="debit",
        receiver=draft["receiver"],
        purpose=draft["purpose"],
        status="pending",
        otp_hash=generate_password_hash(otp),
        otp_expires_at=datetime.utcnow() + timedelta(minutes=10)
    )

    db.session.add(tx)
    db.session.flush()

    db.session.add(Notification(
        user_id=current_user.id,
        category="transfer",
        title="Transfer pending authorization",
        message=f"A transfer of ${amount_cents / 100:,.2f} to {draft['receiver']} is waiting for OTP verification.",
        is_read=False
    ))

    db.session.commit()
    session.pop("draft_transfer", None)

    print(f"[DEV OTP] Transaction #{tx.id}: {otp}")

    flash("Transfer created. Enter the OTP to authorize it.", "info")
    return redirect(url_for("main.verify_otp", tx_id=tx.id))

@main_bp.route("/verify-otp/<int:tx_id>", methods=["GET", "POST"])
@login_required
def verify_otp(tx_id):
    tx = Transaction.query.get_or_404(tx_id)

    if tx.account.user_id != current_user.id:
        abort(403)

    if tx.status != "pending":
        flash("This transaction is no longer pending.", "info")
        return redirect(url_for("main.dashboard"))

    if tx.otp_expires_at and datetime.utcnow() > tx.otp_expires_at:
        tx.status = "failed"
        db.session.add(Notification(
            user_id=current_user.id,
            category="transfer",
            title="Transfer authorization expired",
            message=f"Transfer #{tx.id} expired before OTP confirmation.",
            is_read=False
        ))
        db.session.commit()
        flash("OTP expired. Transaction failed.", "danger")
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()

        if check_password_hash(tx.otp_hash, otp):
            account = current_user.account

            if account.balance_cents < tx.amount_cents:
                tx.status = "failed"
                db.session.add(Notification(
                    user_id=current_user.id,
                    category="account",
                    title="Transfer failed due to insufficient funds",
                    message=f"Transfer #{tx.id} could not be completed because funds were unavailable at approval time.",
                    is_read=False
                ))
                db.session.commit()
                flash("Insufficient funds at approval time.", "danger")
                return redirect(url_for("main.dashboard"))

            account.balance_cents -= tx.amount_cents
            tx.status = "completed"
            tx.otp_hash = None

            db.session.add(Notification(
                user_id=current_user.id,
                category="transfer",
                title="Transfer completed",
                message=f"Transfer #{tx.id} to {tx.receiver} was completed successfully.",
                is_read=False
            ))

            db.session.commit()

            flash("Transaction authorized successfully.", "success")
            return redirect(url_for("main.receipt", tx_id=tx.id))

        flash("Invalid OTP. Please try again.", "danger")

    return render_template("verify_otp.html", tx=tx)

@main_bp.route("/receipt/<int:tx_id>")
@login_required
def receipt(tx_id):
    tx = Transaction.query.get_or_404(tx_id)

    if tx.account.user_id != current_user.id:
        abort(403)

    if tx.status != "completed":
        flash("Receipt is only available for completed transactions.", "warning")
        return redirect(url_for("main.dashboard"))

    receipt_ref = f"NSR-{tx.id:08d}"

    return render_template(
        "receipt.html",
        tx=tx,
        account=current_user.account,
        receipt_ref=receipt_ref
    )

@main_bp.route("/notifications")
@login_required
def notifications():

    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()

    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()

    security_count = Notification.query.filter_by(
        user_id=current_user.id,
        category="security"
    ).count()

    transfer_count = Notification.query.filter_by(
        user_id=current_user.id,
        category="transfer"
    ).count()

    account_count = Notification.query.filter_by(
        user_id=current_user.id,
        category="account"
    ).count()

    
    total_transferred = db.session.query(
        func.count(Transaction.id)
    ).join(Account, Transaction.account_id == Account.id).filter(
        Account.user_id == current_user.id,
        Transaction.tx_type == "debit"
    ).scalar() or 0

    return render_template(
    "notifications.html",
    notifications=notifications,
    unread_count=unread_count,
    security_count=security_count,
    transfer_count=transfer_count,
    account_count=account_count,
    total_transferred=total_transferred,
)

    unread_count = sum(1 for n in notes if not n.is_read)
    security_count = sum(1 for n in notes if n.category == "security")
    transfer_count = sum(1 for n in notes if n.category == "transfer")
    account_count = sum(1 for n in notes if n.category == "account")

    return render_template(
        "notifications.html",
        notifications=notes,
        unread_count=unread_count,
        security_count=security_count,
        transfer_count=transfer_count,
        account_count=account_count
    )

@main_bp.route("/notifications/read/<int:notif_id>", methods=["POST"])
@login_required
def read_notification(notif_id):
    note = Notification.query.get_or_404(notif_id)

    if note.user_id != current_user.id:
        abort(403)

    note.is_read = True
    db.session.commit()

    return redirect(url_for("main.notifications"))

@main_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all_notifications():
    notes = Notification.query.filter_by(user_id=current_user.id, is_read=False).all()

    for note in notes:
        note.is_read = True

    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("main.notifications"))

def get_statement_period(month=None, year=None):
    today = datetime.utcnow()

    if month is None:
        month = today.month
    if year is None:
        year = today.year

    start = datetime(year, month, 1)

    if month == 12:
        next_month_start = datetime(year + 1, 1, 1)
    else:
        next_month_start = datetime(year, month + 1, 1)

    end = min(today, next_month_start - timedelta(microseconds=1))
    return start, end, month, year

def build_statement_data(account, start, end):
    all_txs = Transaction.query.filter_by(account_id=account.id).all()

    def signed_value(tx):
        if tx.status != "completed":
            return 0
        return tx.amount_cents if tx.tx_type == "credit" else -tx.amount_cents

    period_txs = [tx for tx in all_txs if start <= tx.created_at <= end]
    period_txs.sort(key=lambda x: x.created_at, reverse=True)

    net_after_end = sum(signed_value(tx) for tx in all_txs if tx.created_at > end)
    net_period = sum(signed_value(tx) for tx in period_txs)

    closing_balance_cents = account.balance_cents - net_after_end
    opening_balance_cents = closing_balance_cents - net_period

    total_debits_cents = sum(
        tx.amount_cents for tx in period_txs
        if tx.status == "completed" and tx.tx_type == "debit"
    )

    total_credits_cents = sum(
        tx.amount_cents for tx in period_txs
        if tx.status == "completed" and tx.tx_type == "credit"
    )

    completed_count = sum(1 for tx in period_txs if tx.status == "completed")
    pending_count = sum(1 for tx in period_txs if tx.status == "pending")
    failed_count = sum(1 for tx in period_txs if tx.status == "failed")

    statement_ref = f"NST-{start.year}{start.month:02d}-{account.id:06d}"
    period_label = f"{calendar.month_name[start.month]} {start.year}"

    return {
        "period_txs": period_txs,
        "opening_balance_cents": opening_balance_cents,
        "closing_balance_cents": closing_balance_cents,
        "total_debits_cents": total_debits_cents,
        "total_credits_cents": total_credits_cents,
        "completed_count": completed_count,
        "pending_count": pending_count,
        "failed_count": failed_count,
        "statement_ref": statement_ref,
        "period_label": period_label,
    }

@main_bp.route("/statements")
@login_required
def statements():
    account = current_user.account

    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    start, end, month, year = get_statement_period(month, year)
    statement_data = build_statement_data(account, start, end)

    today = datetime.utcnow()
    years = list(range(today.year - 5, today.year + 1))

    return render_template(
        "statements.html",
        account=account,
        selected_month=month,
        selected_year=year,
        years=years,
        start_date=start,
        end_date=end,
        **statement_data
    )

@main_bp.route("/statements/export/csv")
@login_required
def export_statement_csv():
    account = current_user.account

    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    start, end, month, year = get_statement_period(month, year)
    statement_data = build_statement_data(account, start, end)
    txs = statement_data["period_txs"]

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Statement Reference", statement_data["statement_ref"]])
    writer.writerow(["Period", statement_data["period_label"]])
    writer.writerow([])

    writer.writerow(["Date", "Time", "Receiver", "Purpose", "Type", "Status", "Amount"])

    for tx in txs:
        writer.writerow([
            tx.created_at.strftime("%Y-%m-%d"),
            tx.created_at.strftime("%I:%M %p"),
            tx.receiver,
            tx.purpose,
            tx.tx_type,
            tx.status,
            f"{tx.amount_cents / 100:,.2f}"
        ])

    csv_bytes = BytesIO()
    csv_bytes.write(output.getvalue().encode("utf-8"))
    csv_bytes.seek(0)

    filename = f"northstar-statement-{year}-{month:02d}.csv"

    return send_file(
        csv_bytes,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )

@main_bp.route("/statements/export/pdf")
@login_required
def export_statement_pdf():
    account = current_user.account

    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    start, end, month, year = get_statement_period(month, year)
    statement_data = build_statement_data(account, start, end)
    txs = statement_data["period_txs"]

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 50
    y = height - 50

    def draw_text(text, x, y_pos, size=10, bold=False):
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        pdf.drawString(x, y_pos, str(text))

    draw_text("Northstar Bank", margin, y, 18, True)
    y -= 22
    draw_text("Account Statement", margin, y, 14, True)
    y -= 18
    draw_text(f"Statement Reference: {statement_data['statement_ref']}", margin, y, 10)
    y -= 14
    draw_text(f"Period: {statement_data['period_label']}", margin, y, 10)
    y -= 14
    draw_text(f"Account Number: {account.account_number}", margin, y, 10)
    y -= 24

    draw_text("Summary", margin, y, 12, True)
    y -= 16
    summary_lines = [
        f"Opening Balance: ${statement_data['opening_balance_cents'] / 100:,.2f}",
        f"Closing Balance: ${statement_data['closing_balance_cents'] / 100:,.2f}",
        f"Total Debits: ${statement_data['total_debits_cents'] / 100:,.2f}",
        f"Total Credits: ${statement_data['total_credits_cents'] / 100:,.2f}",
        f"Completed: {statement_data['completed_count']}",
        f"Pending: {statement_data['pending_count']}",
        f"Failed: {statement_data['failed_count']}",
    ]

    for line in summary_lines:
        draw_text(line, margin, y, 10)
        y -= 14

    y -= 10
    draw_text("Transactions", margin, y, 12, True)
    y -= 16

    draw_text("Date", margin, y, 9, True)
    draw_text("Receiver", margin + 90, y, 9, True)
    draw_text("Purpose", margin + 210, y, 9, True)
    draw_text("Type", margin + 390, y, 9, True)
    draw_text("Status", margin + 450, y, 9, True)
    draw_text("Amount", margin + 520, y, 9, True)
    y -= 12

    for tx in txs:
        if y < 70:
            pdf.showPage()
            y = height - 50

        draw_text(tx.created_at.strftime("%b %d, %Y"), margin, y, 8)
        draw_text(tx.receiver[:18], margin + 90, y, 8)
        draw_text(tx.purpose[:28], margin + 210, y, 8)
        draw_text(tx.tx_type.capitalize(), margin + 390, y, 8)
        draw_text(tx.status.capitalize(), margin + 450, y, 8)
        draw_text(f"${tx.amount_cents / 100:,.2f}", margin + 520, y, 8)
        y -= 12

    pdf.save()
    buffer.seek(0)

    filename = f"northstar-statement-{year}-{month:02d}.pdf"

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )