import logging
import configparser as module
from ddns_updater import DDNSUpdater

# Init logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
file_handler = logging.FileHandler('DDNS_updater.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.info("DDNS Updater started")

# Load configuration from config.cfg file
config = module.ConfigParser()
config.read('config.cfg')
max_workers = config.getint('APP CONFIGURATION', 'max_workers')
cloudflare_token_key = config.get('CLOUDFLARE API CONFIGURATION', 'cloudflare_token_key')
zone = config.get('DNS CONFIGURATION', 'zone')
dns_records_string = config.get('DNS CONFIGURATION', 'records')
external_ip_scanner_string = config.get('APP CONFIGURATION', 'external_ip_scanner')

# Create instance of DDNSUpdater with configuration settings and logger
if __name__ == "__main__":
    updater = DDNSUpdater(max_workers=max_workers,
                          token=cloudflare_token_key,
                          zone=zone,
                          dns_records_str=dns_records_string,
                          ip_scanner_str=external_ip_scanner_string,
                          logger=logger)
    updater.launch_update_if_needed()
