import os
import sys
import time
import logging
import requests
from substrateinterface import SubstrateInterface, Keypair

# === LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('payout.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def log(msg, level='info'):
    getattr(logging, level)(msg)

# === TELEGRAM ===
def send_telegram(msg, config):
    bot_token = config.get('bot_token')
    chat_id = config.get('chat_id')
    if not bot_token or not chat_id or bot_token == 'none' or chat_id == 'none':
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown'}
        )
    except Exception as e:
        log(f"Failed to send Telegram message: {e}", 'error')

def should_notify(mode, is_success):
    if mode == 'all':
        return True
    elif mode == 'success' and is_success:
        return True
    elif mode == 'failed' and not is_success:
        return True
    return False

# === CONFIG LOADING ===
def load_description():
    config = {}
    with open('description', 'r') as f:
        for line in f:
            if not line.strip() or line.startswith('#'):
                continue
            key, val = line.strip().split('=', 1)
            config[key.strip()] = val.strip()
    config['validators'] = [v.strip() for v in config['validators'].split(',') if v.strip()]
    config['num_eras'] = int(config.get('num_eras', 4))
    config.setdefault('bot_token', 'none')
    config.setdefault('chat_id', 'none')
    config['notification_mode'] = config.get('notification_mode', 'all').lower()
    return config

def load_seed(network):
    seed_file = f".{network}"
    if not os.path.exists(seed_file):
        raise FileNotFoundError(f"Seed file {seed_file} not found.")
    with open(seed_file, 'r') as f:
        return f.read().strip()

# === BLOCKCHAIN FUNCTIONS ===
def connect(network):
    url = "wss://rpc.polkadot.io" if network == 'polkadot' else "wss://kusama-rpc.polkadot.io"
    return SubstrateInterface(url=url, type_registry_preset=network)

def get_current_era(substrate):
    return substrate.query('Staking', 'ActiveEra').value['index']

def check_unclaimed_rewards(substrate, stash, era):
    claimed = substrate.query('Staking', 'ClaimedRewards', [era, stash]).value or []
    exposure = substrate.query('Staking', 'ErasStakersOverview', [era, stash]).value
    if not exposure or 'page_count' not in exposure:
        return []
    return [i for i in range(exposure['page_count']) if i not in claimed]

def payout_era(substrate, keypair, validator_stash, era):
    call = substrate.compose_call(
        call_module='Staking',
        call_function='payout_stakers',
        call_params={'validator_stash': validator_stash, 'era': era}
    )
    extrinsic = substrate.create_signed_extrinsic(call=call, keypair=keypair)
    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    log(f"✅ Payout for {validator_stash} in era {era}: {receipt.extrinsic_hash}")
    return receipt

def short_address(address):
    return f"*{address[:6]}...{address[-5:]}*"

# === VALIDATOR LOGIC ===
def process_validator(substrate, keypair, stash, num_eras, config):
    current_era = get_current_era(substrate)
    all_claimed_eras = []

    identity = short_address(stash)

    for era in range(current_era - num_eras, current_era):
        unclaimed = check_unclaimed_rewards(substrate, stash, era)
        if unclaimed:
            try:
                receipt = payout_era(substrate, keypair, stash, era)
                era_msg = f"✅ *era {era}* - Payout successfully executed for {identity}"
                sender_short = short_address(keypair.ss58_address)
                sender_url = f"https://{config['network']}.subscan.io/account/{keypair.ss58_address}"
                sender_line = f"*Sender:* [{sender_short}]({sender_url})"
                full_msg = f"{era_msg}\n\n{sender_line}"
                log(full_msg)
                if should_notify(config['notification_mode'], is_success=True):
                    send_telegram(full_msg, config)
                time.sleep(6)
            except Exception as e:
                err_msg = f"⚠️ *Payout FAILED* for {identity} in era {era}: {e}"
                log(err_msg, 'error')
                if should_notify(config['notification_mode'], is_success=False):
                    send_telegram(err_msg, config)
        else:
            all_claimed_eras.append(era)

    if all_claimed_eras:
        era_range = f"{all_claimed_eras[0]}–{all_claimed_eras[-1]}" if len(all_claimed_eras) > 1 else str(all_claimed_eras[0])
        msg = f"✅ *era {era_range}* - All rewards already claimed for {identity}"
        log(msg)
        if should_notify(config['notification_mode'], is_success=True):
            send_telegram(msg, config)

# === MAIN ===
def main():
    config = load_description()
    seed_phrase = load_seed(config['network'])

    substrate = connect(config['network'])
    keypair = Keypair.create_from_mnemonic(seed_phrase)

    for stash in config['validators']:
        log(f"\n🔍 Checking stash: {stash}")
        process_validator(substrate, keypair, stash, config['num_eras'], config)

if __name__ == "__main__":
    main()
