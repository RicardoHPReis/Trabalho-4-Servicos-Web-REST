from flask import Flask, request, render_template, jsonify
from flask_sse import sse
import threading
import pika
import json
import logging
import datetime as d

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
destinos_inscritos = []
promocoes_recebidas = []
consumidor_ativo = False
consumer_thread = None
inicio_inscricao = None

with open('../json/marketing.json', 'r', encoding='utf-8') as f:
    destinos_disponiveis = json.load(f).keys()


def callback(ch, method, properties, body):
    if not consumidor_ativo:
        return
    mensagem = json.loads(body)
    destino = method.routing_key.split('_')[1]
    tempo_recebido = d.datetime.now()

    if destino in destinos and tempo_recebido >= inicio_inscricao:
        promocao = f"""
        <div class="promocao">
            <h3>{mensagem['titulo']}</h3>
            <p>{mensagem['descricao']}</p>
            <small>Validade: {mensagem['validade']}</small>
        </div>
        """
        promocoes_recebidas.insert(0, promocao)

def consumir_promocoes(destinos):
    global promocoes_recebidas, inicio_inscricao, consumidor_ativo
    promocoes_recebidas = []
    inicio_inscricao = d.datetime.now()
    consumidor_ativo = True

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    
    # Limpa filas antigas e recria
    for destino in destinos:
        fila = f"promocoes-destino_{destino}"
        channel.queue_delete(queue=fila)
        channel.queue_declare(queue=fila)
        channel.basic_consume(queue=fila, on_message_callback=callback, auto_ack=True)

    try:
        while consumidor_ativo:
            connection.process_data_events(time_limit=1)
    finally:
        connection.close()


@app.route("/", methods=["GET", "POST"])  # Corrigido para aceitar POST
def index():
    global destinos_inscritos, consumer_thread, consumidor_ativo
    
    if request.method == "POST":
        destinos_inscritos = request.form.getlist("destinos")
        if destinos_inscritos:
            # Para consumidor anterior
            if consumidor_ativo:
                consumidor_ativo = False
                if consumer_thread:
                    consumer_thread.join()
            
            # Inicia novo consumidor
            consumer_thread = threading.Thread(
                target=consumir_promocoes,
                args=(destinos_inscritos,),
                daemon=True
            )
            consumer_thread.start()
            logging.info(f"Inscrito em: {', '.join(destinos_inscritos)}")
    
    return render_template(
        "assinante.html",
        destinos_disponiveis=destinos_disponiveis,  # Nome corrigido
        destinos_inscritos=destinos_inscritos,       # Adicionado
        promocoes=promocoes_recebidas
    )

@app.route("/promocoes")
def get_promocoes():
    return jsonify(promocoes=promocoes_recebidas)

@app.route("/pagar/<reserva_id>")
def pagar(reserva_id):
    return f'''
    <h2>Pagamento Fake - Reserva {reserva_id}</h2>
    <p>Simulação de página de pagamento</p>
    <button onclick="window.history.back()">Voltar</button>
    '''

if __name__ == "__main__":
    app.run(port=5000)