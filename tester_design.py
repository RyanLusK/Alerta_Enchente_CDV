import os
from datetime import datetime, timedelta
import random

# Importa a função do novo gerador que criamos hoje
from gerador_imagens import gerar_todas_imagens

# ======================================================
# CONFIGURAÇÃO DO CENÁRIO DE TESTE
# ======================================================
NIVEL_ATUAL = 700.0
TENDENCIA_SIMULADA = "SUBINDO"
VELOCIDADE_SIMULADA = "+15.0"

def gerar_leituras_fake(nivel_final):
    """
    Gera uma lista de 20 leituras falsas (como se viessem do Supabase)
    para o gráfico ter aquela linha progressiva.
    """
    lista = []
    agora = datetime.now()
    nivel_inicial = nivel_final - 50 # Começa 50cm mais baixo
    
    for i in range(20):
        # Simula medições de 15 em 15 minutos
        tempo = agora - timedelta(minutes=15 * (19-i))
        progresso = i / 19 
        nivel = nivel_inicial + (progresso * 50) + random.uniform(-2, 2)
        
        lista.append({
            'data_hora': tempo.isoformat(),
            'nivel_cm': round(nivel, 1)
        })
        
    # Garante que a mais recente (última) seja o nível atual exato
    lista[-1] = {'data_hora': agora.isoformat(), 'nivel_cm': nivel_final}
    
    # O gerador novo espera a lista do mais novo (índice 0) para o mais velho, então invertemos:
    lista.reverse()
    return lista

def gerar_ruas_fake():
    """
    Simula o cálculo de ocupação que agora é feito lá no main.py
    """
    ruas_falsas = [
        {"nome": "Rua Rio Corrente", "nivel_critico_cm": 618},
        {"nome": "Rua Rio Tietê / Araguaia", "nivel_critico_cm": 650},
        {"nome": "Rua Tamoios", "nivel_critico_cm": 680},
        {"nome": "Rua João Pedreiro", "nivel_critico_cm": 700},
        {"nome": "Rua Guanabara", "nivel_critico_cm": 720},
        {"nome": "Rua Minas Gerais", "nivel_critico_cm": 740},
        {"nome": "Travessa Bartolomeu", "nivel_critico_cm": 760},
        {"nome": "Rua Rio São Francisco", "nivel_critico_cm": 780},
        {"nome": "Rua Paraná", "nivel_critico_cm": 800},
        {"nome": "Rua Ceará", "nivel_critico_cm": 820},
        {"nome": "Rua Amazonas", "nivel_critico_cm": 840},
        {"nome": "Beco do Chaves", "nivel_critico_cm": 860},
        {"nome": "Rua Piauí", "nivel_critico_cm": 880},
        {"nome": "Rua Maranhão", "nivel_critico_cm": 900},
        {"nome": "Avenida Brasil", "nivel_critico_cm": 950},
        {"nome": "Rua Santos Dumont", "nivel_critico_cm": 1000},
        {"nome": "Rua Machado de Assis", "nivel_critico_cm": 1050}
    ]
    
    relatorio = []
    for rua in ruas_falsas:
        pct = (NIVEL_ATUAL / rua["nivel_critico_cm"]) * 100
        relatorio.append({
            "nome": rua["nome"],
            "ocupacao_pct": round(pct, 1)
        })
        
    # Retorna do pior cenário para o mais tranquilo
    return sorted(relatorio, key=lambda x: x['ocupacao_pct'], reverse=True)

def rodar_teste():
    print(f"INICIANDO SIMULAÇÃO VISUAL")
    print(f"Nível Atual Simulado: {NIVEL_ATUAL} cm")

    # 1. Gera Leituras
    print("Gerando curva de gráfico simulada...")
    leituras_fake = gerar_leituras_fake(NIVEL_ATUAL)

    # 2. Gera Ruas
    print("Calculando riscos por rua simulados...")
    ruas_fake = gerar_ruas_fake()

    # 3. Chama o Gerador de Imagens
    print("Gerando imagens na pasta output/...")
    caminhos = gerar_todas_imagens(
        nivel_atual=NIVEL_ATUAL,
        tendencia=TENDENCIA_SIMULADA,
        velocidade=VELOCIDADE_SIMULADA,
        leituras=leituras_fake,
        ruas=ruas_fake
    )

    print("\nImagens geradas:")
    for path in caminhos:
        print(f" -> {path}")
        
    print("\n Design gerado na pasta 'output'.")

if __name__ == "__main__":
    rodar_teste()