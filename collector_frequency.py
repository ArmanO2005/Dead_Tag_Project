import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
import numpy as np
import re
import json


with open('credentials.json') as f:
    creds = json.load(f)

username = creds['username']
password = creds['password']

output = []
root = "https://ucbg.collectionspace.org/cspace-services"

i = 0
while True:
    try:
        url = (f"https://ucbg.collectionspace.org/cspace-services/collectionobjects/?pgSz=3000&pgNum={i}")
        response = requests.get(url, auth=HTTPBasicAuth(username, password))
        if response.status_code == 200:
            if re.findall(r"<itemsInPage>(.*?)</itemsInPage>", response.text)[0] == '0':
                break
            urlList = re.findall(r"<uri>(.*?)</uri>", response.text)
            for path in urlList:
                sURL = root + path
                object = requests.get(sURL, auth=HTTPBasicAuth(username, password))
                subs = re.findall(r"<fieldCollector>(.*?)</fieldCollector>", object.text)
                if subs:
                    subs = subs[0]
                    authorName = re.findall(r"'(.+)'", subs)[0]
                    output.append(authorName)
                    print(authorName)
        else:
            print(f"Failed to fetch page {i}: {response.status_code}")
            break
        print(i)
        i += 1
    except:
        break


output = pd.Series(output)
output.value_counts().to_csv("CollectorFrequency.csv", header=False)