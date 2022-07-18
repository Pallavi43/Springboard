import dask.dataframe as dd
from dask.distributed import Client
import pyspark.pandas as ps
import pandas as pd
import numpy as np
from pyspark.sql import SparkSession
import os
import datetime as dt
from datetime import datetime
from urllib.error import HTTPError
import pandas_market_calendars as mcal
import requests
from bs4 import BeautifulSoup
import re
import time

BASE_DATA_PATH = '../../data/'
MACROTRENDS_PATH = os.path.join(BASE_DATA_PATH, 'macrotrends')
STOCK_DATA_PATH = os.path.join(BASE_DATA_PATH, 'stock_data')
TICKER_SECTOR_NAME_PATH = os.path.join(BASE_DATA_PATH, 'ticker_sector_name')


#creating a dataframe for a sector that contains the ticker names, cmpny names and url for stock data
def create_dfs(sector_df):
    file_path = sector_df['filepath'].values[0]
    try:
        ticker = pd.read_csv(file_path)
        ticker_name = ticker['Ticker'].str.lower()
        ticker['Ticker'] = ticker_name
        ticker['txt_file'] = os.path.join(STOCK_DATA_PATH, ticker_name +".us.txt")
        return (ticker)
    except FileNotFoundError:
        print ("file " + csv_file + " not found !!!")
    except pd.errors.EmptyDataError:
        print ("file " + csv_file + " is empty !!!")
    return None


# modify company name to retrieve revenue and pe ratio data
def get_macrotrends_name(company_name):
    # Using re.split()
    # Splitting characters in String
    res = company_name.encode("ascii", "ignore")
    res = re.sub('[^a-zA-Z0-9 \-\_]', '', res.decode())
    res = re.split(' |, ', res)

    macrotrends_name = ''
    for elem in res:
        if not macrotrends_name:
            macrotrends_name = elem.lower()
        else:
            macrotrends_name = macrotrends_name + '-' + elem.lower()
    return macrotrends_name


def fetch_other_features(sector_tickers_df):
    ticker_name = sector_tickers_df['Ticker']
    company_name = sector_tickers_df['Company_Name']
    stock_path = os.path.join(STOCK_DATA_PATH, ticker_name.lower() +".us.txt")

    if not os.path.isfile(stock_path):
        return None

    macrotrends_name = get_macrotrends_name(company_name)
    macrotrends_rev_url = "https://www.macrotrends.net/stocks/charts/{}/{}/revenue".format(ticker_name,
                                                                                           macrotrends_name)
    macrotrends_pe_url = "https://www.macrotrends.net/stocks/charts/{}/{}/pe-ratio".format(ticker_name,
                                                                                           macrotrends_name)

    # try to see if the URL head request results in a non-400 status
    x = requests.head(macrotrends_rev_url)
    if (x.status_code != 404):
        try:
            # Fetch Revenue data for current company using web scrapping
            revenue = pd.read_html(macrotrends_rev_url, match='Quarterly Revenue', flavor='bs4')[0]
            rename_dict = {}
            rename_dict[revenue.columns[0]] = 'Revenue_Date'
            rename_dict[revenue.columns[1]] = 'Revenue_Amount(Millions)'
            revenue.rename(columns=rename_dict, inplace=True)
            revenue['Revenue_Date'] = revenue['Revenue_Date'].astype('datetime64[ns]')
            revenue.sort_values(by=['Revenue_Date'], ascending=True, inplace=True, ignore_index=True)

            # Return None if Revenue data is missing for all quarters
            num_missing_qtrs = revenue['Revenue_Amount(Millions)'].isna().sum()
            num_rows = revenue.shape[0]
            # if more than 25% missing values, discard current DF
            if num_missing_qtrs > int(num_rows * 0.25):
                print ("Discarding DF for ticker={}, num_missing={}, total_quarters={}"
                       .format(ticker_name, num_missing_qtrs, num_rows))
                # print(revenue.shape)
                # print(revenue)
                return None

            # else bfill missing values based on other quarters
            revenue['Revenue_Amount(Millions)'].ffill(inplace=True)
            revenue['Revenue_Amount(Millions)'].bfill(inplace=True)

            # Fetch PE Ratio for current company using web scrapping
            pe_ratio = pd.read_html(macrotrends_pe_url, match='PE Ratio Historical Data', flavor='bs4')[0]
            pe_ratio.columns = pe_ratio.columns.droplevel()
            pe_ratio.drop(columns=[pe_ratio.columns[1], pe_ratio.columns[2]], inplace=True)
            pe_ratio['Date'] = pe_ratio['Date'].astype('datetime64[ns]')
            pe_ratio.sort_values(by=['Date'], inplace=True)

            # Merge PE Ratio data with Revenue DF
            pe_rev_df = pd.merge_asof(pe_ratio, revenue, left_on='Date', right_on='Revenue_Date', direction='nearest')
            pe_rev_df.drop(columns=['Revenue_Date'], inplace=True)

            # Finally, persist the merged DF
            macrotrends_file_out = os.path.join(MACROTRENDS_PATH, ticker_name.lower() + '.csv')
            os.makedirs(MACROTRENDS_PATH, exist_ok=True)
            pe_rev_df.to_csv(macrotrends_file_out, index=False)

        except HTTPError as e:
            print ("Error while retriving URL \"" + macrotrends_rev_url + "\": " + str(e))
        except ValueError as v:
            print ("Error while retriving URL \"" + macrotrends_rev_url + "\": " + str(v))

        return None


def scrape_quarterly_features(company_ddf):
    return company_ddf.apply(fetch_other_features, axis=1)


if __name__ == '__main__':
    # Initiate a Dask Client based on LocalCluster
    client = Client(n_workers=1, threads_per_worker=8, processes=False, memory_limit='2GB')

    # Read all sector files from filepath 'Data/ticker_sector_name'
    sectors_df = pd.DataFrame(columns=['name', 'filepath'])
    for sector_file in os.listdir(TICKER_SECTOR_NAME_PATH):
        sector_name = sector_file.split('.')[0]
        sectors_df = sectors_df.append({'name': sector_name + '_dfs', 'filepath': os.path.join(TICKER_SECTOR_NAME_PATH, sector_file)}, ignore_index=True)

    # Create data frame for all tickers belonging to each sector
    # And persist the final dataframe per sector in a pickled file
    all_tickers_df = sectors_df.groupby('name', group_keys=False).apply(create_dfs)
    all_tickers_df = all_tickers_df.sort_values('Ticker').drop_duplicates().reset_index(drop=True)

    # create a Dask data frame with partitions
    all_tickers_ddf = dd.from_pandas(all_tickers_df, npartitions=16)

    start_time = time.time()
    all_tickers_ddf.apply(fetch_other_features, axis = 1, meta = {}).compute()
    end_time = time.time()
    print ("Elapsed time: {}".format(end_time - start_time))
