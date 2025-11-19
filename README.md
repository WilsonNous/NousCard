# 💳 NousCard

NousCard é uma plataforma simples e visual para conciliação de recebíveis de cartão
voltada para micro e pequenas empresas (salões, barbearias, pequenas lojas, etc.).

## 🎯 Objetivo

- Mostrar quanto o cliente **vendeu** no cartão
- Mostrar quanto ele **realmente recebeu** no banco
- Indicar se ele está **perdendo dinheiro** em taxas ou cobranças indevidas

Tudo de forma visual, em linguagem simples e sem termos técnicos.

---

## 🏗️ Stack

- Python + Flask
- Flask-SQLAlchemy + MySQL
- HTML + CSS + JS (visual estilo fintech)
- Deploy em Render (Web Service)
- Banco em MySQL (ex.: HostGator)

---

## 🚀 Como rodar localmente

```bash
git clone https://github.com/seuusuario/nouscard.git
cd nouscard

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

# Configurar variáveis de ambiente:
#   SECRET_KEY
#   DATABASE_URL (mysql+pymysql://user:pass@host:3306/nouscard_db)

flask --app app run
