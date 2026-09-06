import sqlite3
from datetime import datetime

DB_NAME = 'erp.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                login TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                perfil TEXT NOT NULL,
                status TEXT NOT NULL,
                senha_hash TEXT NOT NULL,
                criado_em TEXT
            );
            CREATE TABLE IF NOT EXISTS placas (
                renavam TEXT PRIMARY KEY,
                modelo TEXT NOT NULL,
                placa TEXT NOT NULL,
                base TEXT NOT NULL,
                status TEXT NOT NULL,
                cliente TEXT,
                cadastro_em TEXT
            );
            CREATE TABLE IF NOT EXISTS clientes (
                contrato TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                cpf TEXT NOT NULL,
                telefone TEXT,
                email TEXT,
                uf TEXT,
                renavam TEXT,
                modelo TEXT,
                placa TEXT,
                base TEXT,
                status TEXT,
                criado_em TEXT
            );
            CREATE TABLE IF NOT EXISTS documentos (
                id TEXT PRIMARY KEY,
                renavam TEXT NOT NULL,
                nome_arquivo TEXT NOT NULL,
                tamanho INTEGER,
                tipo TEXT,
                caminho TEXT,
                enviado_em TEXT,
                FOREIGN KEY(renavam) REFERENCES placas(renavam)
            );
        ''')
        # Inserir usuário admin padrão se não existir
        from auth import hash_senha
        admin = conn.execute('SELECT * FROM usuarios WHERE login = "admin"').fetchone()
        if not admin:
            conn.execute('''
                INSERT INTO usuarios (id, nome, login, email, perfil, status, senha_hash, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('u_admin', 'Administrador', 'admin', 'admin@erploc.com.br', 
                  'admin', 'Ativo', hash_senha('admin123'), datetime.now().isoformat()))

# --- CRUD Placas ---
def listar_placas():
    with get_db() as conn:
        return conn.execute('SELECT * FROM placas ORDER BY base, modelo').fetchall()

def salvar_placa(placa):
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO placas
            (renavam, modelo, placa, base, status, cliente, cadastro_em)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (placa['renavam'], placa['modelo'], placa['placa'], placa['base'],
              placa['status'], placa.get('cliente', ''), placa.get('cadastro_em', datetime.now().isoformat())))
        conn.commit()

def excluir_placa(renavam):
    with get_db() as conn:
        conn.execute('DELETE FROM placas WHERE renavam = ?', (renavam,))
        conn.commit()

# --- CRUD Clientes ---
def listar_clientes():
    with get_db() as conn:
        return conn.execute('SELECT * FROM clientes ORDER BY nome').fetchall()

def salvar_cliente(cliente):
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO clientes
            (contrato, nome, cpf, telefone, email, uf, renavam, modelo, placa, base, status, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (cliente['contrato'], cliente['nome'], cliente['cpf'], cliente['telefone'],
              cliente['email'], cliente['uf'], cliente.get('renavam',''), cliente.get('modelo',''),
              cliente.get('placa',''), cliente.get('base',''), cliente.get('status','DISPONÍVEL'),
              cliente.get('criado_em', datetime.now().isoformat())))
        conn.commit()

def excluir_cliente(contrato):
    with get_db() as conn:
        conn.execute('DELETE FROM clientes WHERE contrato = ?', (contrato,))
        conn.commit()

# --- CRUD Usuários (para administração) ---
def listar_usuarios():
    with get_db() as conn:
        return conn.execute('SELECT * FROM usuarios ORDER BY nome').fetchall()

def buscar_usuario_por_login(login):
    with get_db() as conn:
        return conn.execute('SELECT * FROM usuarios WHERE login = ?', (login,)).fetchone()

def salvar_usuario(usuario):
    with get_db() as conn:
        if 'senha_hash' in usuario:
            conn.execute('''
                INSERT OR REPLACE INTO usuarios
                (id, nome, login, email, perfil, status, senha_hash, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (usuario['id'], usuario['nome'], usuario['login'], usuario['email'],
                  usuario['perfil'], usuario['status'], usuario['senha_hash'], usuario.get('criado_em', datetime.now().isoformat())))
        else:
            conn.execute('''
                UPDATE usuarios SET nome=?, email=?, perfil=?, status=?
                WHERE login = ?
            ''', (usuario['nome'], usuario['email'], usuario['perfil'], usuario['status'], usuario['login']))
        conn.commit()

def excluir_usuario(login):
    with get_db() as conn:
        conn.execute('DELETE FROM usuarios WHERE login = ?', (login,))
        conn.commit()

# --- Documentos ---
def salvar_documento(doc):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO documentos (id, renavam, nome_arquivo, tamanho, tipo, caminho, enviado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (doc['id'], doc['renavam'], doc['nome_arquivo'], doc['tamanho'],
              doc['tipo'], doc['caminho'], doc.get('enviado_em', datetime.now().isoformat())))
        conn.commit()

def listar_documentos_por_renavam(renavam):
    with get_db() as conn:
        return conn.execute('SELECT * FROM documentos WHERE renavam = ?', (renavam,)).fetchall()

def listar_todos_documentos():
    with get_db() as conn:
        return conn.execute('SELECT * FROM documentos').fetchall()

def buscar_documento_por_id(doc_id):
    with get_db() as conn:
        return conn.execute('SELECT * FROM documentos WHERE id = ?', (doc_id,)).fetchone()

def excluir_documento_por_id(doc_id):
    with get_db() as conn:
        doc = buscar_documento_por_id(doc_id)
        if doc:
            import os
            if os.path.exists(doc['caminho']):
                os.remove(doc['caminho'])
        conn.execute('DELETE FROM documentos WHERE id = ?', (doc_id,))
        conn.commit()