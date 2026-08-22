# 💳 NousCard

> **Gestão simples. Operação organizada. Financeiro sob controle.**

O **NousCard** é uma plataforma desenvolvida pela **Nous Tecnologia** para apoiar pequenas empresas e prestadores de serviços na gestão do negócio, integrando em um único ambiente:

**Clientes → Orçamentos → Ordens de Serviço → Financeiro → Resultados**

O projeto nasceu inicialmente com foco em gestão financeira, importação de extratos bancários, movimentações de adquirentes, conciliação e DRE.

Em 2026, o NousCard entrou em uma nova fase, ampliando sua proposta para também organizar a operação comercial e a execução de serviços de pequenas empresas.

🌐 **Website:** [https://nouscard.com.br](https://nouscard.com.br)

---

## 🎯 Visão do Produto

Muitos pequenos empresários ainda administram partes importantes da operação utilizando:

- 📒 cadernos;
- 📱 WhatsApp;
- 📊 planilhas;
- 🧾 documentos separados;
- 💰 internet banking;
- 🧠 informações que ficam apenas na memória.

O NousCard busca reduzir essa fragmentação oferecendo uma plataforma simples para acompanhar o ciclo completo da empresa:

```text
Cliente
   ↓
Orçamento
   ↓
Aprovação
   ↓
Ordem de Serviço
   ↓
Execução
   ↓
Financeiro
   ↓
Resultado
```

A proposta não é criar um ERP excessivamente complexo.

O objetivo é entregar **gestão prática para pequenas empresas que precisam trabalhar, e não administrar um sistema complicado**.

---

# ✨ Módulos Principais

## 👥 Gestão de Clientes

Base comercial centralizada para cadastro e consulta de clientes.

Principais recursos:

- cadastro de pessoa física ou jurídica;
- CPF/CNPJ;
- telefone e WhatsApp;
- e-mail;
- endereço;
- observações;
- vínculo com orçamentos;
- vínculo com ordens de serviço.

---

## 🧾 Orçamentos

Permite criar propostas comerciais estruturadas e acompanhar sua evolução.

### Informações disponíveis

- número automático;
- cliente;
- data;
- validade;
- descrição;
- itens;
- quantidade;
- valor unitário;
- desconto;
- total;
- condições de pagamento;
- prazo estimado;
- observações;
- imagens quando aplicável.

### Fluxo

```text
Rascunho
   ↓
Enviado
   ↓
Aprovado
   ↓
Ordem de Serviço
```

Também é possível registrar orçamentos recusados.

O objetivo é permitir futuramente a geração e compartilhamento de documentos profissionais em PDF.

---

## 🛠️ Ordens de Serviço

Um orçamento aprovado pode ser convertido em uma **Ordem de Serviço**, reaproveitando os dados já cadastrados.

A OS permite acompanhar a execução do trabalho.

### Informações

- número da OS;
- cliente;
- endereço da execução;
- descrição do serviço;
- informações técnicas;
- medidas;
- fotos;
- data prevista;
- responsável;
- observações.

### Status

```text
Aguardando material
        ↓
Material recebido
        ↓
Agendado
        ↓
Em execução
        ↓
Concluído
```

A evolução futura prevê integração direta da conclusão da OS com o financeiro e contas a receber.

---

# 💰 Gestão Financeira

O núcleo financeiro original do NousCard continua fazendo parte da plataforma.

## 📈 Dashboard Financeiro

Visualização consolidada da situação financeira da empresa.

Inclui:

- entradas;
- saídas;
- saldo;
- despesas;
- receitas;
- indicadores gerenciais;
- visão de resultado;
- análise por período.

---

## 🏦 Importação de Extratos

O NousCard possui estrutura para importação e processamento de arquivos financeiros.

Formatos suportados incluem:

- OFX;
- CSV;
- Excel;
- arquivos de adquirentes;
- relatórios financeiros específicos.

O processamento foi desenvolvido para trabalhar também com arquivos maiores utilizando divisão e processamento em lotes.

---

## 🏷️ Categorização Financeira

O sistema pode identificar e organizar diferentes tipos de movimentação, incluindo:

- 💳 vendas de cartão;
- ⚡ PIX recebido;
- 🏪 PIX enviado;
- 🏛️ tributos;
- 💸 empréstimos e financiamentos;
- 📦 investimentos;
- 🛡️ seguros;
- 💼 tarifas bancárias;
- fornecedores;
- outras receitas e despesas.

---

## 🔄 Conciliação Bancária

Estrutura para cruzamento de movimentações bancárias com informações de adquirentes.

Pode utilizar informações como:

- NSU;
- valor;
- data;
- adquirente;
- estabelecimento;
- tolerâncias configuráveis.

O objetivo é identificar recebimentos, divergências e diferenças entre venda e liquidação.

---

## 📊 DRE

O NousCard possui visão gerencial de resultado para apoiar a análise financeira da empresa.

A estrutura permite acompanhar receitas e despesas e evoluir para uma visão cada vez mais integrada entre:

```text
Operação → Recebimento → Despesa → Resultado
```

---

# 🎯 Dashboard de Gestão

A nova fase do NousCard combina informações comerciais, operacionais e financeiras.

O Dashboard pode apresentar indicadores como:

### Gestão

- clientes cadastrados;
- orçamentos em aberto;
- orçamentos aprovados;
- ordens de serviço;
- serviços em andamento;
- serviços concluídos.

### Financeiro

- entradas;
- saídas;
- resultado;
- movimentações;
- conciliação;
- DRE.

A navegação principal também foi organizada em duas áreas:

```text
🧭 Gestão
   ├── Dashboard
   ├── Clientes
   ├── Orçamentos
   └── Ordens de Serviço

💰 Financeiro
   ├── Importações
   ├── Arquivos
   ├── Conciliação
   └── DRE
```

---

# 📣 Captação de Leads

O NousCard possui uma landing page pública voltada à apresentação comercial da plataforma.

O visitante pode acessar:

[https://nouscard.com.br](https://nouscard.com.br)

e selecionar **“Quero conhecer o NousCard”**.

O formulário comercial coleta informações como:

- nome;
- empresa;
- WhatsApp;
- e-mail;
- forma atual de controle;
- áreas que deseja organizar;
- mensagem adicional.

Os leads são armazenados no próprio NousCard e ficam disponíveis para acompanhamento pelo usuário Master.

### Funil Comercial

```text
Novo
  ↓
Contato
  ↓
Qualificado
  ↓
Cliente
```

Também é possível classificar oportunidades como perdidas.

---

# 📊 Google Analytics 4

A landing pública possui integração com **Google Analytics 4**.

Measurement ID atualmente configurado:

```text
G-X3KK2D50EG
```

O funil comercial possui eventos próprios:

```text
page_view
cta_quero_conhecer
lead_form_start
lead_submit
lead_success
```

Isso permite acompanhar:

```text
Visitante
   ↓
Clique no CTA
   ↓
Início do formulário
   ↓
Envio
   ↓
Lead confirmado
```

Nenhum dado pessoal como nome, telefone ou e-mail é enviado ao Google Analytics pelos eventos customizados.

---

# 🌍 Internacionalização

A landing pública possui suporte inicial para:

- 🇧🇷 Português;
- 🇬🇧 Inglês.

O idioma pode ser informado pela URL:

```text
https://nouscard.com.br/?lang=pt
```

ou:

```text
https://nouscard.com.br/?lang=en
```

Também existe suporte para identificação de origem comercial:

```text
https://nouscard.com.br/?lang=en&ref=parceiro
```

Isso permite testar o interesse comercial do NousCard em novos mercados antes de internacionalizar toda a aplicação.

A estrutura foi preparada para permitir futuramente novos idiomas.

---

# 🧪 Cliente-Piloto

A evolução do módulo de Gestão está sendo validada através de uma empresa real prestadora de serviços.

O piloto tem como objetivo validar:

- processo de orçamento;
- transformação em ordem de serviço;
- facilidade de utilização;
- informações realmente necessárias;
- integração com financeiro;
- experiência do usuário;
- aderência comercial.

A estratégia é evitar desenvolver funcionalidades excessivamente específicas antes que exista validação através de uso real.

---

# 🧠 Princípio de Produto

O NousCard não deve se transformar em um sistema diferente para cada cliente.

A diretriz é:

> **Configurar quando possível. Customizar somente quando fizer sentido para o produto.**

Novas funcionalidades devem preferencialmente resolver problemas comuns a diversos pequenos negócios.

Exemplos de segmentos potenciais:

- vidraçarias;
- construção e alvenaria;
- manutenção;
- climatização;
- marcenaria;
- pintura;
- instalação;
- assistência técnica;
- profissionais autônomos;
- prestadores de serviços em geral.

---

# 🔒 Multi-Tenancy e Segurança

O NousCard foi desenvolvido como aplicação multiempresa.

Principais recursos:

- isolamento de dados por empresa;
- usuários vinculados a empresas;
- usuário Master;
- administradores;
- usuários operacionais;
- proteção CSRF;
- controle de sessão;
- timeout de sessão;
- cookies seguros em produção;
- Content Security Policy;
- auditoria;
- criptografia de informações sensíveis quando aplicável.

---

# 🏗️ Arquitetura

## Backend

- **Python 3.11+**
- **Flask 2.3+**
- **Flask-SQLAlchemy**
- **SQLAlchemy**
- **Flask-Login**
- **Flask-Migrate**
- **PyMySQL**

---

## Frontend

- HTML5;
- CSS3;
- JavaScript;
- Jinja2;
- design system próprio;
- layout responsivo;
- landing page comercial;
- navegação desktop e mobile.

---

## Banco de Dados

### Produção

```text
MySQL
```

### Desenvolvimento

Pode ser utilizado:

```text
SQLite
```

dependendo da configuração local.

---

## Infraestrutura

### Aplicação

```text
Render
```

### Banco / Serviços associados

```text
HostGator
```

### Domínio

```text
https://nouscard.com.br
```

---

# 📦 Bibliotecas

Entre as bibliotecas utilizadas pelo projeto estão:

```text
Flask
Flask-SQLAlchemy
SQLAlchemy
Flask-Login
Flask-Migrate
PyMySQL
openpyxl
chardet
ofxparse
```

Consulte `requirements.txt` para a relação atualizada.

---

# 🚀 Executando Localmente

## Pré-requisitos

- Python 3.11 ou superior;
- Git;
- MySQL ou ambiente compatível;
- ambiente virtual Python recomendado.

---

## Clonar o projeto

```bash
git clone <URL_DO_REPOSITORIO>
cd nouscard
```

---

## Criar ambiente virtual

### Linux / macOS

```bash
python -m venv venv
source venv/bin/activate
```

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

---

## Instalar dependências

```bash
pip install -r requirements.txt
```

---

## Configuração

Crie o arquivo `.env` ou configure as variáveis de ambiente utilizadas pelo projeto.

Exemplo:

```env
SECRET_KEY=sua_chave_secreta
DATABASE_URL=mysql+pymysql://usuario:senha@host:3306/nouscard
FLASK_ENV=development
```

Nunca envie senhas ou chaves reais para o repositório.

---

## Banco de Dados

Execute as migrations:

```bash
flask db upgrade
```

---

## Executar

```bash
flask --app app run --debug
```

A aplicação estará disponível normalmente em:

```text
http://localhost:5000
```

---

# 📁 Estrutura Geral

Uma visão simplificada do projeto:

```text
nouscard/
│
├── app.py
├── config.py
├── requirements.txt
│
├── models/
│   ├── base.py
│   ├── usuario.py
│   ├── empresa.py
│   ├── cliente.py
│   ├── orçamento...
│   └── ...
│
├── routes/
│   ├── auth_routes.py
│   ├── dashboard_routes.py
│   ├── clientes_routes.py
│   ├── orcamentos_routes.py
│   ├── ordens_servico_routes.py
│   ├── master_routes.py
│   └── ...
│
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard/
│   ├── clientes/
│   ├── orcamentos/
│   ├── ordens_servico/
│   └── master/
│
├── static/
│   ├── css/
│   ├── js/
│   └── img/
│
└── utils/
```

> A estrutura real pode sofrer alterações conforme a evolução do projeto.

---

# 🗺️ Roadmap

## ✅ Implementado

- [x] Multi-tenancy
- [x] Controle de usuários
- [x] Área Master
- [x] Cadastro de empresas
- [x] Cadastro de clientes
- [x] Gestão de orçamentos
- [x] Ordens de Serviço
- [x] Dashboard de Gestão
- [x] Dashboard Financeiro
- [x] Importação OFX
- [x] Importação CSV
- [x] Importação Excel
- [x] Processamento de movimentações
- [x] Categorização financeira
- [x] Conciliação bancária
- [x] DRE
- [x] Landing page comercial
- [x] Captação de leads
- [x] Funil comercial no Master
- [x] Integração GA4
- [x] Eventos de conversão
- [x] Landing PT/EN
- [x] Identificação de origem comercial

---

## 🚧 Em Validação / Evolução

- [ ] Uso real de Orçamentos + OS em empresa-piloto
- [ ] Geração final de orçamento em PDF
- [ ] Compartilhamento de orçamento
- [ ] Conversão completa Orçamento → OS
- [ ] Integração OS → Contas a Receber
- [ ] Evolução do dashboard operacional
- [ ] Registro de idioma e origem diretamente no Lead
- [ ] Validação comercial com primeiros clientes pagantes
- [ ] Validação de mercado internacional

---

## 📋 Próximas Possibilidades

Funcionalidades futuras devem ser priorizadas conforme uso real e validação comercial.

Entre as possibilidades:

- contas a pagar;
- contas a receber;
- fluxo de caixa projetado;
- integração com Open Finance;
- integração contábil;
- automações;
- notificações;
- relatórios PDF;
- relatórios Excel;
- dashboard comercial;
- indicadores de conversão;
- aplicação mobile;
- novos idiomas;
- inteligência artificial aplicada à operação;
- integrações com serviços externos.

---

# 💼 Estratégia Comercial

O NousCard está atualmente em fase de validação de produto e mercado.

A estratégia prevê:

### Pilotos

Empresas selecionadas podem participar da validação utilizando o produto em operação real e fornecendo feedback.

### Clientes comerciais

Após validação, o produto poderá ser disponibilizado através de assinatura mensal.

A estrutura de planos poderá considerar:

```text
NousCard Essencial
Clientes + Orçamentos + Ordens de Serviço

NousCard Gestão
Gestão + Financeiro

NousCard Pro
Gestão + Financeiro + Conciliação + DRE
```

Preços e composição definitiva dos planos devem ser definidos com base na validação comercial.

---

# 🌎 Visão de Futuro

O objetivo do NousCard é se tornar uma plataforma simples e acessível para pequenas empresas que desejam sair de controles fragmentados e passar a tomar decisões com informações organizadas.

A visão é conectar:

```text
Comercial
   +
Operação
   +
Financeiro
   =
Visão do Negócio
```

---

# 👨‍💻 Autor

**Wilson Martins**

Idealizador e Desenvolvedor Principal

**Nous Tecnologia**

🌐 [https://noustecnologia.com.br](https://noustecnologia.com.br)

---

# 📞 Contato

**Nous Tecnologia**

📧 contato@noustecnologia.com.br

🌐 [https://noustecnologia.com.br](https://noustecnologia.com.br)

💳 [https://nouscard.com.br](https://nouscard.com.br)

---

# ⚠️ Licença

A política de licenciamento deste projeto deve ser definida conforme a estratégia comercial da Nous Tecnologia.

> Antes de publicar este repositório como open source, revise cuidadosamente esta seção e o arquivo `LICENSE`.

---

<div align="center">

## 💳 NousCard

**Gestão simples. Operação organizada. Financeiro sob controle.**

Desenvolvido com 💙 pela **Nous Tecnologia**

</div>
