import pika
import json
import sys
import os
import requests
from shared.utils import verificar_assinatura, chave_publica

class Itinerario:
    def __init__(self):
        self.chave_publica_pagamento = chave_publica()
        self.connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.channel = self.connection.channel()

        self.channel.queue_declare(queue="reserva-criada")
        self.channel.queue_declare(queue="reserva-cancelada")
        
    
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
        assinatura = bytes.fromhex(msg["assinatura"])

        if not verificar_assinatura(self.chave_publica_pagamento, assinatura, reserva_id):
            print(f"[X] Assinatura inválida para reserva {reserva_id}. Ignorando mensagem.")
            return

        print(f"[✓] Pagamento verificado para reserva {reserva_id}")
        self.bilhete_gerado(ch, reserva_id)


    def callback_reserva_criada(self, ch, method, properties, body):
        msg = json.loads(body)
        reserva_id = msg["reserva_id"]
        assinatura = bytes.fromhex(msg["assinatura"])

        if not verificar_assinatura(self.chave_publica_pagamento, assinatura, reserva_id):
            print(f"[X] Assinatura inválida para reserva {reserva_id}. Ignorando mensagem.")
            return

        print(f"[✓] Pagamento verificado para reserva {reserva_id}")
        self.bilhete_gerado(ch, reserva_id)


    def run(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.titulo()
        self.channel.basic_consume(queue='reserva-criada', on_message_callback=self.callback_pagamento_aprovado, auto_ack=True)
        self.channel.basic_consume(queue='reserva-cancelada', on_message_callback=self.callback_pagamento_aprovado, auto_ack=True)


        print("[MS Itinerário] Aguardando confirmações de pagamento...")
        self.channel.start_consuming()


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