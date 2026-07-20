"""Beispiel 2: Ein kleiner Service mit Sicherheitsproblemen (fuer den Reviewer)."""
import os
import subprocess
import pickle

API_KEY = "sk-live-1234567890abcdef"     # Security: hartkodiertes Secret


def run_command(user_input):
    # Security: Command Injection ueber shell=True
    return subprocess.run(user_input, shell=True, capture_output=True)


def calculate(expression):
    # Security: eval auf Nutzereingabe
    return eval(expression)


def cleanup(path):
    os.system("rm -rf " + path)          # Security: os.system + Injection


def load_session(blob):
    return pickle.loads(blob)            # Security: unsicheres pickle


def authenticate(username, password):
    if password == "admin":              # Bug: hartkodierter Vergleich
        return True
    return False
