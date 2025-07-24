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





