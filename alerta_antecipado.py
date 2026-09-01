import requests
from datetime import datetime
from supabase import create_client, Client

# Configurações do Supabase
SUPABASE_URL = "https://bybvlorarvxnnyggdsgf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ5YnZsb3JhcnZ4bm55Z2dkc2dmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzY4OTQ1MCwiZXhwIjoyMTAzMjY1NDUwfQ.WjsNPUXosNNAOFpMN0j8a9IsH8Lu31Oo8b3RDiD_IAA"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Constantes do Modelo
ESTACAO_MONTANTE = "56661000"  # Nova Era
TEMPO_PROPAGACAO_HORAS = 28    # O lag que descobrimos na correlação cruzada
COTA_ALERTA_MONTANTE = 400     # Exemplo: Se Nova Era subir de 400cm, acende o alerta

def verificar_estado_bacia():
    print(consultando := f" Verificando os sensores a montante (Estação {ESTACAO_MONTANTE})...")
    
    # Busca a medição mais recente da estação de Nova Era no Supabase
    resposta = supabase.table("historico_ana")\
        .select("data_hora, nivel_cm, chuva_mm")\
        .eq("codigo_ana", ESTACAO_MONTANTE)\
        .order("data_hora", desc=True)\
        .limit(1)\
        .execute()
    
    if not resposta.data:
        print(" Nenhum dado encontrado.")
        return

    ultimo_dado = resposta.data[0]
    nivel_atual = ultimo_dado['nivel_cm']
    data_hora = ultimo_dado['data_hora']
    
    print(f" Última leitura em {data_hora}: Nível em Nova Era = {nivel_atual} cm")
    
    # Regra de Decisão do SAD (Sistema de Apoio à Decisão)
    if nivel_atual and nivel_atual >= COTA_ALERTA_MONTANTE:
        print("\n" + ""*20)
        print(f"ALERTA VERMELHO: O rio em Nova Era atingiu {nivel_atual} cm!")
        print(f"⏱️ Previsão de impacto crítico em Timóteo em cerca de {TEMPO_PROPAGACAO_HORAS} horas.")
        print(" Ação recomendada: Disparar boletim de aviso antecipado para a Defesa Civil.")
        print(""*20 + "\n")
        
        # Aqui no futuro você pode plugar a API do Telegram, WhatsApp ou Instagram Graph API
        # para enviar a mensagem automaticamente!
    else:
        print(" Situação normalizada. Nenhuma onda de cheia crítica detectada a montante.\n")

if __name__ == "__main__":
    verificar_estado_bacia()