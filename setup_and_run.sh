#!/bin/bash

# Update translations
echo "Updating translations..."
./update_translations.sh

# Install Chrome and ChromeDriver
echo "Installing Chrome and ChromeDriver..."

# Check where Google Chrome is installed
echo "Checking the location of google-chrome binary..."
which google-chrome || echo "Google Chrome not found in PATH."

# Continue with the rest of your installation
# (Make sure the correct URLs are used for downloading)
wget -O /app/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i /app/google-chrome-stable_current_amd64.deb || sudo apt-get -fy install

wget -O /app/chromedriver_linux64.zip https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip
unzip /app/chromedriver_linux64.zip -d /app/chromedriver/

# Start the bot or application
echo "Starting the bot..."
python3 bot.py
