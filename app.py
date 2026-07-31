from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
import subprocess
import socket
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

app = Flask(__name__)
CORS(app)

# ===== CONFIGURAÇÕES =====
DEVICE_NAME = os.environ.get('DEVICE_NAME', 'Celular-01')
DEVICE_RAM = os.environ.get('DEVICE_RAM', '4GB')
MAX_TELAS = int(os.environ.get('MAX_TELAS', '5'))
PORT = int(os.environ.get('PORT', '5000'))

# ===== BANCO LOCAL =====
DB_FILE = 'dados.json'

def carregar():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {"contas": [], "automacoes": [], "historico": []}

def salvar(dados):
    with open(DB_FILE, 'w') as f:
        json.dump(dados, f, indent=2)

# ===== STATUS DO DISPOSITIVO =====
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "dispositivo": DEVICE_NAME,
        "ram": DEVICE_RAM,
        "max_telas": MAX_TELAS,
        "ip": get_ip(),
        "status": "online",
        "api": "Clipador - Servidor de Automação Mobile"
    })

@app.route('/api/status', methods=['GET'])
def status():
    """Status detalhado do dispositivo"""
    mem = get_memory_info()
    return jsonify({
        "dispositivo": DEVICE_NAME,
        "ram_total": mem['total'],
        "ram_livre": mem['free'],
        "ram_usada": mem['used'],
        "telas_ativas": len(threading.enumerate()) - 1,
        "max_telas": MAX_TELAS,
        "cpu": get_cpu_usage(),
        "uptime": get_uptime()
    })

# ===== CONTAS =====
@app.route('/api/contas', methods=['GET'])
def listar_contas():
    dados = carregar()
    return jsonify({"total": len(dados['contas']), "contas": dados['contas']})

@app.route('/api/contas', methods=['POST'])
def adicionar_contas():
    data = request.json
    novas = data.get('contas', [])
    dados = carregar()
    
    for c in novas:
        c['id'] = len(dados['contas']) + 1
        c['status'] = 'ativa'
        dados['contas'].append(c)
    
    salvar(dados)
    return jsonify({"adicionadas": len(novas)}), 201

# ===== AUTOMAÇÃO =====
@app.route('/api/automacao/criar', methods=['POST'])
def criar_automacao():
    data = request.json
    dados = carregar()
    
    auto = {
        "id": len(dados['automacoes']) + 1,
        "nome": data.get('nome', 'Automação'),
        "url_alvo": data.get('url_alvo', ''),
        "passos": data.get('passos', []),
        "criada_em": str(datetime.now())
    }
    
    dados['automacoes'].append(auto)
    salvar(dados)
    return jsonify(auto), 201

@app.route('/api/automacao/executar', methods=['POST'])
def executar():
    data = request.json
    auto_id = data.get('automacao_id')
    qtd = min(data.get('quantidade_telas', 1), MAX_TELAS)
    
    dados = carregar()
    auto = next((a for a in dados['automacoes'] if a['id'] == auto_id), None)
    
    if not auto:
        return jsonify({"erro": "Automação não encontrada"}), 404
    
    contas_ativas = [c for c in dados['contas'] if c.get('status') == 'ativa']
    
    if len(contas_ativas) < qtd:
        return jsonify({"erro": f"Contas insuficientes. Você tem {len(contas_ativas)}."}), 400
    
    selecionadas = contas_ativas[:qtd]
    exec_id = str(int(time.time()))
    
    # Executa em background
    import threading
    thread = threading.Thread(target=executar_telas, args=(exec_id, auto, selecionadas, dados))
    thread.start()
    
    return jsonify({
        "execucao_id": exec_id,
        "dispositivo": DEVICE_NAME,
        "total_telas": qtd,
        "contas": [c['email'] for c in selecionadas]
    })

def executar_telas(exec_id, auto, contas, dados):
    """Executa automação nas telas"""
    resultados = []
    
    for i, conta in enumerate(contas):
        try:
            res = executar_uma_tela(auto, conta, i+1)
            resultados.append(res)
        except Exception as e:
            resultados.append({"tela": i+1, "erro": str(e)})
    
    dados['historico'].append({
        "exec_id": exec_id,
        "automacao": auto['nome'],
        "resultados": resultados,
        "data": str(datetime.now())
    })
    salvar(dados)

def executar_uma_tela(auto, conta, num):
    """Executa UMA tela de automação"""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 375, 'height': 812})
            page.goto(auto['url_alvo'], wait_until='networkidle')
            
            for passo in auto.get('passos', []):
                acao = passo.get('acao')
                sel = passo.get('seletor', '')
                val = passo.get('valor', '')
                
                # Substitui variáveis
                if '{{' in val:
                    val = val.replace('{{email}}', conta.get('email', ''))
                    val = val.replace('{{senha}}', conta.get('senha', ''))
                
                if acao == 'clicar':
                    page.click(sel)
                elif acao == 'preencher':
                    page.fill(sel, val)
                elif acao == 'esperar':
                    page.wait_for_timeout(int(val))
                elif acao == 'navegar':
                    page.goto(val)
                
                page.wait_for_timeout(500)
            
            browser.close()
            return {"tela": num, "conta": conta['email'], "sucesso": True}
    except Exception as e:
        return {"tela": num, "conta": conta['email'], "sucesso": False, "erro": str(e)}

@app.route('/api/historico', methods=['GET'])
def historico():
    dados = carregar()
    return jsonify(dados['historico'][-20:])

# ===== FUNÇÕES AUXILIARES =====
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

def get_memory_info():
    try:
        result = subprocess.run(['free', '-m'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        mem = lines[1].split()
        return {'total': mem[1], 'used': mem[2], 'free': mem[3]}
    except:
        return {'total': 'N/A', 'used': 'N/A', 'free': 'N/A'}

def get_cpu_usage():
    try:
        result = subprocess.run(['top', '-bn1'], capture_output=True, text=True)
        return result.stdout.split('\n')[2][:50] if result.stdout else 'N/A'
    except:
        return 'N/A'

def get_uptime():
    try:
        result = subprocess.run(['uptime'], capture_output=True, text=True)
        return result.stdout.strip()
    except:
        return 'N/A'

if __name__ == '__main__':
    print(f"🤖 {DEVICE_NAME} rodando em http://0.0.0.0:{PORT}")
    print(f"📊 RAM: {DEVICE_RAM} | Máx Telas: {MAX_TELAS}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
