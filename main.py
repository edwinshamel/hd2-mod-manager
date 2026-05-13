#!/usr/bin/env python3
import sys
import os

# Asegurar que el directorio del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui import HD2ModManagerApp

if __name__ == "__main__":
    app = HD2ModManagerApp()
    app.run(sys.argv)
