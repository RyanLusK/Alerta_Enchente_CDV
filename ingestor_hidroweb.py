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

ESTACOES_MONTANTE = [566960000]
ANOS_PARA_BAIXAR = [2026]

#ESTACAO_TIMOTEO = "56696000"
#ESTACAO_BARRAGEM = "56688080"
#ESTACAO_NOVA_ERA = "56661000"

def extrair_valor(tag, elemento):
    """Busca o valor no XML da ANA. Se não existir ou for nulo, retorna None."""
    node = tag.find(elemento)
    if node is not None and node.text:
        try:
            return float(node.text)
        except ValueError:
            return None
    return None

def buscar_ano_hidroweb(codigo_estacao, ano):
    """Faz a requisição para o webservice da ANA para uma estação e ano específicos."""
    print(f"\nBaixando -> Estação: {codigo_estacao} | Ano: {ano}...")
    
    url = "http://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos"
    parametros = {
        "codEstacao": codigo_estacao,
        "dataInicio": f"01/01/{ano}",
        "dataFim": f"31/12/{ano}",
    }
    
    resposta = requests.get(url, params=parametros)
    
    if resposta.status_code != 200:
        print(f"Erro na API da ANA: {resposta.status_code}")
        return []

    root = ET.fromstring(resposta.content)
    dados = []
    
    for dado in root.findall(".//DadosHidrometereologicos"):
        data_hora_str = dado.find('DataHora').text if dado.find('DataHora') is not None else None
        
        if data_hora_str:
            # Mantendo o .strip() para limpar os espaços em branco que a ANA manda por engano
            dt = datetime.strptime(data_hora_str.strip(), "%Y-%m-%d %H:%M:%S")
            
            registro = {
                "codigo_ana": codigo_estacao,
                "data_hora": dt.isoformat(),
                "nivel_cm": extrair_valor(dado, 'Nivel'),
                "chuva_mm": extrair_valor(dado, 'Chuva'),
                "vazao_m3s": extrair_valor(dado, 'Vazao')
            }
            dados.append(registro)
            
    print(f"{len(dados)} leituras encontradas.")
    return dados

def salvar_no_supabase(dados):
    """Envia os dados em lotes para evitar sobrecarga no banco."""
    if not dados: return
    
    tamanho_lote = 1000
    total_inserido = 0
    
    for i in range(0, len(dados), tamanho_lote):
        lote = dados[i : i + tamanho_lote]
        try:
            supabase.table("historico_ana").upsert(lote).execute()
            total_inserido += len(lote)
            print(f"   -> Nuvem atualizada: {total_inserido}/{len(dados)} registros...")
        except Exception as e:
            print(f"Erro ao salvar lote: {e}")

def iniciar_ingestao():
    for estacao in ESTACOES_MONTANTE:
        print(f"\n=========================================")
        print(f"INICIANDO EXTRAÇÃO DA ESTAÇÃO {estacao}")
        print(f"=========================================")
        for ano in ANOS_PARA_BAIXAR:
            leituras_ano = buscar_ano_hidroweb(estacao, ano)
            salvar_no_supabase(leituras_ano)
            
    print("\nDOWNLOAD MASSIVO CONCLUÍDO COM SUCESSO!")

if __name__ == "__main__":
    iniciar_ingestao()