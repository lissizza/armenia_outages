#!/bin/bash

# Extract messages from the code
pybabel extract -F babel.cfg -o locales/messages.pot .

# Update the .po files with metadata
pybabel update -i locales/messages.pot -d locales

# Compile the .po files to .mo files
pybabel compile -d locales

