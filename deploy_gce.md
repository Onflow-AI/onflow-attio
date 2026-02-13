# Deploy Discord Bot to Google Compute Engine (Free Tier)

## Prerequisites
- Google Cloud account with billing enabled (free tier available)
- gcloud CLI installed ([installation guide](https://cloud.google.com/sdk/docs/install))

## Step 1: Create the VM

```bash
# Login to Google Cloud
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Create f1-micro instance (Always Free)
gcloud compute instances create discord-bot \
    --zone=us-west1-b \
    --machine-type=f1-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --tags=discord-bot
```

**Available free tier regions:**
- `us-west1-b` (Oregon)
- `us-central1-a` (Iowa)
- `us-east1-b` (South Carolina)

## Step 2: Upload Your Code

### Option A: Using git (recommended)
```bash
# SSH into the VM
gcloud compute ssh discord-bot --zone=us-west1-b

# Clone your repository
git clone YOUR_GITHUB_REPO_URL ~/discord-bot
cd ~/discord-bot
```

### Option B: Upload files directly
```bash
# From your local machine
gcloud compute scp --recurse ./* discord-bot:~/discord-bot --zone=us-west1-b
```

## Step 3: Run Setup Script

```bash
# SSH into the VM (if not already)
gcloud compute ssh discord-bot --zone=us-west1-b

# Download and run setup script
cd ~/discord-bot
chmod +x setup_gce.sh
./setup_gce.sh
```

The script will:
1. Install Python 3.11
2. Create a virtual environment
3. Install dependencies
4. Set up environment variables
5. Create a systemd service for auto-start
6. Start the bot

## Step 4: Configure Environment Variables

```bash
# Edit the .env file
nano ~/discord-bot/.env
```

Add your keys:
```env
DISCORD_BOT_TOKEN=your_actual_discord_token
GOOGLE_API_KEY=your_actual_google_api_key
ATTIO_API_KEY=your_actual_attio_api_key
LOG_LEVEL=INFO
```

Save and exit (Ctrl+X, then Y, then Enter)

## Step 5: Start the Bot

```bash
# Restart the service with new env vars
sudo systemctl restart discord-bot

# Check status
sudo systemctl status discord-bot

# View logs
sudo journalctl -u discord-bot -f
```

## Useful Commands

### Check bot status
```bash
sudo systemctl status discord-bot
```

### View logs (live)
```bash
sudo journalctl -u discord-bot -f
```

### View recent logs
```bash
sudo journalctl -u discord-bot -n 100
```

### Restart bot
```bash
sudo systemctl restart discord-bot
```

### Stop bot
```bash
sudo systemctl stop discord-bot
```

### Update bot code
```bash
cd ~/discord-bot
git pull
sudo systemctl restart discord-bot
```

## Cost Monitoring

To ensure you stay in the free tier:

```bash
# Check your instance details
gcloud compute instances describe discord-bot --zone=us-west1-b

# View billing
gcloud billing accounts list
```

**Free tier includes:**
- 1 f1-micro instance (0.6GB RAM, shared CPU)
- 30GB standard persistent disk
- 1GB network egress per month

Your bot should easily fit within these limits with 3 requests/day!

## Firewall (if needed)

The bot doesn't need incoming connections, but if you want to add monitoring:

```bash
# Allow HTTP/HTTPS (optional)
gcloud compute firewall-rules create allow-http \
    --allow tcp:80,tcp:443 \
    --target-tags discord-bot
```

## Troubleshooting

### Bot not starting?
```bash
# Check logs for errors
sudo journalctl -u discord-bot -n 50 --no-pager

# Check Python errors
cd ~/discord-bot
source venv/bin/activate
python bot.py
```

### Out of memory?
f1-micro has limited RAM. If you get OOM errors:
```bash
# Add swap space
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Update Python dependencies
```bash
cd ~/discord-bot
source venv/bin/activate
pip install --upgrade -r requirements.txt
sudo systemctl restart discord-bot
```

## Cleanup (if you want to delete everything)

```bash
# Delete the VM
gcloud compute instances delete discord-bot --zone=us-west1-b
```
