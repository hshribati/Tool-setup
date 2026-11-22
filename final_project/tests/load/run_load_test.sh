#!/bin/bash

python -m locust \
  -f tests/load/locustfile.py \
  --headless \
  --users 10 \
  --spawn-rate 2 \
  --run-time 1m \
  --host "$1" \
  --csv tests/load/results
