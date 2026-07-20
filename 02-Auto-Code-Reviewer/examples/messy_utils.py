"""Beispiel 1: Hilfsfunktionen mit typischen Bugs & Code-Smells (fuer den Reviewer)."""
import os
import json
import math


def add_item(item, items=[]):          # Bug: veraenderliches Default-Argument
    items.append(item)
    return items


def find_user(users, name):
    for u in users:
        if u == None:                  # Style: Vergleich mit None via ==
            continue
        if u.get("name") == name:
            return u
    return None


def parse_config(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except:                            # Bug: nacktes except
        pass                           # Smell: verschluckte Exception


def average(numbers):
    # TODO: leere Liste behandeln
    total = 0
    for n in numbers:
        total += n
    return total / len(numbers)        # Bug: Division durch 0 bei leerer Liste


def check(value):
    assert (value > 0, "value muss positiv sein")   # Bug: assert-Tupel immer wahr
    return math.sqrt(value)
