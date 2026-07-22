"""
api/index.py — Vercel Serverless Function entry point for EventRadar.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import app
