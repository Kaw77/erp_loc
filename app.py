from flask import Flask, request, jsonify, session, send_file
from flask_cors import CORS
import os
import uuid
import json
from datetime import datetime
from database import *
from auth import hash_senha, verificar_senha
from ofxparse import OfxParser

app = Flask(__name__, static_folder='static')
app.secret_key = 'troque-por-uma-chave-secreta-forte'
CORS(app, origins=['http://localhost:5000', 'http://127.0.0.1:5000'], supports_credentials=True)

init_db()

# --- Rotas de autenticação ---
@app.route('/api/login', methods=['POST'])
def login():
    dados = request.json
    usuario = buscar_usuario_por_login(dados.get('login', ''))
    if usuario and verificar_senha(dados.get('senha', ''), usuario['senha_hash']):
        session['user_id'] = usuario['id']
        session['user_login'] = usuario['login']
        session['user_perfil'] = usuario['perfil']
        return jsonify({'ok': True, 'perfil': usuario['perfil']})
    return jsonify({'ok': False}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/current_user', methods=['GET'])
def current_user():
    if 'user_id' in session:
        return jsonify({'login': session['user_login'], 'perfil': session['user_perfil']})
    return jsonify({'ok': False}), 401

# --- Rotas placas ---
@app.route('/api/placas', methods=['GET'])
def get_placas():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado'}), 401
    placas = [dict(row) for row in listar_placas()]
    return jsonify(placas)

@app.route('/api/placas', methods=['POST'])
def post_placa():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado'}), 401
    placa = request.json
    # Validações simples
    if not placa.get('renavam') or not placa.get('modelo') or not placa.get('placa'):
        return jsonify({'ok': False, 'erro': 'Dados incompletos'}), 400
    # Verifica duplicidade (opcional)
    salvar_placa(placa)
    return jsonify({'ok': True})

@app.route('/api/placas/<renavam>', methods=['DELETE'])
def delete_placa(renavam):
    if 'user_id' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado'}), 401
    excluir_placa(renavam)
    return jsonify({'ok': True})

# --- Rotas clientes ---
@app.route('/api/clientes', methods=['GET'])
def get_clientes():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado'}), 401
    clientes = [dict(row) for row in listar_clientes()]
    return jsonify(clientes)

@app.route('/api/clientes', methods=['POST'])
def post_cliente():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado'}), 401
    cliente = request.json
    if not cliente.get('contrato') or not cliente.get('nome'):
        return jsonify({'ok': False, 'erro': 'Contrato e nome são obrigatórios'}), 400
    salvar_cliente(cliente)
    return jsonify({'ok': True})

@app.route('/api/clientes/<contrato>', methods=['DELETE'])
def delete_cliente(contrato):
    if 'user_id' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado'}), 401
    excluir_cliente(contrato)
    return jsonify({'ok': True})

# --- Rotas usuários (apenas admin) ---
@app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    if 'user_id' not in session or session.get('user_perfil') != 'admin':
        return jsonify({'ok': False, 'erro': 'Acesso negado'}), 403
    usuarios = [dict(row) for row in listar_usuarios()]
    # Remove hashes para não expor
    for u in usuarios:
        u.pop('senha_hash', None)
    return jsonify(usuarios)

@app.route('/api/usuarios', methods=['POST'])
def post_usuario():
    if 'user_id' not in session or session.get('user_perfil') != 'admin':
        return jsonify({'ok': False, 'erro': 'Acesso negado'}), 403
    dados = request.json
    if not dados.get('login') or not dados.get('nome') or not dados.get('senha'):
        return jsonify({'ok': False, 'erro': 'Dados incompletos'}), 400
    dados['senha_hash'] = hash_senha(dados.pop('senha'))
    dados['id'] = 'u_' + uuid.uuid4().hex[:8]
    salvar_usuario(dados)
    return jsonify({'ok': True})

@app.route('/api/usuarios/<login>', methods=['DELETE'])
def delete_usuario(login):
    if 'user_id' not in session or session.get('user_perfil') != 'admin':
        return jsonify({'ok': False, 'erro': 'Acesso negado'}), 403
    if login == 'admin':
        return jsonify({'ok': False, 'erro': 'Não pode excluir o admin padrão'}), 400
    excluir_usuario(login)
    return jsonify({'ok': True})

# --- Rotas documentos (PDF) ---
@app.route('/api/documentos', methods=['GET'])
def get_documentos():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado'}), 401
    renavam = request.args.get('renavam')
    if renavam:
        docs = listar_documentos_por_renavam(renavam)
    else:
        docs = listar_todos_documentos()
    return jsonify([dict(row) for row in docs])

@app.route('/api/documentos/upload', methods=['POST'])
def upload_documento():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado'}), 401
    renavam = request.form.get('renavam')
    arquivo = request.files.get('pdf')
    if not renavam or not arquivo:
        return jsonify({'ok': False, 'erro': 'Dados incompletos'}), 400
    # Valida extensão
    if not arquivo.filename.lower().endswith('.pdf'):
        return jsonify({'ok': False, 'erro': 'Apenas PDF'}), 400
    # Cria pastas
    pasta = os.path.join('uploads', renavam)
    os.makedirs(pasta, exist_ok=True)
    nome_seguro = f"{uuid.uuid4().hex}_{arquivo.filename}"
    caminho = os.path.join(pasta, nome_seguro)
    arquivo.save(caminho)
    doc_id = 'doc_' + uuid.uuid4().hex
    doc = {
        'id': doc_id,
        'renavam': renavam,
        'nome_arquivo': arquivo.filename,
        'tamanho': os.path.getsize(caminho),
        'tipo': 'application/pdf',
        'caminho': caminho
    }
    salvar_documento(doc)
    return jsonify({'ok': True, 'id': doc_id})

@app.route('/api/documentos/<doc_id>', methods=['GET'])
def get_documento(doc_id):
    if 'user_id' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado'}), 401
    doc = buscar_documento_por_id(doc_id)
    if not doc:
        return jsonify({'ok': False, 'erro': 'Não encontrado'}), 404
    return send_file(doc['caminho'], mimetype='application/pdf')

@app.route('/api/documentos/<doc_id>', methods=['DELETE'])
def delete_documento(doc_id):
    if 'user_id' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado'}), 401
    excluir_documento_por_id(doc_id)
    return jsonify({'ok': True})

# --- Rota para parser OFX (financeiro) ---
@app.route('/api/parse_ofx', methods=['POST'])
def parse_ofx():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'erro': 'Não autorizado'}), 401
    arquivo = request.files.get('ofx')
    if not arquivo:
        return jsonify({'ok': False, 'erro': 'Arquivo não enviado'}), 400
    try:
        ofx = OfxParser.parse(arquivo.stream)
        transacoes = []
        for conta in ofx.accounts:
            for t in conta.statement.transactions:
                transacoes.append({
                    'data': t.date.isoformat() if t.date else '',
                    'valor': float(t.amount),
                    'descricao': t.memo,
                    'tipo': t.type
                })
        return jsonify(transacoes)
    except Exception as e:
        return jsonify({'ok': False, 'erro': str(e)}), 500

# Rota raiz serve o frontend
@app.route('/')
def index():
    return app.send_static_file('index.html')

if __name__ == '__main__':
    # Cria pasta uploads se não existir
    os.makedirs('uploads', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)