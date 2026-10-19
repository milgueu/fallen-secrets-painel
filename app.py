from flask import Flask, render_template, request, jsonify
from datetime import datetime
import json
import os
import requests

app = Flask(__name__)

DATA_FILE = 'membros.json'

# Variável global para armazenar o horário da última sincronização
ULTIMA_SINCRONIZACAO = "nunca"

# --- CREDENCIAIS DA API DO WOLVESVILLE ---
API_KEY = "mPNX1W6PEOq87K3qKMAKLOhcvsNISXT3DXWxpntlf5w6OpK5ofBzYPv8pVCbBWmK"
HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bot {API_KEY}"
}

def carregar_dados():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def salvar_dados(dados):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

# --- ROTAS DAS PÁGINAS ---
@app.route('/')
def index_membro():
    return render_template('index.html', modo_admin=False)

@app.route('/admin-secreto')
def index_admin():
    return render_template('index.html', modo_admin=True)

# --- ROTAS DA API ---
@app.route('/api/membros', methods=['GET'])
def api_listar_membros():
    return jsonify(carregar_dados())

@app.route('/api/membros', methods=['POST'])
def api_adicionar_membro():
    data = request.get_json()
    nome = data.get('nome', '').strip()
    
    membros = carregar_dados()
    novo_id = max([m.get('id', 0) for m in membros], default=0) + 1
    
    novo_membro = {
        "id": novo_id,
        "player_id": None,
        "nome": nome,
        "xp_inicial": data.get('xp_inicial', 0),
        "xp_final": data.get('xp_final', 0)
    }
    membros.append(novo_membro)
    salvar_dados(membros)
    return jsonify({"success": True})

@app.route('/api/membros/<int:id_membro>', methods=['PUT'])
def api_atualizar_membro(id_membro):
    data = request.get_json()
    membros = carregar_dados()
    
    for m in membros:
        if m.get('id') == id_membro:
            if 'xp_inicial' in data:
                m['xp_inicial'] = data['xp_inicial']
            if 'xp_final' in data:
                m['xp_final'] = data['xp_final']
            break
            
    salvar_dados(membros)
    return jsonify({"success": True})

@app.route('/api/membros/<int:id_membro>', methods=['DELETE'])
def api_remover_membro(id_membro):
    membros = carregar_dados()
    membros = [m for m in membros if m.get('id') != id_membro]
    salvar_dados(membros)
    return jsonify({"success": True})

@app.route('/api/resetar-mes', methods=['POST'])
def api_resetar_mes():
    membros = carregar_dados()
    for m in membros:
        m['xp_inicial'] = m.get('xp_final', 0)
        m['xp_final'] = 0
    salvar_dados(membros)
    return jsonify({"success": True})

@app.route('/api/ultima-sinc', methods=['GET'])
def api_ultima_sinc():
    return jsonify({"ultima_sinc": ULTIMA_SINCRONIZACAO})

@app.route('/sincronizar', methods=['POST'])
def sincronizar():
    global ULTIMA_SINCRONIZACAO
    membros = carregar_dados()
    
    res_clan = requests.get("https://api.wolvesville.com/clans/authorized", headers=HEADERS)
    if res_clan.status_code != 200:
        return jsonify({"success": False, "message": f"Erro API Wolvesville ({res_clan.status_code}). Verifique a autorização do Bot."}), 400
    
    clans_data = res_clan.json()
    if not clans_data:
        return jsonify({"success": False, "message": "O bot 'bend' ainda não foi detetado num clã ativo."}), 400
    
    clan_id = clans_data[0]["id"]
    
    res_members = requests.get(f"https://api.wolvesville.com/clans/{clan_id}/members/detailed", headers=HEADERS)
    if res_members.status_code != 200:
        return jsonify({"success": False, "message": "Erro ao procurar membros do clã na API."}), 400
        
    membros_api = res_members.json()
    
    by_player_id = {}
    by_username = {}
    
    for m in membros_api:
        p_id = m.get("playerId") or m.get("id")
        username = m.get("username") or m.get("name") or m.get("nick")
        xp = m.get("xp", 0)
        
        info = {"playerId": p_id, "username": username, "xp": xp}
        if p_id:
            by_player_id[p_id] = info
        if username:
            by_username[username.lower()] = info

    membros_atualizados = 0
    nicks_alterados = 0

    for m in membros:
        player_info = None
        
        if m.get("player_id") and m["player_id"] in by_player_id:
            player_info = by_player_id[m["player_id"]]
        elif m.get("nome") and m["nome"].lower() in by_username:
            player_info = by_username[m["nome"].lower()]
            m["player_id"] = player_info["playerId"]

        if player_info:
            if m["nome"].lower() != player_info["username"].lower():
                m["nome"] = player_info["username"]
                nicks_alterados += 1
            
            m["xp_final"] = player_info["xp"]
            membros_atualizados += 1

    salvar_dados(membros)
    
    # Atualiza o horário global da última sincronização
    agora = datetime.now()
    ULTIMA_SINCRONIZACAO = agora.strftime("%d/%m/%Y às %H:%M")
    
    msg = f"Sincronizado! ({membros_atualizados} membros atualizados com XP do jogo)"
    if nicks_alterados > 0:
        msg += f" — 🔄 {nicks_alterados} nick(s) alterado(s) e atualizado(s) no painel!"

    return jsonify({"success": True, "message": msg, "ultima_sinc": ULTIMA_SINCRONIZACAO})

if __name__ == '__main__':
    app.run(debug=True)