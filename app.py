from flask import Flask
from config import Config
from models.base import db
from routes import register_blueprints

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa banco
    db.init_app(app)

    # Registra blueprints
    register_blueprints(app)

    @app.route("/health")
    def health_check():
        return {"status": "ok", "app": "NousCard"}

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
