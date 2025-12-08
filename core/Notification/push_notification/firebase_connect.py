# firebase_connect.py
import firebase_admin
from firebase_admin import credentials, messaging
from decouple import config
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIREBASE_JSON_PATH = config(
    'FIRE_BASE_MESSAGES',
    default=os.path.join(BASE_DIR, 'admas-9e2c7-9bcdd20b9461.json')
    ) 

def initialize_firebase():
    """
    Initialize Firebase app with service account JSON.
    Returns the firebase app instance.
    """
    # If already initialized, return the existing app
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_JSON_PATH)
        app = firebase_admin.initialize_app(cred)
        return app
    else:
        return firebase_admin.get_app()