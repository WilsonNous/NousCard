# models/arquivo_importado.py
from models.base import db, BaseMixin

class ArquivoImportado(db.Model, BaseMixin):
    __tablename__ = "arquivos_importados"

    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign Keys apenas (sem relationships!)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    
    # Campos de arquivo
    nome_arquivo = db.Column(db.String(255), nullable=False)
    caminho_arquivo = db.Column(db.String(500), nullable=False)
    tipo_arquivo = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(30), default="pendente")
    mensagem_erro = db.Column(db.Text, nullable=True)
    
    # ⚠️ ZERO db.relationship() aqui!
    # Para acessar usuario ou empresa, use query direta:
    # Usuario.query.get(arquivo.usuario_id)
    # Empresa.query.get(arquivo.empresa_id)

    def __repr__(self):
        return f"<ArquivoImportado {self.nome_arquivo}>"
