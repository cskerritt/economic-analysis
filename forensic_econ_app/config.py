import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "ReplaceWithASecretKeyInProduction"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "evaluee_data.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = True
