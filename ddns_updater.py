import requests
import time
from concurrent.futures import ThreadPoolExecutor

class DDNSUpdater:
    def __init__(self, max_workers, token, zone, dns_records_str, ip_scanner_str, logger=None):
        self.logger = logger
        self.max_workers = max_workers
        self.cloudflare_token_key = token
        self.zone = zone
        self.external_ip_scanner_list = [scanner.strip() 
                                         for scanner in ip_scanner_str.split(',')]
        self.dns_records_list = [record.strip()
                                 for record in dns_records_str.split(',')]
        self.dnsrecords = [{"entry": record, "updated": None}
                           for record in self.dns_records_list]

    def make_cloudflare_request(self, method, url, data=None):
        headers = {
            "Authorization": f"Bearer {self.cloudflare_token_key}",
            "Content-Type": "application/json"
        }
        response = requests.request(method, url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()

    def get_current_ipv4(self): 
        urls = self.external_ip_scanner_list
        for url in urls:
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    ipv4 = response.text.strip()
                    return ipv4
            except requests.exceptions.RequestException:
                self.logger.error("Can't retrieve public IPv4 address for url: %s", url)
                pass

    def get_dns_ipv4(self, zoneid, record):
        dnsrecordid = self.get_dns_record_id(zoneid, record)
        record = self.get_dns_record(zoneid, dnsrecordid)
        return record["content"]

    def get_zone_id(self, zone):
        url = f"https://api.cloudflare.com/client/v4/zones?name={zone}"
        response = self.make_cloudflare_request("GET", url)
        zoneid = response["result"][0]["id"]
        return zoneid

    def get_dns_record_id(self, zoneid, record):
        url = f"https://api.cloudflare.com/client/v4/zones/{zoneid}/dns_records?type=A&name={record}"
        response = self.make_cloudflare_request("GET", url)
        dnsrecordid = response["result"][0]["id"]
        return dnsrecordid

    def get_dns_record(self, zoneid, dnsrecordid):
        url = f"https://api.cloudflare.com/client/v4/zones/{zoneid}/dns_records/{dnsrecordid}"
        response = self.make_cloudflare_request("GET", url)
        record = response["result"]
        return record

    def update_dns_record(self, zoneid, dnsrecord, ipv4):
        dnsrecordid = self.get_dns_record_id(zoneid, dnsrecord['entry'])
        url = f"https://api.cloudflare.com/client/v4/zones/{zoneid}/dns_records/{dnsrecordid}"
        data = {
            "type": "A",
            "name": dnsrecord['entry'],
            "content": ipv4,
            "ttl": 1,
            "proxied": False
        }
        self.make_cloudflare_request("PUT", url, data)
        dnsrecord["updated"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.logger.info(f"DNS A - {dnsrecord['entry']} updated with new public IPv4: {ipv4}")

    def launch_update_if_needed(self):
        try:
            zoneid = self.get_zone_id(self.zone)
            dns_ipv4 = self.get_dns_ipv4(zoneid, self.dns_records_list[0])
            current_ipv4 = self.get_current_ipv4()
        except Exception as e:
            self.logger.error("Verify zone/records in your config file. Error: %s", str(e))
            return

        if dns_ipv4 == current_ipv4:
            self.logger.info("DNS records are already up to date. No need for update")
            return
        elif not current_ipv4:
            self.logger.error("Public IPv4 address is not available. Verify your network configuration !")
            return
        else:
            with ThreadPoolExecutor(self.max_workers, thread_name_prefix="SubThread") as executor:
                executor.map(lambda dnsrecord: self.update_dns_record(zoneid, dnsrecord, current_ipv4), self.dnsrecords)
