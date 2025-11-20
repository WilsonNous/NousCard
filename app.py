from flask import Flask
from config import Config
from models.base import db
from routes import register_blueprints

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ------------------------------------------------------
    # Inicializa SQLAlchemy APENAS como estrutura de modelos
    # (Não é usado para conectar ao banco)
    # ------------------------------------------------------
    db.init_app(app)

    # ------------------------------------------------------
    # Registra todas as rotas
    # ------------------------------------------------------
    register_blueprints(app)

    # ------------------------------------------------------
    # Rota simples para checagem
    # ------------------------------------------------------
    @app.route("/health")
    def health_check():
        return {"status": "ok", "app": "NousCard"}

    return app


app = create_app()

if __name__ == "__main__":
    # Debug apenas local
    app.run(host="0.0.0.0", port=5000, debug=True)
