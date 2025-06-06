from flask import Flask, request, jsonify
import threading
import random
import sys
import os
from shared.utils import chave_privada, assinar_mensagem

class Externo:
    def __init__(self):
        self.app = Flask(__name__)
        self.pag_externo_routes()
        
        self.chave_privada_pagamento = chave_privada()
    
    
    def titulo(self) -> None:
        print("--------------------")
        print("       EXTERNO")
        print("--------------------\n")
    
    
    def pag_externo_routes(self):
        @self.app.route('/externo/gerar_link', methods=['GET'])
        def processar_pagamento(reserva_id, valor):
            aprovado = random.choice([True, False])
            status = "aprovado" #if aprovado else "recusado"

            assinatura = assinar_mensagem(self.chave_privada_pagamento, reserva_id)
            link = f"http://localhost:5000/reserva_id={reserva_id}?status={status}?{assinatura.hex()}"
            return jsonify(link), 200
    
    
    def flask_run(self):
        self.app.run(host='localhost', port=5001, debug=False, use_reloader=False)


    def run(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.titulo()
        print("[Pagamento Externo] Aguardando pagamentos para processar...")
        consumer_thread = threading.Thread(target=self.flask_run, args=(), daemon=True)
        consumer_thread.start()


if __name__ == "__main__":
    try:
        externo = Externo()
        externo.run()
    except KeyboardInterrupt:
        print('Interrompido')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)