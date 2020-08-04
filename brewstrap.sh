#!/bin/bash

# Perform all setup tasks on OSX.
# Use: ./brewstrap.sh

set -eux

brew bundle --no-lock
pyenv install -s 3.8.3
