#!/bin/bash

# Update translations
echo "Updating translations..."
./update_translations.sh

# Install Chrome and ChromeDriver
echo "Installing Chrome and ChromeDriver..."

# Download and install Google Chrome
echo "Downloading and installing Google Chrome..."
wget -O /app/google-chrome-stable_current_amd64.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i /app/google-chrome-stable_current_amd64.deb || sudo apt-get -fy install

# Check where Google Chrome is installed and set CHROME_BIN
echo "Checking the location of Google Chrome binary after installation..."
CHROME_BINARY_PATH=$(which google-chrome || which google-chrome-stable)

if [ -n "$CHROME_BINARY_PATH" ]; then
    echo "Google Chrome found at: $CHROME_BINARY_PATH"
    export CHROME_BINARY_PATH="$CHROME_BINARY_PATH"
else
    echo "Google Chrome not found in PATH after installation."
fi

# Download and install ChromeDriver
wget -O /app/chromedriver_linux64.zip https://chromedriver.storage.googleapis.com/114.0.5735.90/chromedriver_linux64.zip
unzip /app/chromedriver_linux64.zip -d /app/chromedriver/

# Make ChromeDriver executable
chmod +x /app/chromedriver/chromedriver

# Update PATH to include ChromeDriver
export PATH=$PATH:/app/chromedriver

# Start the bot or application
echo "Starting the bot..."
python3 bot.py
