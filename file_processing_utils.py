import os
import pandas as pd


def concat_df(folder_path):
    df_list = []
    for file in os.listdir(folder_path):
        df = pd.read_csv(os.path.join(folder_path, file))
        df_list.append(df)
    return pd.concat(df_list, ignore_index=True)


def strip(csvTemplatePath):
    temp = pd.read_csv(csvTemplatePath)
    stripped = pd.DataFrame(columns=temp.iloc[6, 1:len(temp.columns)])
    return stripped


def convert_col_template(df, df_col, template_path, template_col, authority_key):
    template_df = strip(template_path)
    authority_df = pd.read_csv(authority_key)
    for collector in df[df_col].dropna():
        if collector not in authority_df[0]:
            template_df = template_df.append({template_col: collector}, ignore_index=True)
    return template_df


def generate_accession_number(accession_number):
    year, starting = tuple(accession_number.split('.'))
    for i in range(int(starting) + 1, 10000):
        yield f"{year}.{i}"


def processDuplicatesFile(pathToDuplicates, pathToLastAccession):
    """
    takes a modified duplicates file generated from the duplicate notebook. Use the "action" column to determine to merge(m), keep(k), are add a new record(n)  
    """
    df = pd.read_csv(pathToDuplicates)
    last_accession = pd.read_csv(pathToLastAccession)

    generatorLibrary = {}
    for i in range(len(last_accession)):
        generatorLibrary[last_accession.iloc[i, 0]] = generate_accession_number(float(last_accession.iloc[i, 1]))

    df['objectNumber'] = df.apply(
        lambda x: next(generatorLibrary[x['objectNumber'].split('.')[0]]) 
                if x['action'] == 'n' else x['objectNumber'],
        axis=1
    )


    for i in range(len(df)):
        if df.loc[i, 'action'] == 'm':
            group = df[df['objectNumber'] == df.loc[i, 'objectNumber']]
            group = group[group['action'] == 'k']
    
    df.to_csv("data/duplicates_mapping_file", index=False)



def pruneDuplicates(fullDataPath, duplicateMappingPath):
    full_data = pd.read_csv(fullDataPath)
    duplicate_mapping = pd.read_csv(duplicateMappingPath)

    just_merge = duplicate_mapping[duplicate_mapping['action'] == 'm']
    data_no_merges = full_data[~full_data['media handling record: fileName'].isin(just_merge['media handling record: fileName'])]

    just_new = duplicate_mapping[duplicate_mapping['action'] == 'n']
    
    data_no_merges = data_no_merges.set_index('media handling record: fileName')
    just_new = just_new.set_index('media handling record: fileName')

    data_no_merges.update(just_new)
    pruned_data = data_no_merges.reset_index()

    pruned_data.to_csv("data/pruned_duplicates_data.csv", index=False)
