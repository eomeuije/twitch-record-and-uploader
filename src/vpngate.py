import requests
import tempfile
import subprocess
import base64
import time

class Vpngate():
    path: str

    def __init__(self, country: str) -> None:

        if len(country) == 2:
            i = 6  # short name for country
        elif len(country) > 2:
            i = 5  # long name for country
        else:
            print("Country is too short!")
            exit(1)

        try:
            vpn_data = requests.get("http://www.vpngate.net/api/iphone/").text.replace("\r", "")
            servers = [line.split(",") for line in vpn_data.split("\n")]
            labels = servers[1]
            labels[0] = labels[0][1:]
            servers = [s for s in servers[2:] if len(s) > 1]
        except BaseException:
            print("Cannot get VPN servers data")
            exit(1)

        desired = [s for s in servers if country.lower() in s[i].lower()]
        found = len(desired)
        print("Found " + str(found) + " servers for country " + country)
        if found == 0:
            exit(1)

        supported = [s for s in desired if len(s[-1]) > 0]
        print(str(len(supported)) + " of these servers support OpenVPN")
        # We pick the best servers by score
        winner = sorted(supported, key=lambda s: float(s[2].replace(",", ".")), reverse=True)[0]

        print("\n== Best server ==")
        pairs = list(zip(labels, winner))[:-1]
        for (l, d) in pairs[:4]:
            print(l + ": " + d)
        print(pairs[4][0] + ": " + str(float(pairs[4][1]) / 10 ** 6) + " MBps")
        print("Country: " + pairs[5][1])

        print("\nLaunching VPN...")
        _, self.path = tempfile.mkstemp()

        f = open(self.path, "w")
        f.write(base64.b64decode(winner[-1]).decode())

    def start_vpn(self):
        p = subprocess.Popen(
            ["openvpn", "--config", self.path]
            , stdout=subprocess.PIPE
        )
        #Route addition via IPAPI succeeded
        
        while p.poll() == None:
            out = p.stdout.readline()
            print(out)
            try:
                if 'Route addition via IPAPI succeeded' in out.decode('utf-8'):
                    break
            except UnicodeDecodeError:
                pass
            time.sleep(0.1)
        return p