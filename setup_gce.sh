#!/bin/bash
# Setup script for Google Compute Engine
# Run this after SSH-ing into your GCE VM

set -e

echo "=== Discord Bot Setup for GCE ==="

# Update system
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Python 3.11
echo "Installing Python 3.11..."
sudo apt-get install -y python3.11 python3.11-venv python3-pip git

# Create bot directory
echo "Setting up bot directory..."
cd ~
mkdir -p discord-bot
cd discord-bot

# Clone your repository (you'll need to replace this with your repo URL)
echo "Clone your repository manually with:"
echo "git clone YOUR_REPO_URL ."
echo ""
echo "Or upload files manually using: gcloud compute scp"
echo ""
read -p "Press enter after you've added your code files..."

# Create virtual environment
echo "Creating Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file
echo "Creating .env file..."
cat > .env << 'EOF'
DISCORD_BOT_TOKEN=your_discord_token_here
GOOGLE_API_KEY=your_google_api_key_here
ATTIO_API_KEY=your_attio_api_key_here
LOG_LEVEL=INFO
EOF

echo ""
echo "⚠️  IMPORTANT: Edit the .env file with your actual API keys:"
echo "nano .env"
echo ""
read -p "Press enter after you've updated the .env file..."

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/discord-bot.service > /dev/null << EOF
[Unit]
Description=Discord Lead Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/discord-bot
Environment="PATH=$HOME/discord-bot/venv/bin"
ExecStart=$HOME/discord-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
echo "Enabling bot service..."
sudo systemctl daemon-reload
sudo systemctl enable discord-bot
sudo systemctl start discord-bot

echo ""
echo "✅ Setup complete!"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status discord-bot   # Check bot status"
echo "  sudo systemctl restart discord-bot  # Restart bot"
echo "  sudo systemctl stop discord-bot     # Stop bot"
echo "  sudo journalctl -u discord-bot -f   # View logs"
echo ""
echo "To update your bot:"
echo "  cd ~/discord-bot"
echo "  git pull"
echo "  sudo systemctl restart discord-bot"
