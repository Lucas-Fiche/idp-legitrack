from flask import Flask, jsonify
from flask_cors import CORS
from .routes import bp

def create_app():
    app = Flask(__name__)

    CORS(app)

    # Importar e registrar rotas aqui
    app.register_blueprint(bp)

    return app

