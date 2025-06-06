import subprocess as sub
import webbrowser as web
import time as t
import os

pasta_sistema = os.path.dirname(os.path.abspath(__file__))
scripts = ["MS_Marketing.py", "MS_Reserva.py", "MS_Bilhete.py", "MS_Pagamento.py", "MS_Itinerario.py"]  

def abrir_terminal(script_path):
    sub.Popen(f'start cmd /k python "{script_path}"', shell=True)

for script in scripts:
    caminho_completo = os.path.join(pasta_sistema, script)
    abrir_terminal(caminho_completo)

# Aguarda alguns segundos
t.sleep(5)

# Abre o navegador na porta do Assinante (5000)
web.open('http://localhost:5000')

# rabbitmqctl stop_app
# rabbitmqctl reset
# rabbitmqctl start_app