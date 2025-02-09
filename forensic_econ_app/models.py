from flask_sqlalchemy import SQLAlchemy
from decimal import Decimal
from datetime import datetime

db = SQLAlchemy()

class Evaluee(db.Model):
    """
    Represents a single Evaluee record for forensic analysis.
    """
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    uses_discounting = db.Column(db.Boolean, default=True)
    # We store discount rates in a string, e.g. "3,5,7", or "0" if no discounting.
    discount_rates_str = db.Column(db.String(200), default="3,5,7")

    # Demographics
    dob = db.Column(db.String(50))  # store as string "MM/DD/YYYY"
    doi = db.Column(db.String(50))  # likewise
    retirement_date = db.Column(db.String(50))  # "MM/DD/YYYY" if computed

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_discount_rates(self):
        """Return discount rates as a list of floats."""
        if not self.uses_discounting:
            return [0.0]
        if not self.discount_rates_str.strip():
            return [3.0, 5.0, 7.0]
        try:
            return [float(x) for x in self.discount_rates_str.split(",") if x.strip()]
        except:
            return [3.0, 5.0, 7.0]

    def to_dict(self):
        """Serialize to a dict for export."""
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "state": self.state,
            "uses_discounting": self.uses_discounting,
            "discount_rates_str": self.discount_rates_str,
            "dob": self.dob,
            "doi": self.doi,
            "retirement_date": self.retirement_date,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
