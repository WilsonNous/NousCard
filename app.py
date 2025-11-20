# app.py
from flask import Flask, g
from config import Config
from models.base import db
from routes import register_blueprints
from datetime import datetime

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa banco
    db.init_app(app)

    # Registra blueprints
    register_blueprints(app)

    # ---------------------------------------------------------
    # DISPONIBILIZA O USUÁRIO PARA TODOS TEMPLATES
    # ---------------------------------------------------------
    @app.context_processor
    def inject_user():
        return {"usuario": getattr(g, "user", None)}

    # ---------------------------------------------------------
    # DISPONIBILIZA VARIÁVEIS GLOBAIS (ANO ATUAL, ETC)
    # ---------------------------------------------------------
    @app.context_processor
    def inject_globals():
        return {
            "current_year": datetime.utcnow().year
        }

    # ---------------------------------------------------------
    # HEALTH CHECK
    # ---------------------------------------------------------
    @app.route("/health")
    def health_check():
        return {"status": "ok", "app": "NousCard"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
