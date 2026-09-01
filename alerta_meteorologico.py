import requests
from datetime import datetime

# ==========================================
# CONFIGURAÇÕES DO RADAR METEOROLÓGICO
# ==========================================
# Coordenadas do Vale do Aço / Bacia do Piracicaba
LATITUDE = "-19.5314"
LONGITUDE = "-42.6444"

# Limite de perigo (Se a previsão de chuva passar disso, dispara o alerta)
LIMITE_CHUVA_CRITICA_MM = 50.0  

def monitorar_nuvens():
    print("Conectando aos satélites meteorológicos...")
    print(f"Alvo: Bacia do Rio Piracicaba (Lat: {LATITUDE}, Lon: {LONGITUDE})\n")

    # URL da API Open-Meteo (Previsão de precipitação por hora para os próximos 3 dias)
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&hourly=precipitation&timezone=America%2FSao_Paulo&forecast_days=3"
    
    try:
        resposta = requests.get(url)
        resposta.raise_for_status()
        dados = resposta.json()
        
        tempos = dados['hourly']['time']
        chuvas = dados['hourly']['precipitation']
        
        # Vamos analisar as próximas 48 horas a partir de agora
        chuva_acumulada_48h = 0.0
        hora_atual = datetime.now().isoformat()[:13] # Pega até a hora (ex: 2026-08-31T11)
        
        index_atual = 0
        for i, t in enumerate(tempos):
            if t.startswith(hora_atual):
                index_atual = i
                break
                
        # Soma a chuva das próximas 48 horas
        janela_48h = chuvas[index_atual : index_atual + 48]
        chuva_acumulada_48h = sum(janela_48h)
        
        print("RELATÓRIO DO RADAR PARA AS PRÓXIMAS 48 HORAS:")
        print(f"Precipitação total esperada: {chuva_acumulada_48h:.1f} mm")
        
        # Regra de Decisão Meteorológica
        if chuva_acumulada_48h >= LIMITE_CHUVA_CRITICA_MM:
            print("\n" + ""*15)
            print("ALERTA METEOROLÓGICO: TEMPESTADE SEVERA A CAMINHO!")
            print(f"O volume de {chuva_acumulada_48h:.1f} mm ultrapassa a capacidade de absorção do solo.")
            print(f"Pelos nossos cálculos (Regra das 36h), o rio entrará em cota de alerta logo após essa chuva.")
            print(""*15 + "\n")
        elif chuva_acumulada_48h > 0:
            print("Chuva leve a moderada prevista. A bacia tem capacidade para absorver o volume sem risco de cheia.\n")
        else:
            print("Tempo firme. Nenhuma gota de chuva prevista para os próximos 2 dias. Nível do rio em declínio ou estável.\n")

    except Exception as e:
        print(f"Erro ao acessar os dados do satélite: {e}")

if __name__ == "__main__":
    monitorar_nuvens()