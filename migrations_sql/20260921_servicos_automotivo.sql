-- NousCard v0.3 - Serviços / Automotivo
-- Faça backup do banco antes de executar.

CREATE TABLE IF NOT EXISTS veiculos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  empresa_id INT NOT NULL,
  cliente_id INT NOT NULL,
  placa VARCHAR(10) NOT NULL,
  marca VARCHAR(80), modelo VARCHAR(100) NOT NULL, ano VARCHAR(10), cor VARCHAR(50),
  quilometragem INT, chassi VARCHAR(30), seguradora VARCHAR(120), observacoes TEXT,
  criado_em DATETIME NOT NULL, atualizado_em DATETIME NULL, ativo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT fk_veiculo_empresa FOREIGN KEY (empresa_id) REFERENCES empresas(id),
  CONSTRAINT fk_veiculo_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,
  CONSTRAINT uq_veiculo_empresa_placa UNIQUE (empresa_id, placa),
  INDEX idx_veiculo_empresa_cliente (empresa_id, cliente_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE orcamentos ADD COLUMN veiculo_id INT NULL;
ALTER TABLE orcamentos ADD COLUMN public_token VARCHAR(96) NULL;
ALTER TABLE orcamentos ADD CONSTRAINT fk_orcamento_veiculo FOREIGN KEY (veiculo_id) REFERENCES veiculos(id) ON DELETE SET NULL;
CREATE INDEX idx_orcamento_veiculo ON orcamentos(veiculo_id);
CREATE UNIQUE INDEX uq_orcamento_public_token ON orcamentos(public_token);

CREATE TABLE IF NOT EXISTS orcamento_interacoes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  empresa_id INT NOT NULL, orcamento_id INT NOT NULL,
  acao VARCHAR(30) NOT NULL, nome_cliente VARCHAR(150), mensagem TEXT,
  ip_origem VARCHAR(64), user_agent VARCHAR(500),
  criado_em DATETIME NOT NULL, atualizado_em DATETIME NULL, ativo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT fk_interacao_empresa FOREIGN KEY (empresa_id) REFERENCES empresas(id),
  CONSTRAINT fk_interacao_orcamento FOREIGN KEY (orcamento_id) REFERENCES orcamentos(id) ON DELETE CASCADE,
  INDEX idx_interacao_orcamento (orcamento_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE ordens_servico ADD COLUMN valor_recebido DECIMAL(14,2) NOT NULL DEFAULT 0;
ALTER TABLE ordens_servico ADD COLUMN taxa_pagamento DECIMAL(14,2) NOT NULL DEFAULT 0;
ALTER TABLE ordens_servico ADD COLUMN forma_pagamento VARCHAR(30) NULL;

CREATE TABLE IF NOT EXISTS ordem_servico_custos (
  id INT AUTO_INCREMENT PRIMARY KEY,
  empresa_id INT NOT NULL, ordem_servico_id INT NOT NULL,
  tipo VARCHAR(30) NOT NULL DEFAULT 'OUTRO', descricao VARCHAR(220) NOT NULL,
  fornecedor VARCHAR(160), valor DECIMAL(14,2) NOT NULL DEFAULT 0, data_custo DATE, observacoes TEXT,
  criado_em DATETIME NOT NULL, atualizado_em DATETIME NULL, ativo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT fk_custo_empresa FOREIGN KEY (empresa_id) REFERENCES empresas(id),
  CONSTRAINT fk_custo_os FOREIGN KEY (ordem_servico_id) REFERENCES ordens_servico(id) ON DELETE CASCADE,
  INDEX idx_custo_os (ordem_servico_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
