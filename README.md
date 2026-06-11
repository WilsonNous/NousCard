# 💳 NousCard - Assistente Financeiro Inteligente

> Transforme seu extrato bancário em inteligência financeira automática.

**NousCard** é uma plataforma de gestão financeira inteligente para micro e pequenas empresas (salões, barbearias, pequenas lojas, etc.). Importe seu extrato bancário (OFX/CSV) e tenha automaticamente:

- 📊 **Dashboard financeiro** com KPIs em tempo real
- 💰 **Separação automática** de entradas e saídas
- 🏷️ **Categorização inteligente** (vendas cartão, PIX, impostos, fornecedores)
- 💡 **Insights automáticos** sobre sua saúde financeira
- 🔄 **Conciliação bancária** com vendas da maquininha
- 🏢 **Multi-tenant** (cada empresa com dados isolados)

---

## 🎯 O Problema que Resolvemos

Pequenos empresários perdem horas tentando entender:
- ❌ Quanto realmente venderam no cartão?
- ❌ Quanto receberam de PIX?
- ❌ Quanto gastaram com fornecedores?
- ❌ Quanto pagaram de impostos?
- ❌ As taxas da maquininha estão corretas?

**O NousCard responde tudo isso em segundos**, automaticamente, sem planilhas.

---

## ✨ Features Principais

### 📈 Dashboard Financeiro Inteligente
- KPIs de entradas, saídas e saldo do período
- Breakdown visual de receitas (Cartão, PIX, Transferências)
- Breakdown visual de despesas (Fornecedores, Impostos, Outras)
- Insights automáticos baseados nos dados
- Seletor de período (mês atual, anterior, últimos 3 meses)

### 🏦 Importação Inteligente de Extratos
- **OFX** (extrato bancário de qualquer banco brasileiro)
- **CSV** (exportação de bancos e planilhas)
- **Excel** (XLSX/XLS)
- **Flow CSV** (relatório da Flow para vendas)
- Divisão automática de arquivos grandes (evita timeout)
- Extração automática de dados da conta bancária

### 🏷️ Categorização Automática
O sistema identifica automaticamente:
- 💳 Vendas via Maquininha (Mastercard, Visa, Elo, Maestro)
- ⚡ PIX Recebido (vendas de clientes)
- 🏪 PIX Emitido (pagamentos a fornecedores)
- 🏛️ Tributos e Impostos (DAS, RFB, Simples Nacional)
- 💸 Empréstimos e Financiamentos
- 📦 Investimentos (RDC, CDB, aplicações)
- 🛡️ Seguros
- 💼 Tarifas Bancárias

### 🔄 Conciliação Bancária
- Cruzamento automático de vendas (maquininha) com recebimentos (banco)
- Detecção de divergências e taxas indevidas
- Suporte a conciliação manual para casos especiais
- Match por NSU, valor e data com tolerâncias configuráveis

### 🔒 Multi-Tenancy Seguro
- Isolamento total de dados por empresa
- Sistema de permissões (Master, Admin, Usuário)
- Auditoria completa de ações
- Criptografia de dados sensíveis

### 🚀 Performance
- Parser OFX ultra-rápido (split de string, não regex)
- Processamento em chunks para arquivos grandes
- Batches otimizados para banco de dados
- Timeout inteligente para evitar travamentos

---

## 🏗️ Stack Tecnológica

### Backend
- **Python 3.11+**
- **Flask 2.3** (framework web)
- **Flask-SQLAlchemy** (ORM)
- **Flask-Login** (autenticação)
- **Flask-Migrate** (migrations)
- **PyMySQL** (driver MySQL)

### Frontend
- **HTML5 + CSS3 + JavaScript**
- Design system próprio (paleta estilo Facebook)
- Responsivo (mobile-first)
- Gráficos interativos

### Banco de Dados
- **MySQL 5.7+** (produção)
- **SQLite** (desenvolvimento)

### Deploy
- **Render** (Web Service)
- **HostGator** (MySQL)

### Bibliotecas Especiais
- `openpyxl` (parser Excel)
- `chardet` (detecção de encoding)
- `ofxparse` (parser OFX - com fallback customizado)

---

## 🚀 Como Rodar Localmente

### Pré-requisitos
- Python 3.11+
- MySQL 5.7+ (ou SQLite para desenvolvimento)
- Git

### Instalação

