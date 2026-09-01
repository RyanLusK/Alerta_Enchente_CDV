#  SAD - Sistema de Apoio à Decisão (Alerta Enchente CDV)

![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-brightgreen)
![Versão](https://img.shields.io/badge/Versão-1.0%20(MVP)-blue)
![Python](https://img.shields.io/badge/Python-3.10+-yellow)
![React](https://img.shields.io/badge/React-18%20(Vite)-61DAFB)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E)

O **SAD-Rio Piracicaba** é um ecossistema de software Full-Stack desenvolvido para monitoramento hidrológico, previsão de impactos e comunicação de risco automatizada para a comunidade de Cachoeira do Vale (Timóteo, MG). 

O sistema consolida dados telemetricos em tempo real, gerencia o estado operacional através de um Centro de Controle (CCO) protegido e automatiza o disparo de alertas em redes sociais utilizando uma arquitetura anti-shadowban.

---

##  Arquitetura do Sistema

O projeto é dividido em três camadas principais operando de forma assíncrona:

1. **Backend & Motor Analítico (Python):** 
   - Coleta de dados via API (Agência Nacional de Águas).
   - Cálculo de tendências (Velocidade de subida/descida).
   - Processamento de Imagens Preditivas (Pillow + Matplotlib) para alertas visuais.
2. **Camada de Dados & Backend as a Service (Supabase):**
   - Banco de Dados PostgreSQL (Leituras do rio, Ruas monitoradas, Status do sistema).
   - Autenticação de Usuários (Auth).
   - WebSockets para sincronização de estado em tempo real (Realtime).
3. **Frontend (React + Vite + TailwindCSS):**
   - **Dashboard Comunitário (`/`):** Interface pública, mobile-first, exibindo a cota de inundação cruzada com o nível atual, alertando moradores sobre o risco em suas ruas específicas.
   - **CCO / Painel Admin (`/admin`):** Acesso restrito (Login), telemetria em tempo real (Recharts), chaves operacionais (Kill Switch, Forçar Postagem) e injeção de cenários de teste simulados.

---

##  Arquitetura de Comunicação (ADR 001)

### O Desafio
Plataformas como o Instagram (Meta) possuem algoritmos rígidos contra bots. Em um contexto de Defesa Civil, ter a conta banida durante um desastre natural por uso de APIs não-oficiais (ex: `instagrapi`) é um risco inaceitável.

### A Solução Adotada (Guerrilla Engineering)
O disparo de mensagens foi desenhado para imitar 100% o comportamento humano:
* O script Python (`gerador_imagens.py`) desenha os relatórios sobrepostos a templates de alerta.
* Um módulo integrador (`android_bot.py`) utiliza comandos **ADB (Android Debug Bridge)** para enviar o arquivo diretamente via USB para um dispositivo Android físico (Redmi Note 12).
* Através de um Intent do sistema (`am broadcast`), o Python acorda o aplicativo **MacroDroid** no celular, que executa uma rotina de cliques nativos na interface real do Instagram.
* **Resultado:** Operação 100% à prova de banimentos algorítmicos.

---

##  Estrutura de Pastas

```text
/
├── frontend/                # Aplicação React (Dashboard)
│   ├── src/pages/           # Home (Comunidade) e Admin (CCO)
│   ├── src/supabaseClient.js # Conexão com o BaaS
│   └── ...
├── backend/                 # Motor Preditivo (Python)
│   ├── main.py              # Maestro (Loop assíncrono principal)
│   ├── gerador_imagens.py   # Renderização de gráficos e alertas (Pillow/Matplotlib)
│   ├── android_bot.py       # Integração ADB e gestão do MacroDroid
│   ├── tester_design.py     # Ambiente de testes isolado de componentes visuais
│   ├── assets/              # Templates base e Fontes
│   └── output/              # Repositório temporário de imagens geradas
└── README.md