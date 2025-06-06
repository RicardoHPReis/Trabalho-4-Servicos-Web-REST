import pika
import json
import random
import sys
import os
from flask import Flask, request, jsonify
from shared.utils import chave_privada, assinar_mensagem, verificar_assinatura, chave_publica

class Pagamento:
    def __init__(self):
        self.app = Flask(__name__)
        
        self.chave_privada_pagamento = chave_privada()
        self.chave_publica_pagamento = chave_publica()

        self.connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='sd4-pag', exchange_type='fanout', durable=True)

        self.channel.queue_declare(queue="sd4-reserva-criada")
        self.channel.queue_declare(queue="sd4-pagamento-recusado")
    
    
    def __del__(self):
        self.connection.close()
        #os.system('cls' if os.name == 'nt' else 'clear')
        
    
    def titulo(self) -> None:
        print("--------------------")
        print("      PAGAMENTO")
        print("--------------------\n")
        

    def publicar_status_pagamento(self, reserva_id, valor):
        print(f"[PROCESSANDO] Pagamento da reserva {reserva_id} no valor de R${valor}")
        aprovado = random.choice([True, False])
        status = "aprovado" #if aprovado else "recusado"
        fila = "sd4-pagamento-" + status

        assinatura = assinar_mensagem(self.chave_privada_pagamento, reserva_id)
        mensagem = {"reserva_id": reserva_id, "status": status, "assinatura": assinatura.hex()}

        if status == "recusado":
            self.channel.basic_publish(
                exchange='',
                routing_key='sd4-pagamento-recusado',
                body=json.dumps(mensagem)
            )
        else:
            self.channel.basic_publish(
                exchange='sd4-pag',
                routing_key='',
                body=json.dumps(mensagem)
            )
              
        print(f"[OK] Pagamento {status} para reserva {reserva_id}. Mensagem enviada para '{fila}'.")


    def callback_reserva_criada(self, ch, method, properties, body):
        msg = json.loads(body)
        reserva_id = msg["reserva_id"]
        valor = msg["valor"]
        self.publicar_status_pagamento(ch, reserva_id, valor)


    def run(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.titulo()
        self.channel.basic_consume(queue='sd4-reserva-criada', on_message_callback=self.callback_reserva_criada, auto_ack=True)

        print("[MS Pagamento] Aguardando novas reservas para processar...")
        self.channel.start_consuming()


if __name__ == "__main__":
    try:
        pagamento = Pagamento()
        pagamento.run()
    except KeyboardInterrupt:
        print('Interrompido')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)