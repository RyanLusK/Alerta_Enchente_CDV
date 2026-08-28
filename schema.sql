-- ==============================================================================
-- 1. TABELAS DIMENSÃO (Cadastros)
-- ==============================================================================

-- Cadastro das Estações Hidrológicas
-- Usar o codigo_ana como Primary Key facilita o pipeline de ingestão (não exige JOIN prévio)
CREATE TABLE estacoes (
    codigo_ana VARCHAR(20) PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    cidade VARCHAR(100) NOT NULL,
    cota_atencao_cm INT NOT NULL,
    cota_alerta_cm INT NOT NULL,
    cota_inundacao_cm INT NOT NULL,
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- Cadastro das Ruas e Cotas Críticas
CREATE TABLE ruas_monitoradas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    bairro VARCHAR(100) NOT NULL,
    nivel_critico_cm INT NOT NULL, -- Nível do rio em que a rua alaga
    criado_em TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- ==============================================================================
-- 2. TABELAS FATO (Séries Temporais e Eventos)
-- ==============================================================================

-- Série Temporal de Leituras Telemétricas
CREATE TABLE leituras_rio (
    id BIGSERIAL PRIMARY KEY,
    codigo_ana VARCHAR(20) REFERENCES estacoes(codigo_ana) ON DELETE CASCADE,
    nivel_cm NUMERIC(6, 2) NOT NULL,
    vazao_m3s NUMERIC(8, 2) DEFAULT 0.0,
    chuva_mm NUMERIC(5, 2) DEFAULT 0.0,
    data_hora TIMESTAMP WITH TIME ZONE NOT NULL,
    capturado_em TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    
    -- A CONSTRAINT ABAIXO É O CORAÇÃO DO SEU UPSERT NO PYTHON:
    -- Ela impede que a mesma leitura da ANA seja salva duas vezes.
    CONSTRAINT idx_leitura_unica UNIQUE(codigo_ana, data_hora)
);

-- Índices de performance para acelerar o Dashboard Web e os cálculos de velocidade
CREATE INDEX idx_leituras_estacao ON leituras_rio (codigo_ana);
CREATE INDEX idx_leituras_data_desc ON leituras_rio (data_hora DESC);


-- Mensageria do Chat Comunitário (Preparado para o WebSockets/Realtime)
CREATE TABLE mensagens_chat (
    id BIGSERIAL PRIMARY KEY,
    usuario_id UUID NOT NULL, -- Link com a tabela auth.users do Supabase
    nome_usuario VARCHAR(100) NOT NULL,
    rua_id INT REFERENCES ruas_monitoradas(id) ON DELETE SET NULL,
    conteudo TEXT NOT NULL,
    enviado_em TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);

-- ==============================================================================
-- 3. GOVERNANÇA E SEGURANÇA (Row Level Security - RLS)
-- ==============================================================================

-- Habilitar RLS em todas as tabelas
ALTER TABLE estacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE ruas_monitoradas ENABLE ROW LEVEL SECURITY;
ALTER TABLE leituras_rio ENABLE ROW LEVEL SECURITY;
ALTER TABLE mensagens_chat ENABLE ROW LEVEL SECURITY;

-- 3.1 Políticas de Leitura (O Dashboard Web pode ler tudo)
CREATE POLICY "Leitura pública permitida para estacoes" ON estacoes FOR SELECT USING (true);
CREATE POLICY "Leitura pública permitida para ruas" ON ruas_monitoradas FOR SELECT USING (true);
CREATE POLICY "Leitura pública permitida para leituras" ON leituras_rio FOR SELECT USING (true);
CREATE POLICY "Leitura pública permitida para chat" ON mensagens_chat FOR SELECT USING (true);

-- 3.2 Políticas de Escrita Segura
-- (O backend Python usa a SUPABASE_SERVICE_ROLE_KEY, que bypassa o RLS nativamente,
-- então não precisamos criar política de INSERT para as leituras. 
-- Mas para o CHAT, precisamos permitir que usuários autenticados postem mensagens).

CREATE POLICY "Usuários logados podem enviar mensagens" 
ON mensagens_chat 
FOR INSERT 
WITH CHECK (auth.uid() = usuario_id);