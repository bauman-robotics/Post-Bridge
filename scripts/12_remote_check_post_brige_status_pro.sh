#!/bin/bash

# ============================================
# SSH CONNECTION SCRIPT
# ============================================
# Description: Connects to remote server via SSH
#              and executes a script located at
#              specified path on the server
# ============================================

# ---------- CONFIGURATION ----------
# Remote server connection details
REMOTE_USER="root"
REMOTE_HOST="5.187.0.91"
REMOTE_PORT="22"  # Default SSH port

# Path to the script on the remote server
REMOTE_SCRIPT_PATH="/root/Post-Bridge/scripts/11_check_logs_pro.sh"

# Additional SSH options (optional)
SSH_OPTIONS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"
# -----------------------------------

# Check if script path is configured
if [ -z "$REMOTE_SCRIPT_PATH" ]; then
    echo "ERROR: REMOTE_SCRIPT_PATH is not set in the script header."
    exit 1
fi

# Check if remote user/host is configured
if [ -z "$REMOTE_USER" ] || [ -z "$REMOTE_HOST" ]; then
    echo "ERROR: REMOTE_USER or REMOTE_HOST is not set in the script header."
    exit 1
fi

# Display connection info
echo "Connecting to $REMOTE_USER@$REMOTE_HOST:$REMOTE_PORT..."
echo "Executing script: $REMOTE_SCRIPT_PATH"
echo "----------------------------------------"

# Execute the remote script via SSH
# The script output will be displayed directly in the terminal
ssh -p "$REMOTE_PORT" $SSH_OPTIONS "$REMOTE_USER@$REMOTE_HOST" "bash $REMOTE_SCRIPT_PATH"

# Check the exit status of the SSH command
if [ $? -eq 0 ]; then
    echo "----------------------------------------"
    echo "✅ Script executed successfully"
else
    echo "----------------------------------------"
    echo "❌ Script execution failed or SSH connection error"
    exit 1
fi