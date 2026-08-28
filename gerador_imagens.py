import os
import io
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

PASTA_ASSETS = "assets"
PASTA_OUTPUT = "output"
FONTE_BOLD = os.path.join(PASTA_ASSETS, "Roboto-Bold.ttf")
FONTE_REGULAR = os.path.join(PASTA_ASSETS, "Roboto-Regular.ttf")

COR_BRANCA = (255, 255, 255)
COR_CINZA_CLARO = (200, 200, 200)
COR_NORMAL = (46, 204, 113)
COR_ATENCAO = (241, 196, 15)
COR_ALERTA = (230, 126, 34)
COR_PERIGO = (231, 76, 60)

if not os.path.exists(PASTA_OUTPUT):
    os.makedirs(PASTA_OUTPUT)

def obter_caminho_base(nivel):
    if nivel < 610:
        return os.path.join(PASTA_ASSETS, "capa_verde.png")
    elif nivel < 780:
        return os.path.join(PASTA_ASSETS, "capa_amarela.png")
    else:
        return os.path.join(PASTA_ASSETS, "capa_vermelha.png")

def gerar_grafico_transparente(dados_historicos):
    if not dados_historicos: return None
    horas = [d['hora'] for d in dados_historicos]
    niveis = [d['nivel'] for d in dados_historicos]

    fig, ax = plt.subplots(figsize=(7.0, 3.0))
    ax.plot(horas, niveis, color='white', linewidth=2, marker='o', markersize=4, markerfacecolor='white')

    for i, label in enumerate(ax.get_xticklabels()):
        if i % 4 != 0 and i != len(horas) - 1:
            label.set_visible(False)

    ax.set_facecolor('none')
    fig.patch.set_alpha(0)
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(axis='both', colors='white', labelsize=11)
    ax.grid(True, linestyle='--', alpha=0.2, color='white')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', dpi=120)
    plt.close('all')
    buf.seek(0)
    return Image.open(buf).convert("RGBA")

def gerar_capa(nivel_atual, tendencia, velocidade, leituras):
    caminho_base = obter_caminho_base(nivel_atual)
    
    try:
        imagem = Image.open(caminho_base).convert("RGBA")
    except:
        print(f"Aviso: Template {caminho_base} não encontrado. Gerando fundo preto.")
        imagem = Image.new('RGB', (1080, 1920), color=(30, 30, 30))

    draw = ImageDraw.Draw(imagem)
    centro_x = imagem.width // 2

    try:
        fonte_nivel = ImageFont.truetype(FONTE_BOLD, 130)
        fonte_status = ImageFont.truetype(FONTE_BOLD, 50)
        fonte_velocidade = ImageFont.truetype(FONTE_REGULAR, 50)
        fonte_previsao = ImageFont.truetype(FONTE_BOLD, 53)
        fonte_rodape = ImageFont.truetype(FONTE_REGULAR, 35)
    except:
        fonte_nivel = fonte_status = fonte_velocidade = fonte_previsao = fonte_rodape = ImageFont.load_default()

    draw.text((centro_x, 450), f"{int(nivel_atual)} cm", font=fonte_nivel, fill=COR_BRANCA, anchor="mm")
    draw.text((centro_x, 580), f"{tendencia.upper()}", font=fonte_status, fill=COR_BRANCA, anchor="mm")
    draw.text((centro_x, 640), f"({velocidade} cm/h)", font=fonte_velocidade, fill=COR_BRANCA, anchor="mm")
    
    # Gráfico
    if leituras:
        fatia_grafico = leituras[:20]
        hist_graf = []
        for d in fatia_grafico:
            dt = datetime.fromisoformat(d['data_hora'].replace("Z", "+00:00"))
            hist_graf.append({'hora': dt.strftime('%H:%M'), 'nivel': d['nivel_cm']})
        hist_graf.reverse()

        graf_img = gerar_grafico_transparente(hist_graf)
        if graf_img:
            pos_x = (imagem.width - graf_img.width) // 2
            imagem.paste(graf_img, (pos_x, 920), graf_img)

    # Histórico fixo (mantido do original)
    historico_dict = {2020: 890, 2021: 910, 2022: 1040, 2023: 750}
    pos_x_esq, pos_x_dir = 350, 840
    pos_y_l1, pos_y_l2 = 1530, 1750

    def fmt_h(ano):
        return f"{ano}:\n{historico_dict.get(int(ano), '---')} cm"

    draw.text((pos_x_esq, pos_y_l1), fmt_h("2020"), font=fonte_previsao, fill=COR_BRANCA, anchor="mm", align="center")
    draw.text((pos_x_esq, pos_y_l2), fmt_h("2021"), font=fonte_previsao, fill=COR_BRANCA, anchor="mm", align="center")
    draw.text((pos_x_dir, pos_y_l1), fmt_h("2022"), font=fonte_previsao, fill=COR_BRANCA, anchor="mm", align="center")
    draw.text((pos_x_dir, pos_y_l2), fmt_h("2023"), font=fonte_previsao, fill=COR_BRANCA, anchor="mm", align="center")
    
    dt_atual = datetime.now().strftime("%d/%m/%Y às %H:%M")
    draw.text((centro_x, imagem.height - 35), f"Atualizado: {dt_atual}", font=fonte_rodape, fill=COR_CINZA_CLARO, anchor="mm")

    caminho = os.path.join(PASTA_OUTPUT, "capa_final.png")
    imagem.save(caminho)
    return caminho