```bash
# Clonar o repositório
git clone https://github.com/seuusuario/nouscard.git
cd nouscard

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Edite .env com suas configurações:
#   SECRET_KEY=sua_chave_secreta
#   DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/nouscard_db
#   ENCRYPTION_KEY=sua_chave_de_criptografia

# Inicializar banco de dados
flask db upgrade

# Criar usuário master (opcional)
flask shell
>>> from models import Usuario, db
>>> user = Usuario(nome="Admin", email="admin@nouscard.com", master=True)
>>> user.set_password("senha123")
>>> db.session.add(user)
>>> db.session.commit()
>>> exit()

# Rodar a aplicação
flask --app app run --debug

Acesse: `http://localhost:5000`

---

## 📖 Como Funciona

### 1️⃣ Cadastro da Empresa
- Crie sua empresa no painel
- Configure dados básicos (nome, CNPJ, endereço)

### 2️⃣ Importação do Extrato
- Faça upload do extrato bancário (OFX/CSV)
- Sistema identifica automaticamente:
  - Dados da conta bancária
  - Tipo de cada transação
  - Categoria financeira

### 3️⃣ Dashboard Inteligente
- Visualize KPIs em tempo real
- Veja breakdown de receitas e despesas
- Receba insights automáticos

### 4️⃣ Conciliação (Opcional)
- Importe vendas da maquininha (CSV da adquirente)
- Sistema cruza automaticamente com recebimentos
- Identifique divergências e taxas indevidas

---

## 🎨 Paleta de Cores

Design system próprio inspirado no Facebook:

```css
--primary: #1877F2;        /* Azul Facebook */
--primary-dark: #166FE5;
--primary-light: #E7F3FF;

--success: #42B72A;        /* Verde */
--error: #F02849;          /* Vermelho */
--warning: #F7B928;        /* Amarelo */

--text: #1C1E21;           /* Texto principal */
--text-muted: #65676B;     /* Texto secundário */
--gray-light: #F0F2F5;     /* Fundo */

## 🗺️ Roadmap

### ✅ Concluído
- [x] Multi-tenancy com isolamento de dados
- [x] Parser OFX ultra-rápido
- [x] Categorização automática de transações
- [x] Dashboard financeiro com KPIs
- [x] Insights inteligentes
- [x] Conciliação bancária automática
- [x] Suporte a CSV, Excel, OFX, Flow

### 🚧 Em Progresso
- [ ] Gráficos interativos (Chart.js)
- [ ] Exportação de relatórios (PDF/Excel)
- [ ] Alertas automáticos (email/SMS)
- [ ] Integração com APIs de bancos (Open Finance)

### 📋 Próximos Passos
- [ ] App mobile (React Native)
- [ ] Integração com contabilidade
- [ ] Previsão de fluxo de caixa (IA)
- [ ] Marketplace de serviços financeiros

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## 👥 Autores

- **Wilson Martins** - *Idealizador e Desenvolvedor Principal* - [Nous Tecnologia](https://noustecnologia.com.br)

---

## 🙏 Agradecimentos

- Comunidade Flask e Python
- Todos os pequenos empresários que testaram e deram feedback
- Equipe Nous Tecnologia

---

## 📞 Contato

- **Email:** contato@noustecnologia.com.br
- **Website:** [https://noustecnologia.com.br](https://noustecnologia.com.br)
- **LinkedIn:** [Nous Tecnologia](https://linkedin.com/company/noustecnologia)

---

## 🌟 Showcase

Empresas que já usam o NousCard:

- 💈 **Barbearias**
- 💇 **Salões de Beleza**
- 🏪 **Pequenas Lojas**
- 🍔 **Restaurantes**
- 🏥 **Clínicas**

---

<div align="center">

**Feito com 💙 por Nous Tecnologia**

[⭐ Star this repo](https://github.com/seuusuario/nouscard) | [🐛 Report bug](https://github.com/seuusuario/nouscard/issues) | [📖 Documentation](https://github.com/seuusuario/nouscard/wiki)

</div>

---

## 📋 Checklist de Atualização

Antes de fazer o commit, verifique:

- [ ] Atualize o link do GitHub (`seuusuario/nouscard`)
- [ ] Adicione screenshots na pasta `/docs/screenshots/`
- [ ] Crie arquivo `.env.example` com variáveis de exemplo
- [ ] Adicione arquivo `LICENSE` (MIT)
- [ ] Atualize `requirements.txt` com todas as dependências
- [ ] Teste o README localmente (visualize no GitHub)
