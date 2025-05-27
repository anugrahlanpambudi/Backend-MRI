from flask import Flask
from config import Config
from pymongo import MongoClient
from flask_cors import CORS  # ✅ Tambahkan ini

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ✅ Izinkan CORS hanya untuk asal frontend (Next.js)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ✅ Setup database
    client = MongoClient(app.config['MONGODB_URL'])
    app.db = client[app.config['DBNAME']]

    # ✅ Register blueprint
    from .routes.auth import auth_
    app.register_blueprint(auth_)

     # ✅ Predict blueprint
    from .routes.predict import predict_
    app.register_blueprint(predict_)

    from .routes.profile import profile_
    app.register_blueprint(profile_)


    return app
