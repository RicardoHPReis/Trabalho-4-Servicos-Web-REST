import subprocess
import os
import time
import webbrowser

pasta_sistema = os.path.dirname(os.path.abspath(__file__))
scripts = ["MS_Marketing.py", "MS_Reserva.py", "MS_Bilhete.py", "MS_Pagamento.py", "MS_Itinerario.py"]  

def abrir_terminal(script_path):
    subprocess.Popen(f'start cmd /k python "{script_path}"', shell=True)

for script in scripts:
    caminho_completo = os.path.join(pasta_sistema, script)
    abrir_terminal(caminho_completo)

# Aguarda alguns segundos
time.sleep(5)

# Abre o navegador na porta do Assinante (5000)
webbrowser.open('http://localhost:5000')