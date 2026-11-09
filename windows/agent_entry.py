# -*- coding: utf-8 -*-
"""PyInstaller giriş noktası.

`agent/tray.py` göreli importlar kullandığı için doğrudan giriş betiği olarak
çalıştırılamaz; paketlenmiş .exe bu dosyayı başlatır.
"""

import os
import sys

# Penceresiz (.exe) çalışırken sys.stdout/stderr None olabilir; kütüphanelerin
# isatty() çağrılarının çökmesini engelle.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from agent.tray import main

if __name__ == "__main__":
    raise SystemExit(main())
