import asyncio
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from supabase import create_client, Client
from gerador_imagens import gerar_todas_imagens
from android_bot import enviar_carrossel_android

# ==========================================
# CONFIGURAÇÕES INICIAIS
# ==========================================
caminho_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(caminho_env)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(f"Chaves do Supabase não encontradas. Verifique se o arquivo existe em: {caminho_env}")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ANA_API_URL = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos"
ESTACAO_TIMOTEO = "56696000"

# ==========================================
# MÓDULO DE GOVERNANÇA (Ler Supabase)
# ==========================================
def obter_configuracao_sistema() -> dict:
    """Busca o estado das chaves operacionais no Supabase."""
    try:
        response = supabase.table("sistema_config").select("*").eq("id", 1).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        logging.error(f"Erro ao ler configurações do sistema: {e}")
    
    # Se falhar a comunicação, retorna um fallback seguro (tudo normal, sem testes)
    return {
        "modo_teste": False,
        "cenario_teste": "estavel",
        "kill_switch_ig": False,
        "forcar_postagem": False
    }

def desativar_gatilho_postagem():
    """Volta a chave 'forcar_postagem' para False após o disparo manual."""
    try:
        supabase.table("sistema_config").update({"forcar_postagem": False}).eq("id", 1).execute()
        logging.info("Gatilho manual resetado no banco de dados.")
    except Exception as e:
        logging.error(f"Erro ao resetar gatilho de postagem: {e}")

# ==========================================
# MÓDULO 1: INGESTÃO E SIMULAÇÃO
# ==========================================
def gerar_cenario_teste(cenario: str, codigo_estacao: str) -> list:
    agora = datetime.now()
    leituras = []
    
    if cenario == "emergencia":
        nivel_base, salto = 780.0, 7.5
    elif cenario == "atencao":
        nivel_base, salto = 610.0, 3.0
    elif cenario == "vazante":
        nivel_base, salto = 650.0, -5.0
    else: 
        nivel_base, salto = 200.0, 0.5

    for i in range(5):
        leituras.append({
            "estacao_id": codigo_estacao,
            "data_hora": (agora - timedelta(minutes=15*i)).isoformat(),
            "nivel_cm": nivel_base - (salto * i),
            "vazao_m3s": 1200.0 - (50 * i)
        })
        
    logging.info(f"MODO TESTE ATIVADO: Injetando cenário de {cenario.upper()}")
    return leituras

@retry(
    stop=stop_after_attempt(5), 
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
)
async def buscar_dados_xml_async(client: httpx.AsyncClient, codigo_estacao: str) -> list:
    ontem = datetime.now() - timedelta(days=1)
    hoje = datetime.now()
    
    params = {
        "codEstacao": codigo_estacao,
        "dataInicio": ontem.strftime("%d/%m/%Y"),
        "dataFim": hoje.strftime("%d/%m/%Y")
    }
    
    response = await client.get(ANA_API_URL, params=params, timeout=30.0)
    response.raise_for_status()
    
    root = ET.fromstring(response.content)
    leituras = []
    
    for dado in root.iter("DadosHidrometereologicos"):
        nivel, vazao, data_hora = dado.find("Nivel"), dado.find("Vazao"), dado.find("DataHora")
        if data_hora is not None and data_hora.text:
            try:
                dt = datetime.strptime(data_hora.text.strip(), "%Y-%m-%d %H:%M:%S")
                leituras.append({
                    "estacao_id": codigo_estacao,
                    "data_hora": dt.isoformat(),
                    "nivel_cm": float(nivel.text) if (nivel is not None and nivel.text) else 0.0,
                    "vazao_m3s": float(vazao.text) if (vazao is not None and vazao.text) else 0.0
                })
            except ValueError: continue
                
    leituras.sort(key=lambda x: x['data_hora'], reverse=True)
    return leituras

def salvar_no_supabase(leitura: dict):
    try:
        supabase.table("leituras_rio").upsert(
            leitura, on_conflict="codigo_ana, data_hora"
        ).execute()
        logging.info(f"Salvo/Atualizado no DB: {leitura['nivel_cm']}cm às {leitura['data_hora']}")
    except Exception as e:
        logging.error(f"Erro ao salvar no Supabase: {e}")

