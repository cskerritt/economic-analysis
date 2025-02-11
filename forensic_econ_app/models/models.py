from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Model for user accounts."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Relationship with evaluees
    evaluees = db.relationship('Evaluee', backref='user', lazy=True)
    
    def set_password(self, password):
        """Set password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password."""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Evaluee(db.Model):
    """Model for storing evaluee information."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    uses_discounting = db.Column(db.Boolean, default=True)
    _discount_rates = db.Column('discount_rates', db.Text, default='[3.0, 5.0, 7.0]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Demographics data
    date_of_birth = db.Column(db.DateTime)
    date_of_injury = db.Column(db.DateTime)
    life_expectancy = db.Column(db.Numeric(10, 2))
    work_life_expectancy = db.Column(db.Numeric(10, 2))
    years_to_final_separation = db.Column(db.Numeric(10, 2))
    
    # Worklife factor data
    worklife_factor = db.Column(db.Numeric(10, 4))
    
    # AEF data
    gross_earnings_base = db.Column(db.Numeric(10, 2))
    worklife_adjustment = db.Column(db.Numeric(10, 4))
    unemployment_factor = db.Column(db.Numeric(10, 4))
    fringe_benefit = db.Column(db.Numeric(10, 4))
    tax_liability = db.Column(db.Numeric(10, 4))
    wrongful_death = db.Column(db.Boolean, default=False)
    personal_type = db.Column(db.String(50))
    personal_percentage = db.Column(db.Numeric(10, 4))
    
    # Relationships
    earnings_scenarios = db.relationship('EarningsScenario', backref='evaluee', lazy=True)

    @property
    def discount_rates(self):
        return json.loads(self._discount_rates)
    
    @discount_rates.setter
    def discount_rates(self, value):
        self._discount_rates = json.dumps(value)

class EarningsScenario(db.Model):
    """Model for storing earnings calculation scenarios."""
    id = db.Column(db.Integer, primary_key=True)
    evaluee_id = db.Column(db.Integer, db.ForeignKey('evaluee.id'), nullable=False)
    scenario_name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    wage_base = db.Column(db.Numeric(10, 2), nullable=False)
    residual_base = db.Column(db.Numeric(10, 2))
    growth_rate = db.Column(db.Numeric(10, 4))
    adjustment_factor = db.Column(db.Numeric(10, 4))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Store calculation results
    present_value = db.Column(db.Numeric(15, 2))
    total_loss = db.Column(db.Numeric(15, 2))
    
    # Add relationship to offset wages
    offset_wages = db.relationship('OffsetWage', backref='scenario', lazy=True, cascade='all, delete-orphan')

class OffsetWage(db.Model):
    """Model for storing offset wages for specific years in a scenario."""
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('earnings_scenario.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class HealthcareScenario(db.Model):
    """Model for storing healthcare expense scenarios."""
    id = db.Column(db.Integer, primary_key=True)
    evaluee_id = db.Column(db.Integer, db.ForeignKey('evaluee.id'), nullable=False)
    scenario_name = db.Column(db.String(100), nullable=False)
    growth_method = db.Column(db.String(20), default='CPI')  # CPI, PCE, or custom
    growth_rate_custom = db.Column(db.Numeric(10, 4))
    discount_method = db.Column(db.String(20), default='nominal')  # nominal, real, or net
    discount_rate = db.Column(db.Numeric(10, 4))
    partial_offset = db.Column(db.Boolean, default=False)
    total_offset = db.Column(db.Boolean, default=False)
    projection_years = db.Column(db.Integer, default=20)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    medical_items = db.relationship('MedicalItem', backref='scenario', lazy=True, cascade='all, delete-orphan')
    evaluee = db.relationship('Evaluee', backref='healthcare_scenarios', lazy=True)

class MedicalItem(db.Model):
    """Model for storing medical items within a healthcare scenario."""
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('healthcare_scenario.id'), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    annual_cost = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CPIRate(db.Model):
    """Model for storing universal CPI rates."""
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, unique=True)
    rate = db.Column(db.Numeric(10, 4), nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_rate(category):
        """Get the rate for a specific CPI category."""
        rate = CPIRate.query.filter_by(category=category).first()
        return float(rate.rate) if rate else None

    def __repr__(self):
        return f'<CPIRate {self.category}: {self.rate}%>' 