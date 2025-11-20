# app.py
from flask import Flask, g
from config import Config
from models.base import db
from routes import register_blueprints

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    register_blueprints(app)

    @app.context_processor
    def inject_user():
        # Disponibiliza "usuario" automaticamente em todos os templates
        return {"usuario": getattr(g, "user", None)}

    @app.route("/health")
    def health_check():
        return {"status": "ok", "app": "NousCard"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
