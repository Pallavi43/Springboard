import dask.dataframe as dd
from distributed import Client
import pandas as pd
import numpy as np
import datetime as dt
import os
import time
import glob

from statsmodels.tsa.arima.model import ARIMA
import pmdarima as pm
from sklearn.metrics import mean_squared_error
from prophet import Prophet

STOCK_FILES_PATH = 'Data/generated/daily/'
STOCK_MODELS_OUTDIR = 'Data/generated/models'

def pmdarima_model_eval(df):
    train_pmdarima = df[:-30]['close']
    model_auto = pm.auto_arima(train_pmdarima, start_p=1, start_q=1,
                               test='adf',  # use adftest to find optimal 'd'
                               max_p=3, max_q=3,  # maximum p and q
                               m=1,  # frequency of series
                               d=None,  # let model determine 'd'
                               seasonal=False,  # No Seasonality
                               start_P=0,
                               D=0,
                               trace=True,
                               error_action='ignore',
                               suppress_warnings=True,
                               stepwise=True)
    return model_auto.order

def generate_stocks_df():
    # Read all data files from filepath 'Data/generated/daily'
    companies_df = pd.DataFrame(columns=['ticker', 'file_path'])
    for stock_file in os.listdir(STOCK_FILES_PATH):
        ticker_name = stock_file.split('.')[0]
        companies_df = companies_df.append({
            'ticker': ticker_name,
            'file_path': os.path.join(STOCK_FILES_PATH, stock_file)
        },ignore_index=True)
    return companies_df

def apply_pmdarima_df(company_df):
    stocks_df = pd.read_csv(company_df['file_path'])
    stocks_df = stocks_df.set_index('date')
    stocks_df = stocks_df[['close']]
    pmdarima_order = pmdarima_model_eval(stocks_df)
    return pd.Series({'Company' : company_df['ticker'], 'PMDARIMA_ORDER' : pmdarima_order})

def evaluate_models():
    # create a DF containing all tickers and their paths
    stocks_df = generate_stocks_df().sort_values('ticker').reset_index(drop=True)

    # create a Dask DF with 8 partitions
    stocks_ddf = dd.from_pandas(stocks_df, npartitions=8)

    # apply func to each row
    models_df = stocks_ddf.apply(
        apply_pmdarima_df,
        axis = 1,
        meta = {'Company': object, 'PMDARIMA_ORDER': object}
    ).compute().sort_values('Company').reset_index(drop=True)

    # persist models output
    os.makedirs(STOCK_MODELS_OUTDIR, exist_ok=True)
    models_file_out = os.path.join(STOCK_MODELS_OUTDIR, 'arima_orders.csv')
    models_df.to_csv(models_file_out, index=False)

if __name__ == '__main__':
    # Initiate a Dask Client based on LocalCluster
    client = Client(processes=True, n_workers=8, threads_per_worker=1, memory_limit='2GB')

    # evaluate models and generate company
    evaluate_models()
