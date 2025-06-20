import requests
from requests.auth import HTTPBasicAuth
import re

url = "https://ucbg.collectionspace.org/cspace-services/taxonomyauthority"
username = "cyclanthaceae@berkeley.edu"
password = "Arman2005"


response = requests.get(url, auth=HTTPBasicAuth(username, password))

csid = re.search('<csid>(.*?)</csid>', response.text)
print(csid.group(1))