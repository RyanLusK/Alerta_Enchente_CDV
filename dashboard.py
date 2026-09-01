import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
from supabase import create_client

# ==========================================
# CONFIGURAÇÕES INICIAIS
# ==========================================
st.set_page_config(page_title="SAD - Rio Piracicaba", page_icon="", layout="wide")

SUPABASE_URL = "https://bybvlorarvxnnyggdsgf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ5YnZsb3JhcnZ4bm55Z2dkc2dmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzY4OTQ1MCwiZXhwIjoyMTAzMjY1NDUwfQ.WjsNPUXosNNAOFpMN0j8a9IsH8Lu31Oo8b3RDiD_IAA" # Use a service_role para ignorar RLS no backend
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# FUNÇÕES DE BUSCA DE DADOS (Com Cache)
# ==========================================
@st.cache_data(ttl=900) # Atualiza a cada 15 minutos
def buscar_dados_rio():
    # Busca os últimos 7 dias das duas estações
    hoje = datetime.now()
    semana_passada = (hoje - timedelta(days=7)).isoformat()
    
    resposta = supabase.table("historico_ana")\
        .select("codigo_ana, data_hora, nivel_cm")\
        .in_("codigo_ana", ["56661000", "56696000"])\
        .gte("data_hora", semana_passada)\
        .execute()
        
    df = pd.DataFrame(resposta.data)
    if not df.empty:
        df['data_hora'] = pd.to_datetime(df['data_hora'])
        df = df.pivot_table(index='data_hora', columns='codigo_ana', values='nivel_cm', aggfunc='mean')
        df.interpolate(method='linear', inplace=True)
        df.rename(columns={"56661000": "Nova Era (Montante)", "56696000": "Timóteo (Local)"}, inplace=True)
    return df

@st.cache_data(ttl=3600) # Atualiza a cada 1 hora
def buscar_previsao_chuva():
    url = "https://api.open-meteo.com/v1/forecast?latitude=-19.5314&longitude=-42.6444&hourly=precipitation&timezone=America%2FSao_Paulo&forecast_days=2"
    resp = requests.get(url).json()
    chuva_acumulada = sum(resp['hourly']['precipitation'])
    return chuva_acumulada

# ==========================================
# INTERFACE DO USUÁRIO (FRONTEND)
# ==========================================
st.title("Alerta de Enchente - Cachoeira do Vale")
st.markdown("Sistema de Apoio à Decisão para Prevenção de Enchentes no Cachoeira do Vale")
st.divider()

# Carrega os dados
with st.spinner("Conectando ao Data Lake e Satélites..."):
    df_rios = buscar_dados_rio()
    chuva_48h = buscar_previsao_chuva()

# 1. LINHA DE INDICADORES (KPIs)
col1, col2, col3 = st.columns(3)

# Lógica do Nível Atual
nivel_timoteo = df_rios['Timóteo (Local)'].iloc[-1] if not df_rios.empty else 0
nivel_nova_era = df_rios['Nova Era (Montante)'].iloc[-1] if not df_rios.empty else 0

col1.metric("Nível Atual - Timóteo", f"{nivel_timoteo:.0f} cm", "Estável")
col2.metric("Nível Atual - Nova Era", f"{nivel_nova_era:.0f} cm", "Monitorando")
col3.metric("Previsão de Chuva (48h)", f"{chuva_48h:.1f} mm", "Satélite", delta_color="inverse")

# 2. STATUS DE ALERTA
st.markdown("### Painel de Alerta")
if chuva_48h > 50 or nivel_nova_era > 400:
    st.error("**ALERTA CRÍTICO ATIVO:** Condições favoráveis para inundação. Lembre-se: O impacto da onda de cheia de Nova Era atinge Timóteo em aproximadamente **28 horas**.")
else:
    st.success("**SITUAÇÃO NORMAL:** Sem risco de cheia nas próximas horas. Bacia estabilizada.")

# 3. GRÁFICO INTERATIVO DE TELEMETRIA
st.markdown("### Telemetria da Bacia (Últimos 7 dias)")
if not df_rios.empty:
    # Usando Plotly para um gráfico web interativo
    fig = px.line(df_rios, x=df_rios.index, y=df_rios.columns, 
                  labels={'value': 'Nível da Água (cm)', 'data_hora': 'Data e Hora', 'codigo_ana': 'Estação'},
                  color_discrete_map={"Nova Era (Montante)": "#ff7f0e", "Timóteo (Local)": "#1f77b4"})
    
    # Adicionando a linha vermelha de perigo para Timóteo
    fig.add_hline(y=780, line_dash="dash", line_color="red", annotation_text="Cota de Emergência (Timóteo)")
    
    st.plotly_chart(fig, width='stretch')
else:
    st.warning("Aguardando coleta de dados recentes da ANA.")

# Rodapé
st.divider()
st.caption("by Ryan Luks")