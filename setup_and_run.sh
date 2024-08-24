#!/bin/bash

echo "Updating translations..."
./update_translations.sh

echo "Installing Chrome and ChromeDriver..."

# Install Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list'
apt-get update
apt-get install -y google-chrome-stable

# Install ChromeDriver
wget -O /app/chromedriver_linux64.zip https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip
unzip /app/chromedriver_linux64.zip -d /app/chromedriver
rm /app/chromedriver_linux64.zip
chmod +x /app/chromedriver/chromedriver

# Set the Chrome binary location
export CHROME_BIN=/usr/bin/google-chrome
export PATH=$PATH:/app/chromedriver

echo "Starting the bot..."
python bot.py
