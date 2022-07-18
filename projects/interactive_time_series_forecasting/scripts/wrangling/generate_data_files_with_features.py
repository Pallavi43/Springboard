import dask.dataframe as dd
import pandas as pd
import numpy as np
import os
import datetime as dt
from datetime import datetime
from urllib.error import HTTPError
import pandas_market_calendars as mcal
import requests
from bs4 import BeautifulSoup
import re
import time
import glob

BASE_DATA_PATH = '../../data/'
MACROTRENDS_PATH = os.path.join(BASE_DATA_PATH, 'macrotrends')
STOCK_DATA_PATH = os.path.join(BASE_DATA_PATH, 'stock_data')
TICKER_SECTOR_NAME_PATH = os.path.join(BASE_DATA_PATH, 'ticker_sector_name')
WRANGLED_DATA_PATH = os.path.join(BASE_DATA_PATH ,'wrangled_data_files')


#creating a dataframe for a sector that contains the ticker names, cmpny names and url for stock data
def create_dfs(sector_df):
    file_path = sector_df['filepath'].values[0]
    try:
        ticker = pd.read_csv(file_path)
        ticker_name = ticker['Ticker'].str.lower()
        ticker['Ticker'] = ticker_name
        ticker['file_path'] = os.path.join(STOCK_DATA_PATH, ticker_name +".us.txt") 
        return (ticker)
    except FileNotFoundError:
        print ("file " + csv_file + " not found !!!")
    except pd.errors.EmptyDataError:
        print ("file " + csv_file + " is empty !!!")
    return None


# filtering the data by years
def filter_data_by_year(df, start_year, end_year):
    df_start_year = df['date'].min().year
    df_end_year = df['date'].max().year
    if start_year >= df_start_year:
        if end_year <= df_end_year:
            return df[df['date'].dt.year.between(start_year, end_year)]
    return None


# checking if nyse open days equal to the stock price time series
def nyse_open_days(df):
    nyse = mcal.get_calendar('NYSE')
    min_date = df['date'].min()
    max_date = df['date'].max()
    nyse_open = nyse.schedule(start_date=min_date, end_date=max_date)
    nyse_open.reset_index(inplace=True)
    nyse_open.drop(columns=['market_open', 'market_close'], inplace=True)
    nyse_open.rename(columns={'index': 'date'}, inplace=True)

    nyse_num_open = nyse_open.shape[0]
    df_num_open = df.shape[0]

    num_open_days = nyse_num_open - df_num_open
    if num_open_days < 50:
        nyse_df = df.merge(nyse_open, how='right', on='date')
        nyse_df.ffill(inplace=True)
        nyse_df.bfill(inplace=True)
        return nyse_df
    return None


# retrieve the stock data using the parquet file
def txt_file_to_frame(txt_df):
    txt_file = txt_df['file_path']
    try:
        company_df = pd.read_csv(txt_file)
        tick_name = txt_file.split('/')[-1].split('.')[0]
        company_df['daily_returns'] = company_df['close'].pct_change()
        company_df['date'] = company_df['date'].astype('datetime64[ns]')

        # filter DF by year range (2012,2017)
        company_df = filter_data_by_year(company_df, 2012, 2017)
        if not company_df is None:
            company_df = nyse_open_days(company_df)
            if not company_df is None:
                # print (company_df)
                return company_df
    except FileNotFoundError:
        print ("file " + txt_file + " not found !!!")
    except pd.errors.EmptyDataError:
        print ("file " + txt_file + " is empty !!!")
    return None


#resample the daily stock data to quarter data
def resample_q(df):
    return df.set_index('date').resample('Q').mean().reset_index()

# retrieve of interest rate data
def create_interest_rates_df(start_year, end_year):
    text_file_path = os.path.join(BASE_DATA_PATH, 'fed-funds-rate-historical-chart.csv')
    try:
        interest_rates = pd.read_csv(text_file_path, on_bad_lines='skip')
        interest_rates.rename(columns = {' value' : 'Interest Rate(%)'}, inplace = True)
        interest_rates['date'] = interest_rates['date'].astype('datetime64[ns]')
        interest_rates = interest_rates[interest_rates['date'].dt.year.between(start_year, end_year)]
        interest_rates = interest_rates.set_index('date').resample('Q').mean().reset_index()
        return interest_rates
    except FileNotFoundError:
        print ("file " + text_file_path + " not found !!!")
    except pd.errors.EmptyDataError:
        print ("file " + text_file_path + " is empty !!!")
    return None


