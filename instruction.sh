# install dependencies 
sudo apt update
sudo apt install python3 python3-pip -y
pip3 install substrate-interface requests

# download autPayment folder
git clone https://github.com/legendnodes/autoPayment.git

# update service files  
cd autoPayment

# modify description file
nano description

# modify .polkadot file - type inside your 12 words seed
nano .polkadot

# modify .kusama file - type inside your 12 words seed
nano .kusama

# give permission to run_payout file
chmod +x run_payout.sh

# use crontab for auto running - in this exmple, run it at 16:00 UTC every day
crontab -e
# polkadot - 1 payment a day
00 16 * * * /full/path/to/autoPayment/run_payout.sh

# kusama - 4 payments a day
# 45 0,6,12,18 * * * /full/path/to/autoPayment/run_payout.sh 

