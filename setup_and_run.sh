#!/bin/bash

# Update translations if needed
echo "Updating translations..."
./update_translations.sh

# Start your application or bot
echo "Starting the bot..."
python3 bot.py
