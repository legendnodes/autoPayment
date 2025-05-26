#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

# Run the payout checker using Python 3
/usr/bin/python3 payoutApp.py >> payout_cron.log 2>&1