# ==========================================
# MÓDULO 2: MOTOR PREDITIVO E ANÁLISE
# ==========================================
def calcular_velocidade_suavizada(leituras_supabase: list) -> dict:
    if len(leituras_supabase) < 2: return {"velocidade": 0.0, "tendencia": "ESTÁVEL"}

    leituras_validas = []
    for i in range(len(leituras_supabase) - 1):
        atual, anterior = leituras_supabase[i]['nivel_cm'], leituras_supabase[i+1]['nivel_cm']
        if abs(atual - anterior) > 50: continue
        leituras_validas.append(leituras_supabase[i])
    
    if leituras_supabase: leituras_validas.append(leituras_supabase[-1])
    if len(leituras_validas) < 2: return {"velocidade": 0.0, "tendencia": "ESTÁVEL"}

    recente, antiga = leituras_validas[0], leituras_validas[-1] 
    t1 = datetime.fromisoformat(recente['data_hora'].replace("Z", "+00:00"))
    t0 = datetime.fromisoformat(antiga['data_hora'].replace("Z", "+00:00"))
    
    delta_t_horas = (t1 - t0).total_seconds() / 3600.0
    if delta_t_horas <= 0.16: return {"velocidade": 0.0, "tendencia": "ESTÁVEL"}

    velocidade_cm_h = (recente['nivel_cm'] - antiga['nivel_cm']) / delta_t_horas
    tendencia = "SUBINDO" if velocidade_cm_h > 2.0 else "BAIXANDO" if velocidade_cm_h < -2.0 else "ESTÁVEL"
    
    return {"velocidade": round(velocidade_cm_h, 1), "tendencia": tendencia}

def calcular_ocupacao_calha(nivel_atual: float, ruas_banco: list) -> list:
    relatorio = []
    for rua in ruas_banco:
        pct = (nivel_atual / rua['nivel_critico_cm']) * 100
        relatorio.append({
            "nome": rua['nome'],
            "ocupacao_pct": round(pct, 1),
            "critico": pct >= 100.0
        })
    return sorted(relatorio, key=lambda x: x['ocupacao_pct'], reverse=True)

# ==========================================
# ORQUESTRAÇÃO PRINCIPAL
# ==========================================
async def ciclo_principal():
    logging.info("--- Iniciando Ciclo de Varredura ---")
    
    # 1. Lê a "Mesa de Som" do Supabase
    config = obter_configuracao_sistema()
    
    # 2. Roteamento de Dados (Real vs Simulado)
    if config['modo_teste']:
        leituras_recentes = gerar_cenario_teste(config['cenario_teste'], ESTACAO_TIMOTEO)
    else:
        async with httpx.AsyncClient() as client:
            leituras = await buscar_dados_xml_async(client, ESTACAO_TIMOTEO)
        
        if not leituras:
            logging.error("Nenhuma leitura retornada pela ANA.")
            return
            
        leituras_recentes = leituras[:5]
        
        for leitura in leituras_recentes:
            salvar_no_supabase({
                "codigo_ana": leitura["estacao_id"],
                "nivel_cm": leitura["nivel_cm"],
                "vazao_m3s": leitura["vazao_m3s"],
                "data_hora": leitura["data_hora"]
            })
        
    nivel_atual = leituras_recentes[0]["nivel_cm"]
    
    # 3. Motor Preditivo
    analise = calcular_velocidade_suavizada(leituras_recentes)
    
    # 4. Cálculo de Impacto por Rua
    ruas_response = supabase.table("ruas_monitoradas").select("*").execute()
    relatorio_ruas = calcular_ocupacao_calha(nivel_atual, ruas_response.data)
    
    # 5. Painel de Log Visual
    print("\n" + "="*40)
    print(f" RESULTADO DO CICLO {'[MODO TESTE]' if config['modo_teste'] else '[PRODUÇÃO]'}")
    print("="*40)
    print(f" Nível Atual (Timóteo): {nivel_atual} cm")
    print(f" Tendência: {analise['tendencia']} ({analise['velocidade']} cm/h)")
    print("\n️  STATUS OPERACIONAL:")
    print(f" - Trava do Instagram (Kill Switch): {' ATIVADA (Bloqueado)' if config['kill_switch_ig'] else ' Liberado'}")
    print(f" - Gatilho Manual: {'️ DISPARADO' if config['forcar_postagem'] else 'Aguardando'}")
    print("\n️ IMPACTO NAS RUAS:")
    for rua in relatorio_ruas[:4]: # Mostra só as 4 piores no log pra não poluir
        alerta = "️ CRÍTICO!" if rua['critico'] else "Ok"
        print(f" - {rua['nome']}: {rua['ocupacao_pct']}% [{alerta}]")
    print("="*40 + "\n")

    # 6. Lógica de Disparo (Instagram)
    if config['forcar_postagem']:
        logging.info("GATILHO MANUAL DETECTADO! Preparando imagens...")
        
        # Gera as imagens usando seus assets
        caminhos_imagens = gerar_todas_imagens(
            nivel_atual=nivel_atual,
            tendencia=analise['tendencia'],
            velocidade=analise['velocidade'],
            leituras=leituras_recentes,
            ruas=relatorio_ruas
        )
        
        logging.info(f"Imagens geradas com sucesso: {caminhos_imagens}")
        
        if not config['kill_switch_ig']:
            # Envia pro celular via ADB!
            await enviar_carrossel_android(caminhos_imagens, deve_limpar=True)
        else:
            logging.info("Kill Switch ativo. As imagens foram geradas mas NÃO foram postadas.")
            
        desativar_gatilho_postagem()

if __name__ == "__main__":
    asyncio.run(ciclo_principal())