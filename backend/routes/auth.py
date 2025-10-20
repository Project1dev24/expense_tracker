from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.urls import url_parse
from backend.models.user import User
from backend.database import db
import secrets
import datetime

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')

        # Validate input
        if not email or not name or not password:
            flash('All fields are required', 'error')
            return render_template('auth/register.html')

        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered', 'error')
            return render_template('auth/register.html')

        # Create new user
        user = User(email=email, name=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember_me = 'remember_me' in request.form

        # Validate input
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('auth/login.html')

        # Check user credentials
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Invalid email or password', 'error')
            return render_template('auth/login.html')

        # Log user in
        login_user(user, remember=remember_me)
        user.update_last_seen()

        # Redirect to next page or home
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.index')

        return redirect(next_page)

    return render_template('auth/login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', user=current_user)

@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        name = request.form.get('name')

        # Validate input
        if not name:
            flash('Name is required', 'error')
            return render_template('auth/edit_profile.html')

        # Update user profile
        current_user.name = name
        db.session.commit()

        flash('Profile updated successfully', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/edit_profile.html')

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Validate input
        if not current_password or not new_password or not confirm_password:
            flash('All fields are required', 'error')
            return render_template('auth/settings.html')

        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return render_template('auth/settings.html')

        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
            return render_template('auth/settings.html')

        # Update password
        current_user.set_password(new_password)
        db.session.commit()

        flash('Password changed successfully', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/settings.html')

@bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email')

        # Validate input
        if not email:
            flash('Email is required', 'error')
            return render_template('auth/reset_password_request.html')

        # Find user by email
        user = User.query.filter_by(email=email).first()
        if user:
            # In a real application, you would send an email with a reset link
            # For this example, we'll just show the reset form directly
            flash('Check your email for password reset instructions', 'info')
            # For demo purposes, we'll redirect to the reset form directly
            return redirect(url_for('auth.reset_password', user_id=user.id))
        else:
            # For security, don't reveal if email exists or not
            flash('Check your email for password reset instructions', 'info')
            return render_template('auth/reset_password_request.html')

    return render_template('auth/reset_password_request.html')

@bp.route('/reset-password/<int:user_id>', methods=['GET', 'POST'])
def reset_password(user_id):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # Find user by ID
    user = User.query.get(user_id)
    if not user:
        flash('Invalid password reset request', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Validate input
        if not new_password or not confirm_password:
            flash('All fields are required', 'error')
            return render_template('auth/reset_password.html', user_id=user_id)

        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/reset_password.html', user_id=user_id)

        # Validate password strength
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long', 'error')
            return render_template('auth/reset_password.html', user_id=user_id)

        # Update password
        user.set_password(new_password)
        db.session.commit()

        flash('Password reset successfully! You can now log in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', user_id=user_id)
