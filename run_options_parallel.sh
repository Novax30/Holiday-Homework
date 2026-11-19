#!/bin/bash
# Parallel runner: OPTIONS_TERM_STRUCTURE only
cd /Users/nova/Documents/ALPAHA
exec python3 grandmaster_alpha_engine.py \
  --themes OPTIONS_TERM_STRUCTURE \
  --concurrency 3 \
  --submit-limit 4
