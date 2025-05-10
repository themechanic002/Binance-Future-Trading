import requests

external_ip = requests.get("http://checkip.amazonaws.com/").text.strip()
print("외부 IP 주소:", external_ip)
