import pika
import json
import random
import uuid
import time
import sys
import os
import requests
import unicodedata as ud
from flask import Flask, request, render_template, jsonify
from flask_sse import sse
from shared.utils import verificar_assinatura, chave_publica

class Reserva:
    def __init__(self):
        self.app = Flask(__name__)
        
        self.chave_publica_pagamento = chave_publica()
        self.connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='sd4-pag', exchange_type='fanout', durable=True)
        
        self.channel.queue_declare(queue="sd4-reserva-criada")
        self.channel.queue_declare(queue="sd4-reserva-cancelada")
        self.channel.queue_declare(queue="sd4-pagamento-aprovado", durable=True)
        self.channel.queue_declare(queue="sd4-pagamento-recusado")
        self.channel.queue_declare(queue="sd4-bilhete-gerado")
        
        self.channel.queue_bind(exchange='sd4-pag', queue="sd4-pagamento-aprovado")

        self.reservas = {}
        self.itinerarios = []
        with open('./json/itinerarios.json', encoding='utf-8') as arquivo:
            self.itinerarios = json.load(arquivo)
        
        self.destinos = list(self.itinerarios.keys())


    def __del__(self):
        self.connection.close()
        #os.system('cls' if os.name == 'nt' else 'clear')


    def titulo(self) -> None:
        print("--------------------")
        print("       RESERVA")
        print("--------------------\n")


    def callback_marketing(self, ch, method, properties, body):
        msg = json.loads(body)
        print("\n***************************")
        print(f"{msg['titulo']}: {msg['descricao']} Até {msg['validade']}. COMPRE AGORA!")
        print("***************************")


    def callback_bilhete(self, ch, method, properties, body):
        msg = json.loads(body)
        reserva = self.reservas[msg['reserva_id']]
        destino = next((d for d in self.itinerarios.values() if d["id"] == reserva["itinerario_id"]), None)
        
        if not destino:
            print(f"[ERRO] Itinerário {reserva['itinerario_id']} não encontrado.")
            return

        bilhete = {
            "reserva_id": msg['reserva_id'],
            "codigo_bilhete": f"{msg['codigo_bilhete']}",
            "navio": destino["navio"],
            "porto_embarque": destino["porto_embarque"],
            "data": destino["data"],
            "num_passageiros": reserva["num_passageiros"],
            "num_cabines": reserva["num_cabines"],
            "valor_total": reserva["valor_total"]
        }
        
        print(f"[✓] Bilhete detalhado gerado:")
        print("\n***************************")
        print(f"Código: {bilhete['codigo_bilhete']}")
        print(f"Navio: {bilhete['navio']}")
        print(f"Embarque: {bilhete['porto_embarque']}")
        print(f"N° de Passageiros: {bilhete['num_passageiros']}")
        print(f"Cabines: {bilhete['num_cabines']}")
        print(f"Valor pago: {bilhete['valor_total']}")
        print("***************************")


    def callback_pagamento(self, ch, method, properties, body):
        msg = json.loads(body)
        reserva_id = msg["reserva_id"]
        status_pagamento = msg["status"]
        assinatura = bytes.fromhex(msg["assinatura"])

        if not verificar_assinatura(self.chave_publica_pagamento, assinatura, reserva_id):
            print(f"[ERRO] Assinatura inválida para reserva {reserva_id}. Ignorando mensagem.")
            return

        if status_pagamento == "aprovado":
            print(f"[INFO] Pagamento aprovado (assinatura válida) para reserva {reserva_id}.")
        else:
            print(f"[INFO] Pagamento recusado (assinatura válida) para reserva {reserva_id}.")
            self.reservas[reserva_id]["status"] = "cancelado"
            print(f"[INFO] Reserva {reserva_id} cancelada.")


    def reserva_criada(self, reserva_id):
        reserva = self.reservas[reserva_id]
        msg = {
            "reserva_id": reserva_id,
            "itinerario_id": reserva["itinerario_id"],
            "destino": reserva["destino"],
            "valor": reserva["valor_total"],
            "num_passageiros": reserva["num_passageiros"],
            "num_cabines": reserva["num_cabines"]
        }
        self.channel.basic_publish(
            exchange='',
            routing_key='sd4-reserva-criada',
            body=json.dumps(msg)
        )
    
    
    def cancelar_reserva(self, reserva_id):
        reserva = self.reservas[reserva_id]
        msg = {
            "reserva_id": reserva_id,
            "itinerario_id": reserva["itinerario_id"],
            "destino": reserva["destino"],
            "valor": reserva["valor_total"],
            "num_passageiros": reserva["num_passageiros"],
            "num_cabines": reserva["num_cabines"]
        }
        self.channel.basic_publish(
            exchange='',
            routing_key='sd4-reserva-cancelada',
            body=json.dumps(msg)
        )
        
    def itinerarios_rotas(self):
        @self.app.route('/reserva/pagamento', methods=['POST'])
        def webhook_receiver():
            data = request.json
            print("Received webhook data:", data)
            return jsonify({'message': 'Webhook received successfully'}), 200


    def run(self):
        self.app.run(debug=True)
        
        lugar = {}
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            self.titulo()
            propaganda = random.choice(self.destinos)
            fila_propaganda = f'promocoes-destino_{propaganda}'
            self.channel.queue_declare(queue=fila_propaganda)
            self.channel.basic_consume(queue=fila_propaganda, on_message_callback=self.callback_marketing, auto_ack=True)
            
            for it in self.itinerarios.values():
                print(f"Destino: {it['destino']}")
                print(f"Navio: {it['navio']}")
                print(f"Data: {it['data']}")
                print(f"Dias: {it['noites']}")
                print(f"Valor p/pessoa: {it['valor']}")
                print(f"Porto Embarque: {it['porto_embarque']} -> Porto Retorno: {it['porto_retorno']}")
                print("--------------------------")
            
            destino = ud.normalize('NFKD', input("Escolha o destino: ").lower().strip()).encode('ascii', 'ignore').decode('utf-8')
            if destino in self.destinos:
                lugar = self.itinerarios[destino]
                break
            else:
                print('Destino inválido!')
                time.sleep(2)
                
        num_passageiros = int(input("Número de passageiros: "))
        num_cabines = int(input("Número de cabines: "))
        valor_total = num_passageiros * lugar['valor']
        
        dados = {
            "itinerario_id": lugar["id"],
            "num_passageiros": num_passageiros,
            "num_cabines": num_cabines,
            "valor_total": valor_total,
            "destino": destino
        }
        reserva_id = str(uuid.uuid4())
        self.reservas[reserva_id] = {"status": "pendente", **dados}
        print(f"\n[INFO] Link de pagamento: http://localhost:5000/pagar/{reserva_id}")
        self.reserva_criada(reserva_id, self.channel)
        print(f"[INFO] Reserva criada com ID {reserva_id}")
        self.cancelar_reserva(reserva_id, self.channel)

        self.channel.basic_consume(queue='sd4-pagamento-aprovado', on_message_callback=self.callback_pagamento)
        self.channel.basic_consume(queue='sd4-pagamento-recusado', on_message_callback=self.callback_pagamento, auto_ack=True)
        self.channel.basic_consume(queue='sd4-bilhete-gerado', on_message_callback=self.callback_bilhete, auto_ack=True)
        
        print("[*] Aguardando confirmações...")
        self.channel.start_consuming()


if __name__ == "__main__":
    try:
        reserva = Reserva()
        reserva.run()
    except KeyboardInterrupt:
        print('Interrompido')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)