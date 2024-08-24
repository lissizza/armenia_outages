#!/bin/bash

# Update translations
echo "Updating translations..."
./update_translations.sh

# Install Chrome for Selenium
echo "Installing Chrome and ChromeDriver..."
CHROME_VERSION="google-chrome-stable"
wget https://dl.google.com/linux/direct/$CHROME_VERSION_current_amd64.deb
apt-get install -y ./google-chrome-stable_current_amd64.deb

CHROMEDRIVER_VERSION=`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`
wget -N https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip -P ~/
unzip ~/chromedriver_linux64.zip -d ~/chromedriver
chmod +x ~/chromedriver/chromedriver
export PATH=$PATH:~/chromedriver

# Start the bot
echo "Starting the bot..."
python bot.py
