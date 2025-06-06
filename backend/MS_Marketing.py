import pika
import json
import time
import random
import sys
import os

class Marketing:
    def __init__(self):
        self.promocoes = {}
        with open('./json/marketing.json', encoding='utf-8') as arquivo:
            self.promocoes = json.load(arquivo)
        
        self.destinos_disponiveis = list(self.promocoes.keys())
        
        self.connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue="sd4-promocoes-destino")
    
    
    def __del__(self):
        #os.system('cls' if os.name == 'nt' else 'clear')
        try:
            if self.channel and self.channel.is_open:
                self.channel.close()
            if self.connection and self.connection.is_open:
                self.connection.close()
        except Exception as e:
            print(f"[ERRO] {e}")


    def titulo(self) -> None:
        print("--------------------")
        print("      MARKETING")
        print("--------------------\n")


    def publicar_promocao(self, destino):
        msg = self.promocoes[destino]
        self.channel.basic_publish(exchange='', routing_key="sd4-promocoes-destino", body=json.dumps(msg))
        print(f"[✓] Promoção para '{destino}' publicada")


    def run(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self.titulo()
        while True:
            destino = random.choice(self.destinos_disponiveis)
            self.publicar_promocao(destino)
            time.sleep(random.randint(10, 30))


if __name__ == "__main__":
    try:
        marketing = Marketing()
        marketing.run()
    except KeyboardInterrupt:
        print('Interrompido')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)