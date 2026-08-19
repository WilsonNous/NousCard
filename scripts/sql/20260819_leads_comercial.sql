-- ============================================================
-- NousCard • Evolução comercial da tabela leads
-- 2026-08-19
-- MySQL
--
-- FAÇA BACKUP ANTES DE EXECUTAR.
-- ============================================================

-- Tornar CNPJ e e-mail opcionais e ampliar telefone.
ALTER TABLE leads
    MODIFY COLUMN cnpj VARCHAR(20) NULL,
    MODIFY COLUMN email VARCHAR(200) NULL,
    MODIFY COLUMN telefone VARCHAR(30) NOT NULL;

-- Novos dados de descoberta comercial.
ALTER TABLE leads
    ADD COLUMN controle_atual VARCHAR(30) NULL AFTER telefone,
    ADD COLUMN interesses VARCHAR(255) NULL AFTER controle_atual;

-- Índices adicionais.
-- Se algum índice já existir no seu banco, ignore apenas o erro
-- referente àquele CREATE INDEX específico.
CREATE INDEX idx_lead_telefone
    ON leads (telefone);

CREATE INDEX idx_lead_status_data
    ON leads (status, criado_em);

CREATE INDEX idx_lead_origem_data
    ON leads (origem, criado_em);
