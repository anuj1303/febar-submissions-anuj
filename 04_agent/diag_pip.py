# Databricks notebook source
import subprocess, sys
# capture the real pip error (verbose), installing the agent stack
r = subprocess.run(
    [sys.executable, "-m", "pip", "install", "databricks-langchain", "langgraph",
     "unitycatalog-langchain[databricks]", "databricks-agents"],
    capture_output=True, text=True)
print("RETURNCODE:", r.returncode)
print("=== STDOUT tail ==="); print(r.stdout[-2500:])
print("=== STDERR tail ==="); print(r.stderr[-3000:])
