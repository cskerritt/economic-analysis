from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from ..models.models import db, User
from werkzeug.urls import url_parse

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login."""
    if current_user.is_authenticated:
        return redirect(url_for('evaluee.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user = User.query.filter_by(username=username).first()
        
        if user is None or not user.check_password(password):
            flash('Invalid username or password')
            return redirect(url_for('auth.login'))
        
        if not user.is_active:
            flash('This account has been deactivated. Please contact support.')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('evaluee.index')
        
        return redirect(next_page)
    
    return render_template('auth/login.html')

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration."""
    if current_user.is_authenticated:
        return redirect(url_for('evaluee.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([username, email, password, confirm_password]):
            flash('All fields are required.')
            return redirect(url_for('auth.signup'))
        
        if password != confirm_password:
            flash('Passwords do not match.')
            return redirect(url_for('auth.signup'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('auth.signup'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.')
            return redirect(url_for('auth.signup'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Registration successful! Welcome to Economic Analysis.')
            return redirect(url_for('evaluee.index'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration.')
            return redirect(url_for('auth.signup'))
    
    return render_template('auth/signup.html')

@bp.route('/logout')
@login_required
def logout():
    """User logout."""
    logout_user()
    return redirect(url_for('auth.login'))

@bp.route('/profile')
@login_required
def profile():
    """User profile."""
    return render_template('auth/profile.html') 