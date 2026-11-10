import os

# Tests ohne sichtbare Fenster ausführen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
