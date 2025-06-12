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

FILE_RESERVAS = './json/reservas.json'
FILE_INTERESSES   = './json/interesses.json'
FILE_MARKETING    = './json/marketing.json'

reservas = utils.carregar_dados(FILE_RESERVAS)
interesses = set(utils.carregar_dados(FILE_INTERESSES).keys())
sse_clients = {}

def send_sse_message(client_id, message):
    if client_id in sse_clients:
        for q in list(sse_clients[client_id]):
            try:
                q.put(message)
            except:
                sse_clients[client_id].remove(q)

def enviar_historico_promocoes(client_id):
    marketing_db = utils.carregar_dados(FILE_MARKETING)
    for promo in marketing_db.values():
        send_sse_message(client_id, {
            'tipo': 'promocao',
            'promo': promo
        })

def event_stream(client_id):
    q = queue.Queue()
    sse_clients.setdefault(client_id, []).append(q)
    try:
        while True:
            msg = q.get()
            yield f"data: {json.dumps(msg)}\n\n"
    except GeneratorExit:
        pass
    finally:
        if client_id in sse_clients:
            sse_clients[client_id].remove(q)
            if not sse_clients[client_id]:
                del sse_clients[client_id]

def callback(ch, method, properties, body):
    routing_key = method.routing_key
    msg = json.loads(body)
    reserva_id = msg.get('reserva_id')
    client_id = msg.get('client_id')
    current = utils.carregar_dados(FILE_RESERVAS)

    if routing_key == 'pagamento-aprovado':
        if reserva_id in current:
            current[reserva_id]['status'] = 'aprovado'
            utils.salvar_dados(FILE_RESERVAS, current)
            print(f"[SSE] Enviando pagamento-aprovado para {client_id}")
            send_sse_message(client_id, {
                'tipo': 'pagamento-aprovado',
                'reserva_id': reserva_id
            })

    elif routing_key == 'pagamento-recusado':
        if reserva_id in current:
            current[reserva_id]['status'] = 'recusado'
            utils.salvar_dados(FILE_RESERVAS, current)
            requests.post('http://localhost:5000/api/cancelar-reserva',
                          json={'reserva_id': reserva_id, 'client_id': client_id})
            print(f"[SSE] Enviando pagamento-recusado para {client_id}")
            send_sse_message(client_id, {
                'tipo': 'pagamento-recusado',
                'reserva_id': reserva_id
            })

    elif routing_key == 'bilhete-gerado':
        if reserva_id in current:
            current[reserva_id]['status']     = 'concluído'
            current[reserva_id]['bilhete_id'] = msg.get('bilhete_id')
            utils.salvar_dados(FILE_RESERVAS, current)
            print(f"[SSE] Enviando bilhete-gerado para {client_id}")
            send_sse_message(client_id, {
                'tipo': 'bilhete-gerado',
                'bilhete': msg
            })

    elif routing_key == 'promocoes':
        promo = msg
        marketing_db = utils.carregar_dados(FILE_MARKETING)
        promo_id = f"promo-{len(marketing_db) + 1}"
        marketing_db[promo_id] = promo
        utils.salvar_dados(FILE_MARKETING, marketing_db)
        for cid in interesses:
            send_sse_message(cid, {
                'tipo': 'promocao',
                'promo': promo
            })

def consume_events():
    for fila in ['pagamento-aprovado', 'pagamento-recusado', 'bilhete-gerado', 'promocoes']:
        channel.basic_consume(queue=fila, on_message_callback=callback, auto_ack=True)
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

@app.route('/api/itinerarios', methods=['GET'])
def consultar_itinerarios():
    destino = request.args.get('destino')
    data    = request.args.get('data')
    porto   = request.args.get('porto')
    params = {}
    if destino: params['destino'] = destino
    if data:    params['data']    = data
    if porto:   params['porto']   = porto
    resp = requests.get('http://localhost:5001/itinerarios', params=params)
    return jsonify(resp.json())

