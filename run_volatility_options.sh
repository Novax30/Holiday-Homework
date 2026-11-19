#!/bin/bash
# Run Grandmaster Engine on VOLATILITY_CONTRACTION + OPTIONS_TERM_STRUCTURE themes
cd /Users/nova/Documents/ALPAHA
exec python3 grandmaster_alpha_engine.py \
  --themes VOLATILITY_CONTRACTION,OPTIONS_TERM_STRUCTURE \
  --concurrency 3 \
  --submit-limit 4
