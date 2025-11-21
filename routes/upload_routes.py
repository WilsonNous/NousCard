from flask import Blueprint, render_template, request, jsonify, session
from services.importer import process_uploaded_files
from utils.auth_middleware import login_required

upload_bp = Blueprint("upload", __name__)

@upload_bp.route("/", methods=["GET"])
@login_required
def upload_page():
    return render_template("upload.html")


@upload_bp.route("/files", methods=["POST"])
@login_required
def upload_files():
    empresa_id = session.get("empresa_id")
    usuario_id = session.get("usuario_id")

    # Corrigido: o nome correto é "files"
    files = request.files.getlist("files")

    if not files:
        return jsonify({"ok": False, "message": "Nenhum arquivo enviado."}), 400

    result = process_uploaded_files(files, empresa_id, usuario_id)

    return jsonify({"ok": True, "result": result})
