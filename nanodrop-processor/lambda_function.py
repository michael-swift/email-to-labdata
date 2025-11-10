"""
Root-level import shim for lambda_function.

This allows tests to import lambda_function from the root directory
while the actual implementation lives in src/lambda_function.py.
"""

from src.lambda_function import *
