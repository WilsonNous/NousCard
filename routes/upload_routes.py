from flask import Blueprint, render_template, request, jsonify
from services.importer import process_uploaded_files

upload_bp = Blueprint("upload", __name__)

@upload_bp.route("/", methods=["GET"])
def upload_page():
    return render_template("upload.html")

@upload_bp.route("/files", methods=["POST"])
def upload_files():
    files = request.files.getlist("files[]")
    if not files:
        return jsonify({"ok": False, "message": "Nenhum arquivo enviado."}), 400

    result = process_uploaded_files(files)
    return jsonify({"ok": True, "result": result})
