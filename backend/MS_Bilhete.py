import pika
import json
import sys
import os
import requests
from shared.utils import verificar_assinatura, chave_publica

class Bilhete:
    def __init__(self):
        self.chave_publica_pagamento = chave_publica()
        self.connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.channel = self.connection.channel()

        self.channel.queue_declare(queue="pagamento-aprovado")
        self.channel.queue_declare(queue="bilhete-gerado")
        
    
    def __del__(self):
        self.connection.close()
        #os.system('cls' if os.name == 'nt' else 'clear')
        
    
    def titulo(self) -> None:
        print("--------------------")
        print("       BILHETE")
        print("--------------------\n")


    def callback_pagamento_aprovado(self, ch, method, properties, body):
        msg = json.loads(body)
        reserva_id = msg["reserva_id"]
        assinatura = bytes.fromhex(msg["assinatura"])

        if not verificar_assinatura(self.chave_publica_pagamento, assinatura, reserva_id):
            print(f"[X] Assinatura inválida para reserva {reserva_id}. Ignorando mensagem.")
            return

        print(f"[✓] Pagamento verificado para reserva {reserva_id}")
        self.bilhete_gerado(ch, reserva_id)


    def bilhete_gerado(self, channel, reserva_id):
        print(f"[OK] Gerando bilhete para a reserva {reserva_id}...")
        bilhete = {
            "reserva_id": reserva_id,
            "codigo_bilhete": f"BLT-{reserva_id[:8]}",
            "mensagem": "Bilhete gerado com sucesso!"
        }
        
        channel.basic_publish(
            exchange='',
            routing_key='bilhete-gerado',
            body=json.dumps(bilhete)
        )
        print(f"[✓] Bilhete gerado publicado para reserva {bilhete['reserva_id']}")   


    def run(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.titulo()
        self.channel.basic_consume(queue='pagamento-aprovado', on_message_callback=self.callback_pagamento_aprovado, auto_ack=True)

        print("[MS Bilhete] Aguardando confirmações de pagamento...")
        self.channel.start_consuming()


if __name__ == "__main__":
    try:
        bilhete = Bilhete()
        bilhete.run()
    except KeyboardInterrupt:
        print('Interrompido')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)