import os
import logging
import boto3
from botocore.exceptions import ClientError

stock_path = './Data/stock_data'
stock_bucket = 'stocks-data-ankit'

for filename in os.listdir(stock_path):
    f = os.path.join(stock_path, filename)

    # checking if it is a file
    if not os.path.isfile(f):
        continue

    ticker_name = filename.split('.', 1)[0]
    s3_object_name = 'stock_data' + '/ticker=' + ticker_name + '/' + filename
    print(f, s3_object_name)

    s3 = boto3.resource('s3')
    try:
        response = s3.Bucket(stock_bucket).upload_file(f, s3_object_name)
    except ClientError as e:
        logging.error(e)
