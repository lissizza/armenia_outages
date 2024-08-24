#!/bin/bash

# Update translations if needed
echo "Updating translations..."
./update_translations.sh

# Install Chrome and ChromeDriver if not already installed
echo "Installing Chrome and ChromeDriver..."

# Try to find Chrome binary
CHROME_BINARY=$(which google-chrome || which google-chrome-stable || echo "")

if [ -z "$CHROME_BINARY" ]; then
  echo "Google Chrome not found, installing..."
  # Commands to install Chrome
  wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
  sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list'
  sudo apt-get -y update
  sudo apt-get -y install google-chrome-stable
  CHROME_BINARY=$(which google-chrome || which google-chrome-stable || echo "")
else
  echo "Google Chrome found at: $CHROME_BINARY"
fi

# Set the CHROME_BINARY_PATH environment variable
export CHROME_BINARY_PATH=$CHROME_BINARY
export PATH=$PATH:/app/chromedriver

# Log the set path
echo "CHROME_BINARY_PATH set to: $CHROME_BINARY_PATH"

# Set permissions for ChromeDriver
chmod +x /app/chromedriver/chromedriver

# Start your application or bot
echo "Starting the bot..."
python3 bot.py
