#!/bin/bash
# Basic if statement
if ! pgrep -f app.py
then
echo Hey Python file not running.
cd ~/hoomaluo-pi-pm/src
python3 app.py > test.out &
fi
