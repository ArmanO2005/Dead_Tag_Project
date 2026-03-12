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

object_csids = {}
root = "https://ucbg.collectionspace.org/cspace-services"



for i in range(5):
    try:
        url = f"https://ucbg.collectionspace.org/cspace-services/taxonomyauthority/c1662cc5-d458-4788-96ed/items?pgSz=3000&pgNum={i}&as=(collectionspace_core:updatedAt%20%3E=%20TIMESTAMP%20%222026-01-13T00:00:00Z%22)";
        response = requests.get(url, auth=HTTPBasicAuth(username, password))
        if response.status_code == 200:
            if re.findall(r"<itemsInPage>(.*?)</itemsInPage>", response.text)[0] == '0':
                break
            csidList = re.findall(r"<csid>(.*?)</csid>", response.text)
            nameList = re.findall(r"<termDisplayName>(.*?)</termDisplayName>", response.text)
            for j, csid in enumerate(csidList):
                name = nameList[j]
                object_csids[name] = csid
        else:
            print(f"Failed to fetch page {i}: {response.status_code}")
            break
        print(i)
        i += 1
    except:
        print("An error occurred.")
        break

hierarchy_check = pd.DataFrame(columns=['Name', 'Has_Broader', 'Broader_Term'])
rows = []


for name in object_csids:
    print(name)
    url = (f"https://ucbg.collectionspace.org/cspace-services/relations?sbj={object_csids[name]}")

    response = requests.get(url, auth=HTTPBasicAuth(username, password))
    if response.status_code == 200:
        if re.findall(r"<number>(.*?)</number>", response.text) == []:
            rows.append({
                'Name': name,
                'Has_Broader': 'no',
                'Broader_Term': np.nan
                })
        else:
            names = re.findall(r"<number>(.*?)</number>", response.text)
            rows.append({
                'Name': name,
                'Has_Broader': 'yes',
                'Broader_Term': names[1]
                })
            
hierarchy_check = pd.DataFrame(rows)
hierarchy_check.to_csv('prod_taxon_hierarchy_check_nov2025_2.csv', index=False)

#Adenophorus tamariscinus
