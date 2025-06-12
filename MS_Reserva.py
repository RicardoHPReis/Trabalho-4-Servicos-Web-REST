from flask import Flask, request, jsonify, render_template, Response, stream_with_context
import shared.utils as utils
import threading
import requests
import datetime
import queue
import pika
import json
import uuid

app = Flask(
    __name__,
    static_folder="frontend/static",
    template_folder="frontend/templates"
)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue='reserva-criada', durable=True)
channel.queue_declare(queue='reserva-cancelada', durable=True)
channel.queue_declare(queue='pagamento-aprovado', durable=True)
channel.queue_declare(queue='pagamento-recusado', durable=True)
channel.queue_declare(queue='bilhete-gerado', durable=True)
channel.queue_declare(queue='promocoes', durable=True)

reservas = utils.carregar_dados('./json/reservas.json')
interesses = set()
sse_clients = {}

# Helper para enviar mensagens SSE
def send_sse_message(client_id, message):
    if client_id in sse_clients:
        for q in sse_clients[client_id]:
            try:
                q.put(message)
            except:
                pass

# Stream de eventos SSE
def event_stream(client_id):
    q = queue.Queue()
    sse_clients.setdefault(client_id, []).append(q)
    try:
        while True:
            msg = q.get()
            yield f"data: {json.dumps(msg)}\n\n"
    except GeneratorExit:
        if client_id in sse_clients:
            sse_clients[client_id].remove(q)

def consume_events():
    def callback(ch, method, properties, body):
        routing_key = method.routing_key
        event = json.loads(body)

        if routing_key == 'pagamento-aprovado':
            reserva_id = event['reserva_id']
            client_id = event['client_id']
            if reserva_id in reservas:
                reservas[reserva_id]['status'] = 'pagamento aprovado'
                send_sse_message(client_id, {
                    'tipo': 'pagamento-aprovado', 
                    'reserva_id': reserva_id
                })

        elif routing_key == 'pagamento-recusado':
            reserva_id = event['reserva_id']
            client_id = event['client_id']
            if reserva_id in reservas:
                reservas[reserva_id]['status'] = 'pagamento recusado'
                send_sse_message(client_id, {
                    'tipo': 'pagamento-recusado', 
                    'reserva_id': reserva_id
                })

        elif routing_key == 'bilhete-gerado':
            client_id = event['client_id']
            send_sse_message(client_id, {
                'tipo': 'bilhete-gerado', 
                'bilhete': event
            })

        elif routing_key == 'promocoes':
            for client_id in interesses:
                send_sse_message(client_id, {
                    'tipo': 'promocao', 
                    'promo': event
                })

    channel.basic_consume(queue='pagamento-aprovado', on_message_callback=callback, auto_ack=True)
    channel.basic_consume(queue='pagamento-recusado', on_message_callback=callback, auto_ack=True)
    channel.basic_consume(queue='bilhete-gerado', on_message_callback=callback, auto_ack=True)
    channel.basic_consume(queue='promocoes', on_message_callback=callback, auto_ack=True)
    
    print("[MS Reserva] Consumidor RabbitMQ iniciado")
    channel.start_consuming()


threading.Thread(target=consume_events, daemon=True).start()


@app.route("/", endpoint='index')
def page_index():
    return render_template("index.html")

@app.route("/consultar", endpoint='consultar')
def page_consultar():
    return render_template("consultar.html")

@app.route("/reservar", endpoint='reservar')
def page_reservar():
    return render_template("reservar.html")

@app.route("/cancelar", endpoint='cancelar')
def page_cancelar():
    return render_template("cancelar.html")

@app.route("/promocoes", endpoint='promocoes')
def page_promocoes():
    return render_template("promocoes.html")

# Endpoints REST
@app.route('/api/itinerarios', methods=['GET'])
def consultar_itinerarios():
    destino = request.args.get('destino')
    data = request.args.get('data')
    porto = request.args.get('porto')
    
    params = {}
    if destino: params['destino'] = destino
    if data: params['data'] = data
    if porto: params['porto'] = porto
    
    resp = requests.get('http://localhost:5001/itinerarios', params=params)
    return jsonify(resp.json())

@app.route('/api/reservar', methods=['POST'])
def efetuar_reserva():
    data = request.json
    reserva_id = f"RES-{str(uuid.uuid4().hex[:8].upper())}"
    valor = 2000
    
    reserva = {
        'reserva_id': reserva_id,
        'destino': data['destino'],
        'data_embarque': data.get('data_embarque', '2025-01-01'),
        'passageiros': int(data['passageiros']),
        'cabines': int(data['cabines']),
        'client_id': data['client_id'],
        'valor': valor*int(data['passageiros']),
        "horario": datetime.datetime.now().isoformat(),
        'status': 'pendente'
    }
    reservas = utils.adicionar_dado('./json/reservas.json', reserva_id, reserva)

    channel.basic_publish(
        exchange='',
        routing_key='reserva-criada',
        body=json.dumps(reserva),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    pagamento_req = {
        'reserva_id': reserva_id,
        'client_id': reserva['client_id'],
        'valor': reserva['valor'],
        "horario": datetime.datetime.now().isoformat()
    }
    resp = requests.post('http://localhost:5002/pagamento', json=pagamento_req)
    link_pagamento = resp.json().get('link_pagamento', '')
    
    if link_pagamento == "":
        requests.post('http://localhost:5000/api/cancelar-reserva', json={'reserva_id': reserva_id, 'client_id': reserva['client_id']})

    return jsonify({
        'reserva_id': reserva_id,
        'link_pagamento': link_pagamento
    }), 200

@app.route('/api/cancelar-reserva', methods=['POST'])
def cancelar_reserva():
    data = request.json
    reserva_id = data.get('reserva_id')
    client_id = data.get('client_id')
    
    if not reserva_id or reserva_id not in reservas:
        return jsonify({'erro': 'Reserva não encontrada'}), 404
    
    if reservas[reserva_id]['client_id'] != client_id:
        return jsonify({'erro': 'Reserva não pertence ao cliente'}), 403
    
    reservas[reserva_id]['status'] = 'cancelada'
    utils.atualizar_dado("./json/reservas.json", reserva_id, 'status', 'cancelada')
    
    channel.basic_publish(
        exchange='',
        routing_key='reserva-cancelada',
        body=json.dumps(reservas[reserva_id]),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    return jsonify({'mensagem': 'Reserva cancelada com sucesso'}), 200

@app.route('/api/reservas/<client_id>', methods=['GET'])
def listar_reservas(client_id):
    user_reservas = [r for r in reservas.values() if r['client_id'] == client_id]
    return jsonify(user_reservas), 200

@app.route('/api/registrar-interesse', methods=['POST'])
def registrar_interesse():
    data = request.json
    client_id = data.get('client_id')
    
    if not client_id:
        return jsonify({'erro': 'client_id obrigatório'}), 400
    
    interesses.add(client_id)
    return jsonify({'mensagem': f'Interesse registrado para {client_id}'})

@app.route('/api/cancelar-interesse', methods=['POST'])
def cancelar_interesse():
    data = request.json
    client_id = data.get('client_id')
    
    if not client_id:
        return jsonify({'erro': 'client_id obrigatório'}), 400
    
    if client_id in interesses:
        interesses.remove(client_id)
    
    return jsonify({'mensagem': f'Interesse cancelado para {client_id}'})

# Endpoint SSE para notificações
@app.route('/api/notificacoes/<client_id>')
def sse_events(client_id):
    return Response(
        stream_with_context(event_stream(client_id)),
        mimetype='text/event-stream'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)