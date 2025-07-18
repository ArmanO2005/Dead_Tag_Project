import pandas as pd
import numpy as np
import re
from nltk import edit_distance
import math
import string


def TaxonNoAuthor(data, columnName):
    """
    Modifies the dataframe data to contain one new columns:
    ***no_author: the binomial with the author name ommitted
    """
    binomialPattern = (
        r'([A-Z][a-z]+ \'.+\'|[A-Z][a-z]+ aff\. [a-z-]+|'
        r'[A-Z][a-z]+ cf\. [a-z-]+|[A-Z][a-z]+ [a-z-]+)'
    )
    
    additionsPattern = (
        r'(ssp\. [a-z]+|subsp\. [a-z]+|var\. [a-z]+|\'[a-z]+\'|\'.+\')'
    )

    def get_first_match(pattern, text):
        matches = re.findall(pattern, text)
        return matches[0] if matches else None

    def get_all_matches(pattern, text):
        matches = re.findall(pattern, text)
        return matches if matches else []
    
    def strip_sp(text):
        if len(text.split()) == 2 and ' sp' in text and len(text.split()[1]) < 3:
            return text.split()[0]
        return text

    data["binomial_match"] = data[columnName].apply(lambda x: get_first_match(binomialPattern, x.strip().replace('  ', ' ')))
    data["additions_match"] = data[columnName].apply(lambda x: get_all_matches(additionsPattern, x.strip().replace('  ', ' ')))
    data["binomial_match"] = data["binomial_match"].fillna(data[columnName])
    
    for i in range(len(data)):
        if len(data.at[i, "additions_match"]) > 0 and len(data.at[i, "binomial_match"].split(" ")) > 1:
            if data.at[i, "additions_match"][0] == data.at[i, "binomial_match"].split(" ", 1)[1]:
                data.at[i, "additions_match"] = data.at[i, "additions_match"][1:]

    data["***no_author"] = data["binomial_match"] + data["additions_match"].apply(lambda x : ' ' + ' '.join(x))
    data["***no_author"] = data["***no_author"].apply(lambda x: x.translate(string.punctuation))
    data["***no_author"] = data["***no_author"].apply(lambda x: strip_sp(x).replace('  ', ' ').strip())

    return data

def MatchTaxon(data, data_column, key, key_column, threshold=3):
    """
    Modifies the dataframe data to contain one new columns:
    ***DbTaxonGuess: the most similar taxon name in the database
    """
    def closest(text):
        if text[0] in ['"',"'","(", ")"]:
            text = text[1:]
        copy = key.copy()
        copy = copy[copy[key_column].str[0] == text[0]]
        copy['score'] = copy[key_column].astype(str).apply(lambda x: edit_distance(x, text))
        copy = copy.sort_values(by='score', ascending=True)
        if copy.iloc[0]['score'] < threshold:
            return copy.iloc[0][key_column]
        else:
            return None

    data['***DbTaxonGuess'] = data[data_column].astype(str).apply(closest)
    return data


def MatchCollector(data, columnName):
    """
    Modifies the dataframe data to contain one new columns:
    ***DbCollectorGuess: the most similar collector name in the database based on EditDistanceCol
    """
    data['***DbCollectorGuess'] = data[columnName].apply(lambda x : _EditDistanceCol(str(x)))


collectorNames = pd.read_csv("data/Collectors.csv")
collectorNames['strippedCollector'] = collectorNames['0'].str.lower().str.replace(',','').str.replace('.','').str.replace('  ', ' ')
collectorFrequency = pd.read_csv("data/CollectorFrequency.csv", header=None)
collectorFrequency[0] = collectorFrequency[0].replace('&amp;', '&')
collectorFrequency.set_index(0, inplace=True)


def reformatCol(collector):

    collector = collector.strip()
    collector = re.sub(r'^[A-Za-z]{2}\.\s+', '', collector)

    collector = collector.replace('s.n.', '')

    parts = re.split(r'\s*&\s*', collector, maxsplit=1)
    first, rest = parts[0], (parts[1] if len(parts) > 1 else None)

    m = re.match(r'^([A-Z](?:\.[A-Z])*\.)\s+(.+)$', first)
    if m:
        initials, surname = m.groups()
        first_fmt = f"{surname}, {initials}" if rest else f"{surname} {initials}"
    else:
        first_fmt = first

    return f"{first_fmt} & {rest}" if rest else first_fmt



    # collector = collector.strip()
    # collector = collector.replace('s.n.', '').replace('Dr.', '')

    # pattern = r"([A-Z]\.[A-Z]\.)\s[A-Z]"
    # match = re.search(pattern, collector)

    # if match:
    #     col = collector.replace(match.group(0)[:4] + ' ', '')
    #     if len(col.split()) > 1:
    #         return col.split()[0] + ' ' + match.group(0)[:4] + ' ' + " ".join(collector.split()[1:])
    #     else:
    #         return col.split()[0] + ' ' + match.group(0)[:4]
    # else:
    #     pattern = r"([A-Z]\.)\s[A-Z]"
    #     match = re.search(pattern, collector)
    #     if match:
    #         col = collector.replace(match.group(0)[:2] + ' ', '')
    #         if len(col.split()) > 1:
    #             return col.split()[0] + ' ' + match.group(0)[:2] + ' ' + " ".join(col.split()[1:])
    #         else:
    #             return col.split()[0] + ' ' + match.group(0)[:2]
    # return collector


