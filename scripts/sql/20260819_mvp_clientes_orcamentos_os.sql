-- NousCard Gestão - MVP Clientes, Orçamentos e Ordens de Serviço
-- MySQL 8+ / MariaDB compatível. Execute primeiro em homologação/backup.

CREATE TABLE IF NOT EXISTS clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    nome VARCHAR(180) NOT NULL,
    tipo_pessoa VARCHAR(2) NOT NULL DEFAULT 'PF',
    documento VARCHAR(20) NULL,
    telefone VARCHAR(30) NULL,
    email VARCHAR(150) NULL,
    endereco VARCHAR(255) NULL,
    cidade VARCHAR(100) NULL,
    uf VARCHAR(2) NULL,
    observacoes TEXT NULL,
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    INDEX idx_clientes_empresa_id (empresa_id),
    INDEX idx_cliente_empresa_nome (empresa_id, nome),
    INDEX idx_cliente_empresa_documento (empresa_id, documento),
    CONSTRAINT fk_clientes_empresa FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orcamentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    cliente_id INT NOT NULL,
    numero INT NOT NULL,
    data_emissao DATE NOT NULL,
    validade_ate DATE NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'RASCUNHO',
    subtotal DECIMAL(14,2) NOT NULL DEFAULT 0,
    desconto DECIMAL(14,2) NOT NULL DEFAULT 0,
    total DECIMAL(14,2) NOT NULL DEFAULT 0,
    condicoes_pagamento TEXT NULL,
    prazo_estimado VARCHAR(160) NULL,
    observacoes_cliente TEXT NULL,
    observacoes_internas TEXT NULL,
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE KEY uq_orcamento_empresa_numero (empresa_id, numero),
    INDEX idx_orcamento_empresa_status (empresa_id, status),
    INDEX idx_orcamento_empresa_data (empresa_id, data_emissao),
    INDEX idx_orcamentos_cliente_id (cliente_id),
    CONSTRAINT fk_orcamentos_empresa FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    CONSTRAINT fk_orcamentos_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orcamento_itens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    orcamento_id INT NOT NULL,
    descricao VARCHAR(220) NOT NULL,
    detalhamento TEXT NULL,
    quantidade DECIMAL(12,3) NOT NULL DEFAULT 1,
    valor_unitario DECIMAL(14,2) NOT NULL DEFAULT 0,
    valor_total DECIMAL(14,2) NOT NULL DEFAULT 0,
    medidas VARCHAR(255) NULL,
    informacoes_tecnicas TEXT NULL,
    custo_material DECIMAL(14,2) NOT NULL DEFAULT 0,
    custo_instalacao DECIMAL(14,2) NOT NULL DEFAULT 0,
    outros_custos DECIMAL(14,2) NOT NULL DEFAULT 0,
    imagem_base64 LONGTEXT NULL,
    ordem INT NOT NULL DEFAULT 0,
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    INDEX idx_orcamento_itens_orcamento_id (orcamento_id),
    CONSTRAINT fk_orcamento_itens_orcamento FOREIGN KEY (orcamento_id) REFERENCES orcamentos(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orcamento_anexos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    orcamento_id INT NOT NULL,
    item_id INT NULL,
    nome_arquivo VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NULL,
    arquivo_base64 LONGTEXT NOT NULL,
    descricao VARCHAR(255) NULL,
    visivel_cliente BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    INDEX idx_orcamento_anexos_orcamento_id (orcamento_id),
    INDEX idx_orcamento_anexos_item_id (item_id),
    CONSTRAINT fk_orcamento_anexos_orcamento FOREIGN KEY (orcamento_id) REFERENCES orcamentos(id) ON DELETE CASCADE,
    CONSTRAINT fk_orcamento_anexos_item FOREIGN KEY (item_id) REFERENCES orcamento_itens(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ordens_servico (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,
    orcamento_id INT NOT NULL,
    cliente_id INT NOT NULL,
    numero INT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'AGUARDANDO_MATERIAL',
    endereco_execucao VARCHAR(255) NULL,
    data_prevista DATE NULL,
    responsavel VARCHAR(150) NULL,
    descricao_execucao TEXT NULL,
    informacoes_tecnicas TEXT NULL,
    observacoes TEXT NULL,
    criado_em DATETIME NOT NULL,
    atualizado_em DATETIME NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE KEY uq_os_empresa_numero (empresa_id, numero),
    UNIQUE KEY uq_os_orcamento (orcamento_id),
    INDEX idx_os_empresa_status (empresa_id, status),
    INDEX idx_os_cliente_id (cliente_id),
    CONSTRAINT fk_os_empresa FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    CONSTRAINT fk_os_orcamento FOREIGN KEY (orcamento_id) REFERENCES orcamentos(id) ON DELETE RESTRICT,
    CONSTRAINT fk_os_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
