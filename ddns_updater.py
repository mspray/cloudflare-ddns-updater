import requests
import time
import logging
import configparser as module
from concurrent.futures import ThreadPoolExecutor

config = module.ConfigParser()
config.read('config.cfg')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
file_handler = logging.FileHandler('DDNS_updater.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

max_workers = config.getint('APP CONFIGURATION', 'max_workers')
cloudflare_token_key = config.get('CLOUDFLARE API CONFIGURATION', 'cloudflare_token_key')
zone = config.get('DNS CONFIGURATION', 'zone')
dns_records_string = config.get('DNS CONFIGURATION', 'records')
dns_records_list = [record.strip() for record in dns_records_string.split(',')]
dnsrecords = [{"entry": record, "updated": None} for record in dns_records_list]

def make_cloudflare_request(method, url, data=None): 
    headers = {
        "Authorization": f"Bearer {cloudflare_token_key}",
        "Content-Type": "application/json"
    }
    response = requests.request(method, url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def get_dns_ipv4(zoneid, entry):
    dnsrecordid = get_dns_record_id(zoneid, entry)
    record = get_dns_record(zoneid, dnsrecordid)
    return record["content"]

def get_current_ipv4(): # Using external services to get the public IPv4 address
    urls = ["https://icanhazip.com", "https://ipinfo.io/ip", "https://checkip.amazonaws.com"]
    for url in urls:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                ipv4 = response.text.strip()
                return ipv4
        except requests.exceptions.RequestException:
            logger.error("Can't retrieve public IPv4 address for url: %s", url)
            pass

# def get_current_ipv4(): # Using external services to get the public IPv4 address
#     ipv4 = "109.25.16.110"
#     return ipv4

def get_zone_id(zone):
    url = f"https://api.cloudflare.com/client/v4/zones?name={zone}"
    response = make_cloudflare_request("GET", url)
    zoneid = response["result"][0]["id"]
    return zoneid

def get_dns_record_id(zoneid, entry):
    url = f"https://api.cloudflare.com/client/v4/zones/{zoneid}/dns_records?type=A&name={entry}"
    response = make_cloudflare_request("GET", url)
    dnsrecordid = response["result"][0]["id"]
    return dnsrecordid

def get_dns_record(zoneid, dnsrecordid):
    url = f"https://api.cloudflare.com/client/v4/zones/{zoneid}/dns_records/{dnsrecordid}"
    response = make_cloudflare_request("GET", url)
    record = response["result"]
    return record

def update_dns_record(zoneid, dnsrecord, ipv4):
    dnsrecordid = get_dns_record_id(zoneid, dnsrecord['entry'])
    url = f"https://api.cloudflare.com/client/v4/zones/{zoneid}/dns_records/{dnsrecordid}"
    data = {
        "type": "A",
        "name": dnsrecord['entry'],
        "content": ipv4,
        "ttl": 1,
        "proxied": False
    }
    make_cloudflare_request("PUT", url, data)
    dnsrecord["updated"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    logger.info(f"DNS A - {dnsrecord['entry']} updated with new public IPv4: {ipv4}")

def launch_update_if_needed():
    try:
        zoneid = get_zone_id(zone)
        dns_ipv4 = get_dns_ipv4(zoneid, dnsrecords[0]['entry'])
        current_ipv4 = get_current_ipv4()
    except Exception as e:
        logger.error("Verify zone/records in your config file. Error: %s", str(e))
        return

    if dns_ipv4 == current_ipv4:
        logger.info("DNS records are already up to date. No need for update") 
        return
    elif not current_ipv4:
        logger.warning("Public IPv4 address is not available. Verify your network configuration !")
        return
    else:
        with ThreadPoolExecutor(max_workers) as executor:
            executor.map(lambda dnsrecord: update_dns_record(zoneid, dnsrecord, current_ipv4), dnsrecords)

try:
    launch_update_if_needed()
except Exception as e:
    error_message = "Unexpected error : {}".format(str(e))
    logger.error(error_message)
