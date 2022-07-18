import os
import logging
import boto3
import tqdm
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial

STOCK_PATH_LOCAL = './Data/stock_data/'
STOCK_BUCKET = 'stocks-data-ankit'
STOCK_BUCKET_PREFIX = 'stock_data_parquet/'

session = boto3.Session()
client = session.client("s3", region_name='us-west-2')
paginator = client.get_paginator('list_objects')
operation_parameters = {'Bucket': STOCK_BUCKET,
                        'Prefix': STOCK_BUCKET_PREFIX}
page_iterator = paginator.paginate(**operation_parameters)

files_to_download = []
for page in page_iterator:
    for content in page['Contents']:
        files_to_download.append(content['Key'])

def download_one_file(client: boto3.client, bucket: str, s3_file: str):
    """
    Download a single file from S3
    Args:
        client (boto3.client): S3 client
        bucket (str): S3 bucket where images are hosted
        s3_file (str): S3 object name
    """

    path_split = os.path.split(s3_file)
    #print (path_split[0], path_split[1])
    local_dir = STOCK_PATH_LOCAL + path_split[0]
    os.makedirs(local_dir, exist_ok=True)

    client.download_file(
        Bucket=bucket, Key=s3_file, Filename=os.path.join(local_dir, path_split[1])
    )

# The client is shared between threads
func = partial(download_one_file, client, STOCK_BUCKET)

# List for storing possible failed downloads to retry later
failed_downloads = []

with tqdm.tqdm(desc="Downloading parquet files from S3", total=len(files_to_download)) as pbar:
    with ThreadPoolExecutor(max_workers=8) as executor:
        # Using a dict for preserving the downloaded file for each future, to store it as a failure if we need that
        futures = {
            executor.submit(func, file_to_download): file_to_download for file_to_download in files_to_download
        }
        for future in as_completed(futures):
            if future.exception():
                failed_downloads.append(futures[future])
            pbar.update(1)
if len(failed_downloads) > 0:
    print("Some downloads have failed. Saving ids to csv")
    with open(
        os.path("failed_downloads.csv"), "w", newline=""
    ) as csvfile:
        wr = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
        wr.writerow(failed_downloads)