@app.route('/api/reservar', methods=['POST'])
def efetuar_reserva():
    data       = request.json
    reserva_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
    itin = requests.get('http://localhost:5001/itinerarios',
                        params={'destino': data['destino']}).json()
    valor = itin[0]['valor']

    reserva = {
        'reserva_id':   reserva_id,
        'destino':      data['destino'],
        'data_embarque':data.get('data_embarque', '2025-01-01'),
        'passageiros':  int(data['passageiros']),
        'cabines':      int(data['cabines']),
        'client_id':    data['client_id'],
        'valor':        valor * int(data['passageiros']),
        'horario':      datetime.datetime.now().isoformat(),
        'status':       'pendente'
    }
    utils.adicionar_dado(FILE_RESERVAS, reserva_id, reserva)

    channel.basic_publish(
        exchange='',
        routing_key='reserva-criada',
        body=json.dumps(reserva),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    pagamento_req = {
        'reserva_id': reserva_id,
        'client_id': data['client_id'],
        'valor': reserva['valor'],
        'horario': datetime.datetime.now().isoformat()
    }
    resp = requests.post('http://localhost:5002/pagamento', json=pagamento_req)
    return jsonify({
        'reserva_id':   reserva_id,
        'link_pagamento': resp.json().get('link_pagamento', '')
    }), 200

@app.route('/api/cancelar-reserva', methods=['POST'])
def cancelar_reserva():
    data = request.json
    reserva_id = data.get('reserva_id')
    client_id = data.get('client_id')
    all_res = utils.carregar_dados(FILE_RESERVAS)
    if not reserva_id or reserva_id not in all_res:
        return jsonify({'erro': 'Reserva não encontrada'}), 404
    if all_res[reserva_id]['client_id'] != client_id:
        return jsonify({'erro': 'Reserva não pertence ao cliente'}), 403

    all_res[reserva_id]['status'] = 'cancelada'
    utils.salvar_dados(FILE_RESERVAS, all_res)

    channel.basic_publish(
        exchange='',
        routing_key='reserva-cancelada',
        body=json.dumps(all_res[reserva_id]),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    return jsonify({'mensagem': 'Reserva cancelada com sucesso'}), 200

@app.route('/api/reservas/<client_id>', methods=['GET'])
def listar_reservas(client_id):
    all_res = utils.carregar_dados(FILE_RESERVAS)
    user_res = [r for r in all_res.values() if r['client_id'] == client_id]
    return jsonify(user_res), 200

@app.route('/api/registrar-interesse', methods=['POST'])
def registrar_interesse():
    data = request.json
    client_id = data.get('client_id')
    if not client_id:
        return jsonify({'erro': 'client_id obrigatório'}), 400

    db = utils.carregar_dados(FILE_INTERESSES)
    if client_id not in db:
        db[client_id] = {'horario': datetime.datetime.now().isoformat()}
        utils.salvar_dados(FILE_INTERESSES, db)
        interesses.add(client_id)
        enviar_historico_promocoes(client_id)

    return jsonify({
        'mensagem': f'Interesse registrado para {client_id}',
        'total_interessados': len(db)
    }), 200

@app.route('/api/cancelar-interesse', methods=['POST'])
def cancelar_interesse():
    data = request.json
    client_id = data.get('client_id')
    if not client_id:
        return jsonify({'erro': 'client_id obrigatório'}), 400

    db = utils.carregar_dados(FILE_INTERESSES)
    if client_id in db:
        del db[client_id]
        utils.salvar_dados(FILE_INTERESSES, db)
        interesses.discard(client_id)

    return jsonify({
        'mensagem': f'Interesse cancelado para {client_id}',
        'total_interessados': len(db)
    }), 200

@app.route('/api/promocoes', methods=['GET'])
def listar_promocoes():
    promos = utils.carregar_dados(FILE_MARKETING)
    return jsonify(list(promos.values())), 200

@app.route('/api/notificacoes/<client_id>')
def sse_events(client_id):
    return Response(
        stream_with_context(event_stream(client_id)),
        mimetype='text/event-stream'
    )

@app.route('/api/status-reserva/<reserva_id>', methods=['GET'])
def status_reserva(reserva_id):
    dados = utils.carregar_dados(FILE_RESERVAS)
    if reserva_id not in dados:
        return jsonify({'erro': 'reserva não encontrada'}), 404
    return jsonify(dados[reserva_id])

if __name__ == '__main__':
    app.run(debug=True, port=5000)