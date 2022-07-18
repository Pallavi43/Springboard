import dask.dataframe as dd
from distributed import Client
import pandas as pd
import numpy as np
import datetime as dt
import os
import time
import glob

STOCK_FILES_PATH_DAILY = 'Data/generated/daily/'
STOCK_FILES_PATH_QTLY = 'Data/generated/qtly/'
STOCK_AUTOML_OUTDIR = 'Data/generated/automl/'


def add_features(df_feat):
    cols = df_feat.iloc[:, 4:7].columns.tolist()
    for col in cols:
        df_feat[col + '_7_min'] = df_feat[col].rolling(7).min()
        df_feat[col + '_7_max'] = df_feat[col].rolling(7).max()
        df_feat[col + '_7_mean'] = df_feat[col].rolling(7).mean()
        df_feat[col + '_7_std'] = df_feat[col].rolling(7).std()
        df_feat[col + '_14_min'] = df_feat[col + '_7_min'].shift(7)
        df_feat[col + '_14_max'] = df_feat[col + '_7_max'].shift(7)
        df_feat[col + '_14_mean'] = df_feat[col + '_7_mean'].shift(7)
        df_feat[col + '_14_std'] = df_feat[col + '_7_std'].shift(7)
        df_feat.dropna(inplace=True)

        return df_feat

def genearate_automl_df(company_df):
    df_daily = pd.read_csv(company_df['file_path_daily'])
    df_qtly = pd.read_csv(company_df['file_path_qtly'])
    df_daily = df_daily[['date', 'close']]
    df_qtly = df_qtly[['date', 'PE Ratio', 'Revenue_Amount(Millions)', 'Interest Rate(%)']]

    df_daily['date'] = df_daily['date'].astype('datetime64')
    df_qtly['date'] = df_qtly['date'].astype('datetime64')
    df_qtly['Revenue_Amount(Millions)'] = df_qtly['Revenue_Amount(Millions)'].astype('str').str.replace('$', '',
                                                                                                        regex=True)
    df_qtly['Revenue_Amount(Millions)'] = df_qtly['Revenue_Amount(Millions)'].astype('str').str.replace(',', '',
                                                                                                        regex=True)

    merged_df = pd.merge_asof(df_daily, df_qtly, on='date', direction='forward').set_index('date')
    new_cols_list_t = list(map(lambda x: x + '[t]', merged_df.columns.tolist()))
    new_cols_list_t_1 = list(map(lambda x: x + '[t-1]', merged_df.columns.tolist()))
    merged_df.columns = new_cols_list_t
    merged_df_shift_1 = merged_df.shift(1)
    merged_df_shift_1.columns = new_cols_list_t_1
    merged_df = merged_df.merge(merged_df_shift_1, right_index=True, left_index=True).dropna()
    return add_features(merged_df)

def generate_stocks_df():
    # Read all data files from filepath 'Data/generated/daily'
    companies_df = pd.DataFrame(columns=['ticker', 'file_path'])

    for stock_file in os.listdir(STOCK_FILES_PATH_DAILY):
        ticker_name = stock_file.split('.')[0]
        companies_df = companies_df.append({
            'ticker': ticker_name,
            'file_path_daily': os.path.join(STOCK_FILES_PATH_DAILY, stock_file),
            'file_path_qtly': os.path.join(STOCK_FILES_PATH_QTLY, stock_file)
        },ignore_index=True)
    return companies_df

def apply_automl_generate_df(company_df):
    generated_df = genearate_automl_df(company_df)

    # persist models output
    os.makedirs(STOCK_AUTOML_OUTDIR, exist_ok=True)
    models_file_out = os.path.join(STOCK_AUTOML_OUTDIR, company_df['ticker'] + '.csv')
    generated_df.to_csv(models_file_out, index=True)
    return pd.Series({'dummy': 'dummy'})

def create_automl_data_files():
    # create a DF containing all tickers and their paths
    stocks_df = generate_stocks_df().sort_values('ticker').reset_index(drop=True)

    # create a Dask DF with 8 partitions
    stocks_ddf = dd.from_pandas(stocks_df, npartitions=8)

    # apply func to each row
    models_df = stocks_ddf.apply(
        apply_automl_generate_df,
        axis = 1,
        meta = {'dummy' : object}
    ).compute()


if __name__ == '__main__':
    # Initiate a Dask Client based on LocalCluster
    client = Client(processes=True, n_workers=8, threads_per_worker=1, memory_limit='2GB')

    # generate daily CSV files for running AUTO-ML
    create_automl_data_files()
