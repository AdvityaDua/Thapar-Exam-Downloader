# wsgi.py
import sys
import os

# Make sure Python can find your project files
sys.path.insert(0, os.path.dirname(__file__))

from main import app as application