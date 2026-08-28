import os
import subprocess
import asyncio

def executar_adb(comando_lista):
    cmd_adb = "adb"
    if os.path.exists("adb.exe"):
        cmd_adb = ".\\adb.exe"
    subprocess.run([cmd_adb] + comando_lista, check=False)

def acordar_celular():
    print("📱 Acordando o celular...")
    executar_adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"])
    executar_adb(["shell", "input", "swipe", "500", "2000", "500", "1000", "200"])
    executar_adb(["shell", "settings", "put", "system", "screen_brightness", "1"])

def dormir_celular():
    print("💤 Colocando celular para dormir...")
    executar_adb(["shell", "input", "keyevent", "KEYCODE_HOME"])
    executar_adb(["shell", "input", "keyevent", "KEYCODE_SLEEP"])

async def limpar_stories_antigos():
    print("🧹 Iniciando ROTINA DE FAXINA...")
    executar_adb(["shell", "am", "force-stop", "com.instagram.android"])
    await asyncio.sleep(2)
    executar_adb(["shell", "monkey", "-p", "com.instagram.android", "-c", "android.intent.category.LAUNCHER", "1"])
    
    await asyncio.sleep(8)
    print("   Disparando MacroDroid: APAGARSTORY")
    executar_adb(["shell", "am", "broadcast", "-a", "APAGARSTORY", "-p", "com.arlosoft.macrodroid"])
    
    tempo_macro = 30 
    print(f"   Aguardando {tempo_macro}s para a faxina...")
    await asyncio.sleep(tempo_macro)
    print("Limpeza concluída.")

async def enviar_uma_imagem(caminho_imagem):
    nome_arquivo = "alerta_story.png"
    destino_celular = f"/sdcard/Pictures/{nome_arquivo}"
    
    executar_adb(["shell", "rm", "-f", destino_celular])
    executar_adb(["push", caminho_imagem, destino_celular])
    executar_adb(["shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{destino_celular}"])
    
    executar_adb(["shell", "am", "force-stop", "com.instagram.android"])
    await asyncio.sleep(1.5)
    executar_adb(["shell", "monkey", "-p", "com.instagram.android", "-c", "android.intent.category.LAUNCHER", "1"])
    
    await asyncio.sleep(10)
    print("   Disparando Macro POSTAR_STORY...")
    executar_adb(["shell", "am", "broadcast", "-a", "POSTAR_STORY", "-p", "com.arlosoft.macrodroid"])

async def enviar_carrossel_android(lista_caminhos, deve_limpar=False):
    print("\n--- INICIANDO POSTAGEM ANDROID ---")
    acordar_celular()
    
    if deve_limpar:
        try:
            await limpar_stories_antigos() 
        except Exception as e:
            print(f"Erro na limpeza: {e}")

    tempo_por_story = 35 
    
    for i, imagem in enumerate(lista_caminhos):
        print(f"\nPostando {i+1}/{len(lista_caminhos)}...")
        try:
            await enviar_uma_imagem(imagem)
            print(f"⏳ Dando {tempo_por_story}s para o MacroDroid trabalhar...")
            await asyncio.sleep(tempo_por_story)
        except Exception as e:
            print(f"Erro ao postar imagem {i+1}: {e}")
            
    print("Ciclo Android finalizado.")
    dormir_celular()