from flask import Flask
from config import Config
from pymongo import MongoClient
from flask_cors import CORS  # ✅ Tambahkan ini

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ✅ Izinkan CORS hanya untuk asal frontend (Next.js)
    CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

    # ✅ Setup database
    client = MongoClient(app.config['MONGODB_URL'])
    app.db = client[app.config['DBNAME']]

    # ✅ Register blueprint
    from .routes.auth import auth_
    app.register_blueprint(auth_)

    return app
