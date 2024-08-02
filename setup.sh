#!/bin/bash

# Update package list and install necessary packages
sudo apt-get update
sudo apt-get install -y curl autoconf automake build-essential libtool

# Install libpostal
git clone https://github.com/openvenues/libpostal
cd libpostal
./bootstrap.sh
./configure
make
sudo make install
sudo ldconfig
cd ..

# Install Python dependencies
pip install -r requirements.txt
