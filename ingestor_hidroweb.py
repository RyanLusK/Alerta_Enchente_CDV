import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# CONFIGURAÇÕES DO BANCO E DA API
# ==========================================
SUPABASE_URL = "https://bybvlorarvxnnyggdsgf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ5YnZsb3JhcnZ4bm55Z2dkc2dmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzY4OTQ1MCwiZXhwIjoyMTAzMjY1NDUwfQ.WjsNPUXosNNAOFpMN0j8a9IsH8Lu31Oo8b3RDiD_IAA" # Use a service_role para ignorar RLS no backend
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CODIGO_ESTACAO = "56696000" # Mário de Carvalho
ANOS_PARA_BAIXAR = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

def extrair_valor(tag, elemento):
    """Busca o valor no XML da ANA. Se não existir ou for nulo, retorna None."""
    node = tag.find(elemento)
    if node is not None and node.text:
        try:
            return float(node.text)
        except ValueError:
            return None
    return None

def buscar_ano_hidroweb(ano):
    """Faz a requisição para o webservice da ANA para um ano específico."""
    print(f"\n📡 Conectando ao HidroWeb (ANA) para o ano de {ano}...")
    
    url = "http://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos"
    parametros = {
        "codEstacao": CODIGO_ESTACAO,
        "dataInicio": f"01/01/{ano}",
        "dataFim": f"31/12/{ano}",
    }
    
    resposta = requests.get(url, params=parametros)
    
    if resposta.status_code != 200:
        print(f"❌ Erro na API da ANA: {resposta.status_code}")
        return []

    # O retorno da ANA é em formato XML. Vamos converter para dicionários Python.
    root = ET.fromstring(resposta.content)
    dados = []
    
    # Navega pelas tags do XML retornado
    for dado in root.findall(".//DadosHidrometereologicos"):
        data_hora_str = dado.find('DataHora').text if dado.find('DataHora') is not None else None
        
        if data_hora_str:
            # Converte a data da ANA para o padrão do Banco de Dados (ISO)
            dt = datetime.strptime(data_hora_str.strip(), "%Y-%m-%d %H:%M:%S")
            
            registro = {
                "codigo_ana": CODIGO_ESTACAO,
                "data_hora": dt.isoformat(),
                "nivel_cm": extrair_valor(dado, 'Nivel'),
                "chuva_mm": extrair_valor(dado, 'Chuva'),
                "vazao_m3s": extrair_valor(dado, 'Vazao')
            }
            dados.append(registro)
            
    print(f"✅ {len(dados)} leituras encontradas para {ano}.")
    return dados

def salvar_no_supabase(dados):
    """Envia os dados em lotes para evitar sobrecarga no banco."""
    if not dados: return
    
    tamanho_lote = 1000
    total_inserido = 0
    
    print("💾 Iniciando inserção no Supabase...")
    for i in range(0, len(dados), tamanho_lote):
        lote = dados[i : i + tamanho_lote]
        try:
            # Usamos 'upsert' para que, se o script rodar duas vezes, não duplique dados
            supabase.table("historico_ana").upsert(lote).execute()
            total_inserido += len(lote)
            print(f"   -> Salvos {total_inserido}/{len(dados)} registros...")
        except Exception as e:
            print(f"❌ Erro ao salvar lote: {e}")
            
    print("🚀 Inserção concluída!")

def iniciar_ingestao():
    for ano in ANOS_PARA_BAIXAR:
        leituras_ano = buscar_ano_hidroweb(ano)
        salvar_no_supabase(leituras_ano)

if __name__ == "__main__":
    print("🌊 INICIANDO EXTRATOR DE DADOS HISTÓRICOS SAD 🌊")
    iniciar_ingestao()