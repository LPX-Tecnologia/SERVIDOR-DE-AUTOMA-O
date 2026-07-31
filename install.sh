#!/bin/bash
# ==========================================================
# CLIPADOR - Instalador Automático para Android/Termux
# ==========================================================

echo "🤖 Instalando Servidor de Automação no Celular..."

# Atualiza pacotes
pkg update -y && pkg upgrade -y

# Instala dependências
echo "📦 Instalando Python e dependências..."
pkg install -y python python-pip git wget curl

# Instala bibliotecas Python
echo "📚 Instalando bibliotecas..."
pip install flask flask-cors gunicorn requests Pillow

# Instala Playwright (automação)
echo "🎭 Instalando Playwright..."
pip install playwright

# Instala navegadores
echo "🌐 Instalando Chromium..."
playwright install chromium
playwright install-deps chromium

# Cria pasta do app
mkdir -p ~/clipador-server
cd ~/clipador-server

# Baixa o código
echo "📥 Baixando código do servidor..."
curl -o app.py https://raw.githubusercontent.com/LPX-Tecnologia/clipador-server/main/app.py
curl -o requirements.txt https://raw.githubusercontent.com/LPX-Tecnologia/clipador-server/main/requirements.txt

echo ""
echo "✅ INSTALAÇÃO CONCLUÍDA!"
echo ""
echo "🚀 Para iniciar o servidor, execute:"
echo "   cd ~/clipador-server"
echo "   python app.py"
echo ""
echo "📱 Acesse: http://localhost:5000"
