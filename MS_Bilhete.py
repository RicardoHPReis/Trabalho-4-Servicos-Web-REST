import shared.utils as utils
import threading
import datetime
import pika
import json
import uuid


bilhetes = utils.carregar_dados('./json/bilhetes.json')

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue="pagamento-aprovado", durable=True)
channel.queue_declare(queue="bilhete-gerado", durable=True)


def callback(ch, method, properties, body):
    dados = json.loads(body)
    reserva_id = dados["reserva_id"]
    client_id = dados["client_id"]

    bilhete_id = f"BLT-{str(uuid.uuid4().hex[:8].upper())}"
    bilhete = {
        "bilhete_id": bilhete_id,
        "reserva_id": reserva_id,
        "client_id": client_id,
        "horario": datetime.datetime.now().isoformat(),
    }
    bilhetes = utils.adicionar_dado('./json/bilhetes.json', bilhete_id, bilhete)

    bilhetes[bilhete_id] = bilhete

    channel.basic_publish(
        exchange='',
        routing_key="bilhete-gerado",
        body=json.dumps(bilhete),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    print(f"Bilhete gerado: {bilhete}")


def consumir():
    channel.basic_consume(
        queue="pagamento-aprovado",
        on_message_callback=callback,
        auto_ack=True
    )
    print("[Bilhete] Aguardando pagamentos aprovados...")
    channel.start_consuming()


if __name__ == '__main__':
    threading.Thread(target=consumir, daemon=False).start()