def revenue_df_for_ticker(ticker, start_year, end_year):
    text_file_path = os.path.join(MACROTRENDS_PATH, ticker + ".csv")
    try:
        revenue_pe_df = pd.read_csv(text_file_path, on_bad_lines='skip')
        revenue_pe_df['Date'] = revenue_pe_df['Date'].astype('datetime64[ns]')
        revenue_pe_df = revenue_pe_df[revenue_pe_df['Date'].dt.year.between(start_year, end_year)]
        return revenue_pe_df
    except FileNotFoundError:
        print ("file " + text_file_path + " not found !!!")
    except pd.errors.EmptyDataError:
        print ("file " + text_file_path + " is empty !!!")
    return None


def merge_other_features(df, revenue_pe_df, interest_rates_df):
    if revenue_pe_df is None:
        return None

    if interest_rates_df is None:
        return None

    # Merge Revenue data with current company's DF
    rev_df = pd.merge_asof(df, revenue_pe_df, left_on='date', right_on='Date', direction='nearest').drop(
                columns='Date')

    # Merge Interest Rates DF with PE Ratio DF
    return pd.merge_asof(rev_df, interest_rates_df, on='date', direction='nearest')

def apply_to_single_company(sector_tickers_df):
    ticker_name = sector_tickers_df['Ticker'].lower()
    company_name = sector_tickers_df['Company_Name']

    company_df = txt_file_to_frame(sector_tickers_df)
    if company_df is None:
        return None

    company_df_qtly = resample_q(company_df)
    revenue_pe_df = revenue_df_for_ticker(ticker_name, 2012, 2017)
    rates_df = create_interest_rates_df(2012, 2017)

    merged_df = merge_other_features(company_df_qtly, revenue_pe_df, rates_df)
    if merged_df is None:
        return None

    # Finally, persist the merged DF
    base_path = WRANGLED_DATA_PATH
    daily_path = os.path.join(base_path, 'daily')
    os.makedirs(daily_path, exist_ok=True)
    daily_file_out = os.path.join(daily_path, ticker_name + '.csv')
    company_df.to_csv(daily_file_out, index=False)

    qtly_path = os.path.join(base_path, 'qtly')
    os.makedirs(qtly_path, exist_ok=True)
    qtly_file_out = os.path.join(qtly_path, ticker_name + '.csv')
    merged_df.to_csv(qtly_file_out, index=False)

    return None

def apply_to_company_partition(partitions_ddf):
    return partitions_ddf.apply(apply_to_single_company, axis=1)

if __name__ == '__main__':
    # Initiate a Dask Client based on LocalCluster
    client = Client(n_workers=4, threads_per_worker=2, memory_limit='2GB')

    # Read all sector files from filepath 'Data/ticker_sector_name'
    sectors_df = pd.DataFrame(columns=['name', 'filepath'])
    for sector_file in os.listdir(TICKER_SECTOR_NAME):
        sector_name = sector_file.split('.')[0]
        sectors_df = sectors_df.append({'name': sector_name + '_dfs', 'filepath': os.path.join(TICKER_SECTOR_NAME, sector_file)}, ignore_index=True)

    # Create data frame for all tickers belonging to each sector
    # And persist the final dataframe per sector in a pickled file
    all_tickers_df = sectors_df.groupby('name', group_keys=False).apply(create_dfs)
    all_tickers_df = all_tickers_df.sort_values('Ticker').drop_duplicates().reset_index(drop=True)

    # create a Dask data frame with partitions
    all_tickers_ddf = dd.from_pandas(all_tickers_df, npartitions=16)

    start_time = time.time()
    all_tickers_ddf.map_partitions(apply_to_company_partition).compute()
    end_time = time.time()
    print ("Elapsed time: {}".format(end_time - start_time))
