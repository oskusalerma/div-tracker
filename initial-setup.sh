#!/bin/bash

virtualenv venv
. venv/bin/activate
pip install -U pip
pip install Django
pip install -r requirements.txt
