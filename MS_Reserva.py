from flask import Flask, request, jsonify, Response, stream_with_context
import shared.utils as utils
import threading
import requests
import datetime
import queue
import pika
import json
import uuid

app = Flask(__name__)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue='reserva-criada', durable=True)
channel.queue_declare(queue='reserva-cancelada', durable=True)
channel.queue_declare(queue='pagamento-aprovado', durable=True)
channel.queue_declare(queue='pagamento-recusado', durable=True)
channel.queue_declare(queue='bilhete-gerado', durable=True)
channel.queue_declare(queue='promocoes', durable=True)

reservas = utils.carregar_dados('./json/reservas.json')
interesses_clientes = set()
sse_clientes = {}

def send_sse_message(client_id, message):
    if client_id in sse_clientes:
        for q in sse_clientes[client_id]:
            try:
                q.put(message)
            except Exception:
                pass

def event_stream(client_id):
    q = queue.Queue()
    if client_id not in sse_clientes:
        sse_clientes[client_id] = []
    sse_clientes[client_id].append(q)
    try:
        while True:
            msg = q.get()
            yield f"data: {json.dumps(msg)}\n\n"
    except GeneratorExit:
        sse_clientes[client_id].remove(q)


def callback(ch, method, properties, body):
    routing_key = method.routing_key
    event = json.loads(body)

    if routing_key == 'pagamento-aprovado':
        reserva_id = event['reserva_id']
        client_id = event['client_id']
        if reserva_id in reservas:
            reservas[reserva_id]['status'] = 'aprovado'
            reservas = utils.atualizar_dado("./json/reservas.json", reserva_id, 'status', 'aprovado')
            send_sse_message(client_id, {'tipo': 'pagamento-aprovado', 'reserva_id': reserva_id})

    elif routing_key == 'pagamento-recusado':
        reserva_id = event['reserva_id']
        client_id = event['client_id']
        if reserva_id in reservas:
            reservas[reserva_id]['status'] = 'recusado'
            reservas = utils.atualizar_dado("./json/reservas.json", reserva_id, 'status', 'cancelada')
            send_sse_message(client_id, {'tipo': 'pagamento-recusado', 'reserva_id': reserva_id})

    elif routing_key == 'bilhete-gerado':
        client_id = event['client_id']
        send_sse_message(client_id, {'tipo': 'bilhete-gerado', 'bilhete': event})

    elif routing_key == 'promocoes':
        for client_id in interesses_clientes:
            send_sse_message(client_id, {'tipo': 'promocao', 'promo': event})


def consume_events():
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


@app.route('/consultar-itinerarios', methods=['POST'])
def consultar_itinerarios():
    dados = request.json
    resp = requests.post('http://localhost:5001/itinerarios', json=dados)
    return jsonify(resp.json()), 200


@app.route('/efetuar-reserva', methods=['POST'])
def efetuar_reserva():
    dados = request.json
    reserva_id = f"RES-{str(uuid.uuid4().hex[:8].upper())}"
    reserva = {
        'reserva_id': reserva_id,
        'itinerario_id': dados['itinerario_id'],
        'client_id': dados['client_id'],
        'data_embarque': dados['data_embarque'],
        'passageiros': dados['passageiros'],
        'cabines': dados['cabines'],
        'status': 'pendente',
        "horario": datetime.datetime.now().isoformat()
    }
    reservas[reserva_id] = reserva

    channel.basic_publish(
        exchange='',
        routing_key='reserva-criada',
        body=json.dumps(reserva),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    pagamento_req = {
        'reserva_id': reserva_id,
        'client_id': dados['client_id'],
        'valor': dados['valor'],
        "horario": datetime.datetime.now().isoformat()
    }
    resp = requests.post('http://localhost:5002/pagamento', json=pagamento_req)
    link_pagamento = resp.json().get('link_pagamento', '')

    return jsonify({'reserva_id': reserva_id, 'link_pagamento': link_pagamento}), 200

@app.route('/cancelar-reserva', methods=['POST'])
def cancelar_reserva():
    dados = request.json
    reserva_id = dados.get('reserva_id')
    if not reserva_id or reserva_id not in reservas:
        return jsonify({'erro': 'Reserva não encontrada'}), 404

    reservas = utils.atualizar_dado("./json/reservas.json", reserva_id, 'status', 'cancelada')

    channel.basic_publish(
        exchange='',
        routing_key='reserva-cancelada',
        body=json.dumps(reservas[reserva_id]),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    return jsonify({'mensagem': 'Reserva cancelada'}), 200


@app.route("/reservas/<client_id>", methods=["GET"])
def listar_reservas(client_id):
    reservas_cliente = [r for r in reservas.values() if r["client_id"] == client_id]
    return jsonify(reservas_cliente), 200


@app.route('/registrar-interesse', methods=['POST'])
def registrar_interesse():
    dados = request.json
    client_id = dados.get('client_id')
    if not client_id:
        return jsonify({'erro': 'client_id obrigatório'}), 400
    interesses_clientes.add(client_id)
    return jsonify({'mensagem': f'Interesse registrado para {client_id}'}), 200


@app.route('/cancelar-interesse', methods=['POST'])
def cancelar_interesse():
    dados = request.json
    client_id = dados.get('client_id')
    if not client_id:
        return jsonify({'erro': 'client_id obrigatório'}), 400
    interesses_clientes.discard(client_id)
    return jsonify({'mensagem': f'Interesse cancelado para {client_id}'}), 200


@app.route('/eventos/<client_id>')
def eventos(client_id):
    return Response(stream_with_context(event_stream(client_id)), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(debug=True, port=5000)