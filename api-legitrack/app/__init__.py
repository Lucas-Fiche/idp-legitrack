from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from flask_cors import CORS
import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    CORS(app)
    db.init_app(app)          
    migrate.init_app(app, db)

    from .routes import bp

    # Importar e registrar rotas aqui
    app.register_blueprint(bp)

    from . import models

    return app