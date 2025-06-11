from flask import Flask, request, jsonify, Response, stream_with_context
import requests
import pika
import json
import threading
import uuid
import time

app = Flask(__name__)

# RabbitMQ connection
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

# Declare queues
channel.queue_declare(queue='reserva-criada', durable=True)
channel.queue_declare(queue='reserva-cancelada', durable=True)
channel.queue_declare(queue='pagamento-aprovado', durable=True)
channel.queue_declare(queue='pagamento-recusado', durable=True)
channel.queue_declare(queue='bilhete-gerado', durable=True)
channel.queue_declare(queue='promocoes', durable=True)

# In-memory storage
reservas = {}
interesses = set()  # clientes interessados em promoções
sse_clients = {}  # client_id -> list of generator functions for SSE

def send_sse_message(client_id, message):
    # Envia evento SSE para todos os clientes conectados com esse client_id
    if client_id in sse_clients:
        for q in sse_clients[client_id]:
            try:
                q.put(message)
            except Exception:
                pass

# Função para criar generator para SSE
def event_stream(client_id):
    import queue
    q = queue.Queue()
    if client_id not in sse_clients:
        sse_clients[client_id] = []
    sse_clients[client_id].append(q)
    try:
        while True:
            msg = q.get()
            yield f"data: {json.dumps(msg)}\n\n"
    except GeneratorExit:
        sse_clients[client_id].remove(q)

# Consumidor RabbitMQ para filas que o MS Reserva escuta
def consume_events():
    def callback(ch, method, properties, body):
        routing_key = method.routing_key
        event = json.loads(body)

        if routing_key == 'pagamento-aprovado':
            reserva_id = event['reserva_id']
            client_id = event['client_id']
            if reserva_id in reservas:
                reservas[reserva_id]['status'] = 'pagamento aprovado'
                send_sse_message(client_id, {'tipo': 'pagamento-aprovado', 'reserva_id': reserva_id})

        elif routing_key == 'pagamento-recusado':
            reserva_id = event['reserva_id']
            client_id = event['client_id']
            if reserva_id in reservas:
                reservas[reserva_id]['status'] = 'pagamento recusado'
                send_sse_message(client_id, {'tipo': 'pagamento-recusado', 'reserva_id': reserva_id})

        elif routing_key == 'bilhete-gerado':
            client_id = event['client_id']
            send_sse_message(client_id, {'tipo': 'bilhete-gerado', 'bilhete': event})

        elif routing_key == 'promocoes':
            # Enviar promoções apenas para clientes interessados
            for client_id in interesses:
                send_sse_message(client_id, {'tipo': 'promocao', 'promo': event})

    # Setup consume
    channel.queue_declare(queue='pagamento-aprovado', durable=True)
    channel.queue_declare(queue='pagamento-recusado', durable=True)
    channel.queue_declare(queue='bilhete-gerado', durable=True)
    channel.queue_declare(queue='promocoes', durable=True)

    channel.basic_consume(queue='pagamento-aprovado', on_message_callback=callback, auto_ack=True)
    channel.basic_consume(queue='pagamento-recusado', on_message_callback=callback, auto_ack=True)
    channel.basic_consume(queue='bilhete-gerado', on_message_callback=callback, auto_ack=True)
    channel.basic_consume(queue='promocoes', on_message_callback=callback, auto_ack=True)

    channel.start_consuming()

threading.Thread(target=consume_events, daemon=True).start()

# Endpoints

@app.route('/consultar-itinerarios', methods=['POST'])
def consultar_itinerarios():
    dados = request.json
    # Consulta o MS Itinerarios via REST
    resp = requests.post('http://localhost:5001/itinerarios', json=dados)
    return jsonify(resp.json())

@app.route('/efetuar-reserva', methods=['POST'])
def efetuar_reserva():
    dados = request.json
    reserva_id = str(uuid.uuid4())
    reserva = {
        'id': reserva_id,
        'itinerario_id': dados['itinerario_id'],
        'data_embarque': dados['data_embarque'],
        'passageiros': dados['passageiros'],
        'cabines': dados['cabines'],
        'client_id': dados['client_id'],
        'status': 'pendente'
    }
    reservas[reserva_id] = reserva

    # Publica na fila reserva-criada
    channel.basic_publish(
        exchange='',
        routing_key='reserva-criada',
        body=json.dumps(reserva),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    # Solicita link de pagamento ao MS Pagamento
    pagamento_req = {
        'reserva_id': reserva_id,
        'valor': dados['valor'],
        'client_id': dados['client_id']
    }
    resp = requests.post('http://localhost:5002/pagamento', json=pagamento_req)
    link_pagamento = resp.json().get('link_pagamento', '')

    return jsonify({'reserva_id': reserva_id, 'link_pagamento': link_pagamento})

@app.route('/cancelar-reserva', methods=['POST'])
def cancelar_reserva():
    dados = request.json
    reserva_id = dados.get('reserva_id')
    if not reserva_id or reserva_id not in reservas:
        return jsonify({'erro': 'Reserva não encontrada'}), 404

    reserva = reservas[reserva_id]
    reserva['status'] = 'cancelada'

    # Publica na fila reserva-cancelada
    channel.basic_publish(
        exchange='',
        routing_key='reserva-cancelada',
        body=json.dumps(reserva),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    return jsonify({'mensagem': 'Reserva cancelada'})

@app.route("/reservas/<client_id>", methods=["GET"])
def listar_reservas(client_id):
    reservas_cliente = [r for r in reservas.values() if r["client_id"] == client_id]
    return jsonify(reservas_cliente)

@app.route('/registrar-interesse', methods=['POST'])
def registrar_interesse():
    dados = request.json
    client_id = dados.get('client_id')
    if not client_id:
        return jsonify({'erro': 'client_id obrigatório'}), 400
    interesses.add(client_id)
    return jsonify({'mensagem': f'Interesse registrado para {client_id}'})

@app.route('/cancelar-interesse', methods=['POST'])
def cancelar_interesse():
    dados = request.json
    client_id = dados.get('client_id')
    if not client_id:
        return jsonify({'erro': 'client_id obrigatório'}), 400
    interesses.discard(client_id)
    return jsonify({'mensagem': f'Interesse cancelado para {client_id}'})

@app.route('/eventos/<client_id>')
def eventos(client_id):
    return Response(stream_with_context(event_stream(client_id)), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, port=5000)