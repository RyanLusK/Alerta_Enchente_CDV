import asyncio
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from supabase import create_client, Client

# ==========================================
# CONFIGURAÇÕES INICIAIS
# Força o .env carregar no mesmo diretório
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


# MÓDULO 1: INGESTÃO

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
    
    logging.info(f"Buscando XML da estação {codigo_estacao}...")
    response = await client.get(ANA_API_URL, params=params, timeout=30.0)
    response.raise_for_status()
    
    # Parse do XML
    root = ET.fromstring(response.content)
    leituras = []
    
    for dado in root.iter("DadosHidrometereologicos"):
        nivel = dado.find("Nivel")
        vazao = dado.find("Vazao")
        data_hora = dado.find("DataHora")
        
        if data_hora is not None and data_hora.text:
            try:
                dt = datetime.strptime(data_hora.text.strip(), "%Y-%m-%d %H:%M:%S")
                val_nivel = float(nivel.text) if (nivel is not None and nivel.text) else 0.0
                val_vazao = float(vazao.text) if (vazao is not None and vazao.text) else 0.0
                
                leituras.append({
                    "estacao_id": codigo_estacao,
                    "data_hora": dt.isoformat(),
                    "nivel_cm": val_nivel,
                    "vazao_m3s": val_vazao
                })
            except ValueError:
                continue
                
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


# MÓDULO 2: MOTOR PREDITIVO E ANÁLISE

def calcular_velocidade_suavizada(leituras_supabase: list) -> dict:
    if len(leituras_supabase) < 2:
        return {"velocidade": 0.0, "tendencia": "ESTÁVEL"}

    leituras_validas = []
    for i in range(len(leituras_supabase) - 1):
        atual = leituras_supabase[i]['nivel_cm']
        anterior = leituras_supabase[i+1]['nivel_cm']
        
        if abs(atual - anterior) > 50:
            continue
        leituras_validas.append(leituras_supabase[i])
    
    if leituras_supabase:
         leituras_validas.append(leituras_supabase[-1])

    if len(leituras_validas) < 2:
         return {"velocidade": 0.0, "tendencia": "ESTÁVEL"}

    recente = leituras_validas[0]
    antiga = leituras_validas[-1] 
    
    t1 = datetime.fromisoformat(recente['data_hora'].replace("Z", "+00:00"))
    t0 = datetime.fromisoformat(antiga['data_hora'].replace("Z", "+00:00"))
    
    delta_t_horas = (t1 - t0).total_seconds() / 3600.0

    if delta_t_horas <= 0.16: 
        return {"velocidade": 0.0, "tendencia": "ESTÁVEL"}

    velocidade_cm_h = (recente['nivel_cm'] - antiga['nivel_cm']) / delta_t_horas

    tendencia = "ESTÁVEL"
    if velocidade_cm_h > 2.0: tendencia = "SUBINDO"
    elif velocidade_cm_h < -2.0: tendencia = "BAIXANDO"

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

def gerar_cenario_teste(cenario: str, codigo_estacao: str) -> list:
    """
    Gera uma lista de 5 leituras (1 hora) simulando diferentes comportamentos do rio.
    """
    agora = datetime.now()
    leituras = []
    
    # Define a cota base e a velocidade de variação por leitura (15 min)
    if cenario == "emergencia":
        nivel_base = 780.0  # Já transbordando
        salto = 7.5         # Sobe 30cm por hora
    elif cenario == "atencao":
        nivel_base = 610.0  # Acima da cota de alerta
        salto = 3.0         # Sobe 12cm por hora
    elif cenario == "vazante":
        nivel_base = 650.0  # Rio alto, mas baixando
        salto = -5.0        # Desce 20cm por hora
    else: # estavel
        nivel_base = 200.0  # Nível normal
        salto = 0.5         # Variação mínima

    # Cria as leituras de trás pra frente (da mais recente para a mais antiga)
    for i in range(5):
        leituras.append({
            "estacao_id": codigo_estacao,
            "data_hora": (agora - timedelta(minutes=15*i)).isoformat(),
            "nivel_cm": nivel_base - (salto * i),
            "vazao_m3s": 1200.0 - (50 * i) # Vazão genérica acompanhando
        })
        
    logging.info(f"MODO TESTE ATIVADO: Injetando cenário de {cenario.upper()}")
    return leituras

# ORQUESTRAÇÃO DE TESTE

async def teste_integrado():
    logging.info("--- Iniciando Ciclo ---")
    
    # 1. Verifica se estamos em teste
    IS_TESTE = os.getenv("MODO_TESTE", "False").lower() in ("true", "1", "t")
    CENARIO = os.getenv("CENARIO_TESTE", "estavel")
    
    if IS_TESTE:
        leituras_recentes = gerar_cenario_teste(CENARIO, ESTACAO_TIMOTEO)
    else:
        # Busca dados REAIS da ANA
        async with httpx.AsyncClient() as client:
            leituras = await buscar_dados_xml_async(client, ESTACAO_TIMOTEO)
        
        if not leituras:
            logging.error("Nenhuma leitura retornada pela ANA.")
            return
            
        leituras_recentes = leituras[:5]
        
        # SALVA NO SUPABASE APENAS SE NÃO FOR TESTE
        for leitura in leituras_recentes:
            dado_insercao = {
                "codigo_ana": leitura["estacao_id"],
                "nivel_cm": leitura["nivel_cm"],
                "vazao_m3s": leitura["vazao_m3s"],
                "data_hora": leitura["data_hora"]
            }
            salvar_no_supabase(dado_insercao)
        
    nivel_atual = leituras_recentes[0]["nivel_cm"]
    
    # 3. Executa Motor Preditivo (Funciona igual para Real e Teste!)
    analise = calcular_velocidade_suavizada(leituras_recentes)
    
    # 4. Busca ruas no Supabase e Calcula Ocupação
    ruas_response = supabase.table("ruas_monitoradas").select("*").execute()
    relatorio_ruas = calcular_ocupacao_calha(nivel_atual, ruas_response.data)
    
    # 5. Exibe os resultados
    print("\n" + "="*40)
    print(f"📊 RESULTADO DO CICLO {'[MODO TESTE]' if IS_TESTE else ''}")
    print("="*40)
    print(f"🌊 Nível Atual (Timóteo): {nivel_atual} cm")
    print(f"📈 Tendência: {analise['tendencia']} ({analise['velocidade']} cm/h)")
    print("\n🏘️ IMPACTO NAS RUAS:")
    for rua in relatorio_ruas:
        alerta = "⚠️ CRÍTICO!" if rua['critico'] else "Ok"
        print(f" - {rua['nome']}: {rua['ocupacao_pct']}% [{alerta}]")
    print("="*40 + "\n")

if __name__ == "__main__":
    asyncio.run(teste_integrado())