def _EditDistanceCol(collector):
    if not collector:
        return None

    collector = reformatCol(collector)
    wordsInCollector = collector.lower().replace(',','').replace('.','').replace('  ', ' ').split()

    def containsWords(target):
        target = target.split()
        for i in wordsInCollector:
            if i in target:
                return True
        return False
    
    def containsAllWords(target):
        target = target.split()
        score = 1
        for i in wordsInCollector:
            if i in target:
                score += 1
        return score
    
    def frequency(target):
        if target not in collectorFrequency.index:
            return 1
        score = collectorFrequency.loc[target, 1]
        return 1/math.log(score + 1, 10)
            
    filtered_df = collectorNames[collectorNames['strippedCollector'].apply(lambda x : containsWords(str(x)))]

    Score = pd.DataFrame({
        'string' : filtered_df['0'], 
        'stripped_string' : filtered_df['strippedCollector'], 
        'score' : filtered_df['strippedCollector'].apply(lambda x : (edit_distance(str(x), collector) / containsAllWords(x)) * frequency(x))})
    
    if Score.empty:
        return None

    Score['score'] = Score.apply(lambda x : (x['score']), axis=1)

    Score = Score.sort_values(by='score')
    return Score.iloc[0,0]


def ParseDet(data, columnName):
    """
    Modifies the dataframe data to contain one new columns:
    ***det: the determination
    """
    data['***determinationParsed'] = data[columnName].split('Det. ')[1]


def MatchLocation(data, columnName):
    """
    Modifies the dataframe data to contain two new columns: 
    ***DbPlaceGuess: the most similar location in the database based on EditDistanceLoc
    ***Contains_Paren: whether the location contains a parenthesis
    """

    data[["***DbPlaceGuess", "***Contains_Paren"]] = data[columnName].apply(lambda x : _EditDistanceLoc(str(x))).apply(pd.Series)


placeNames = pd.read_csv("data/PlaceName.csv")
placeNames['strippedLoc'] = placeNames['0'].str.lower().str.replace(',','').str.replace('.','').str.replace('  ', ' ')

def _EditDistanceLoc(location):
    """
    helper function for MatchLocation
    """

    if not location:
        return (None, False)

    continentList = ['africa', 'antarctica', 'asia', 'australia', 'europe', 'north america', 'south america']

    location = location.lower().replace('calif', 'california')
    wordsInLoc = location.lower().replace(',','').replace('.','').replace('  ', ' ').replace('(', '').replace(')', '').split()
    if 'usa' in wordsInLoc:
        wordsInLoc.remove('usa')


    placeNamesCopy = placeNames.copy()
    for cont in continentList:
        if cont not in location:
            placeNamesCopy['strippedLoc'] = placeNamesCopy['strippedLoc'].apply(lambda x : x.replace(cont, ''))
            

    def containsWords(target):
        target = target.split()
        for i in wordsInLoc:
            if i in target:
                return True
        return False
    
    def containsAllWords(target):
        target = target.split()
        score = 1
        for i in wordsInLoc:
            if i in target:
                score *= 10
        return score

    filtered_df = placeNamesCopy[placeNamesCopy['strippedLoc'].apply(lambda x : containsWords(str(x)))]

    if filtered_df.empty:
        return (None, bool(re.match(r'^\([^()]+\)$', location)))

    Score = pd.DataFrame({
        'string' : filtered_df['0'], 
        'stripped_string' : filtered_df['strippedLoc'], 
        'score' : filtered_df['strippedLoc'].apply(lambda x : edit_distance(str(x), location))})

    Score['score'] = Score.apply(lambda x : x['score']/containsAllWords(x['stripped_string']), axis=1)

    Score = Score.sort_values(by='score')
    return (Score.iloc[0, 0], bool(re.match(r'^\([^()]+\)$', location)))


def punctStrip(text):
    text = text.translate(str.maketrans('', '', string.punctuation + '1234567890'))
    return text.strip()

def detectCultivar(text):
    pattern = r'^\S+\s+([A-Z]+)\b'
    match = re.search(pattern, text)
    if match:
        return True
    return False


def sortOutput(list):
    if list:
        list.sort(key=lambda x: x[1])
    return list

