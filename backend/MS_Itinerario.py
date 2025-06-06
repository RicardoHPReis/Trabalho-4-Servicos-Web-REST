from flask import Flask, request, jsonify
import pika
import json
import sys
import os
from shared.utils import carregar_dados, atualizar_dado, deletar_dado, adicionar_dado

class Itinerario:
    def __init__(self):
        self.app = Flask(__name__)
        self.itinerarios_routes()
        
        self.connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.channel = self.connection.channel()

        self.channel.queue_declare(queue="sd4-reserva-criada")
        self.channel.queue_declare(queue="sd4-reserva-cancelada")
        
        self.caminho_reservas = './json/reservas.json'
        self.caminho_itinerarios = './json/itinerarios.json'
        self.itinerarios = carregar_dados(self.caminho_itinerarios)
        self.reservas = carregar_dados(self.caminho_reservas)
        
        self.app.run(host='localhost', port=5000, debug=False, use_reloader=False)
        
    
    def __del__(self):
        self.connection.close()
        #os.system('cls' if os.name == 'nt' else 'clear')
        
    
    def titulo(self) -> None:
        print("--------------------")
        print("      ITINERÁRIO")
        print("--------------------\n")


    def callback_reserva_criada(self, ch, method, properties, body):
        msg = json.loads(body)
        reserva_id = msg["reserva_id"]
        itinerario_id = msg["itinerario_id"]
        
        self.reservas = adicionar_dado(self.reservas, self.caminho_reservas, reserva_id)
        self.itinerarios = atualizar_dado(self.itinerarios, self.caminho_itinerarios, itinerario_id, reserva_id)
        print(f"[✓] Foi criada a reserva {reserva_id}")
    
    
    def callback_reserva_cancelada(self, ch, method, properties, body):
        msg = json.loads(body)
        reserva_id = msg["reserva_id"]
        itinerario_id = msg["itinerario_id"]

        self.reservas = deletar_dado(self.reservas, self.caminho_reservas, reserva_id)
        self.itinerarios = atualizar_dado(self.itinerarios, self.caminho_itinerarios, itinerario_id, reserva_id)
        print(f"[!] Pedido de cancelamento para reserva {reserva_id}")


    def itinerarios_routes(self):
        @self.app.route('/itinerarios', methods=['GET'])
        def get_itinerarios():
            return jsonify(carregar_dados(self.caminho_itinerarios)), 200
        

    def run(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.titulo()
        self.channel.basic_consume(queue='sd4-reserva-criada', on_message_callback=self.callback_reserva_criada, auto_ack=True)
        self.channel.basic_consume(queue='sd4-reserva-cancelada', on_message_callback=self.callback_reserva_cancelada, auto_ack=True)

        print("[MS Itinerário] Aguardando confirmações de pagamento...")
        self.channel.start_consuming()
        
    def run(self):
        os.system('cls' if os.name == 'nt' else 'clear')


if __name__ == "__main__":
    try:
        itinerario = Itinerario()
        itinerario.run()
    except KeyboardInterrupt:
        print('Interrompido')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)