def gerar_placares_paginados(relatorio_ruas):
    ITENS_POR_PAGINA = 14
    ESPACO_VERTICAL = 115
    paginas = [relatorio_ruas[i:i + ITENS_POR_PAGINA] for i in range(0, len(relatorio_ruas), ITENS_POR_PAGINA)]
    caminhos_gerados = []

    try:
        font_titulo = ImageFont.truetype(FONTE_BOLD, 70)
        font_nome_rua = ImageFont.truetype(FONTE_BOLD, 45)
        font_detalhe = ImageFont.truetype(FONTE_REGULAR, 40)
        font_pct = ImageFont.truetype(FONTE_BOLD, 50)
    except:
        font_titulo = font_nome_rua = font_detalhe = font_pct = ImageFont.load_default()

    for i, ruas_pagina in enumerate(paginas):
        largura, altura = 1080, 1920
        img = Image.new('RGB', (largura, altura), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)
        centro_x = largura // 2

        titulo = "SITUAÇÃO DAS RUAS" if len(paginas) == 1 else f"SITUAÇÃO DAS RUAS ({i+1}/{len(paginas)})"
        draw.text((50, 100), titulo, font=font_titulo, fill=COR_BRANCA)
        draw.line([(50, 190), (1030, 190)], fill=COR_BRANCA, width=3)

        y_pos = 220
        for rua in ruas_pagina:
            nome_p = rua['nome']
            pct = rua['ocupacao_pct']

            cor_b = COR_NORMAL
            if pct > 50: cor_b = COR_ATENCAO
            if pct > 80: cor_b = COR_ALERTA
            if pct >= 100: cor_b = COR_PERIGO

            draw.text((50, y_pos), nome_p, font=font_nome_rua, fill=COR_BRANCA)
            draw.text((50, y_pos + 45), "Ocupação da Calha", font=font_detalhe, fill=COR_CINZA_CLARO)

            draw.rectangle([(600, y_pos + 15), (900, y_pos + 55)], fill=(60, 60, 60))
            largura_b = (min(pct, 100) / 100) * 300
            draw.rectangle([(600, y_pos + 15), (600 + largura_b, y_pos + 55)], fill=cor_b)
            draw.text((920, y_pos + 5), f"{pct:.0f}%", font=font_pct, fill=cor_b)
            
            y_pos += ESPACO_VERTICAL

        if i < len(paginas) - 1:
            draw.text((centro_x, 1850), "Continua no próximo story... ➡️", font=font_detalhe, fill=COR_BRANCA, anchor="mm")

        caminho = os.path.join(PASTA_OUTPUT, f"placar_ruas_parte_{i+1}.png")
        img.save(caminho)
        caminhos_gerados.append(caminho)

    return caminhos_gerados

def gerar_todas_imagens(nivel_atual, tendencia, velocidade, leituras, ruas):
    caminho_capa = gerar_capa(nivel_atual, tendencia, velocidade, leituras)
    lista_placares = gerar_placares_paginados(ruas)
    return [caminho_capa] + lista_placares