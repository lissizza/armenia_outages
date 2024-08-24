#!/bin/bash

# Update translations
echo "Updating translations..."
./update_translations.sh

# Install Chrome for Selenium
echo "Installing Chrome and ChromeDriver..."

# Install dependencies
apt-get update
apt-get install -y wget unzip

# Install Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt-get install -y ./google-chrome-stable_current_amd64.deb

# Install ChromeDriver
CHROMEDRIVER_VERSION=`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`
wget -N https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip -P /app
unzip /app/chromedriver_linux64.zip -d /app/chromedriver
chmod +x /app/chromedriver/chromedriver
export PATH=$PATH:/app/chromedriver

# Start the bot
echo "Starting the bot..."
python bot.py
