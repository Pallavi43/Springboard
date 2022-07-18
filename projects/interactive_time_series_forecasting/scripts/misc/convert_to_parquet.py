import os
import logging
import boto3
from botocore.exceptions import ClientError
import time

STOCKS_DATABASE = 'stock_analysis'
STOCKS_TABLE = 'stock_data'
PARQUET_STOCKS_TABLE = 'stock_data_parquet'
ATHENA_OUTPUT_LOCATION = 's3://aws-athena-query-results-stock-data/'

def get_var_char_values(d):
    return [obj['VarCharValue'] for obj in d['Data']]

def query_results(query, wait = True, get_results = False):
    client = boto3.client('athena')
    
    ## This function executes the query and returns the query execution ID
    response_query_execution_id = client.start_query_execution(
        QueryString = query,
        QueryExecutionContext = {
            'Database' : STOCKS_DATABASE
        },
        ResultConfiguration = {
            'OutputLocation': ATHENA_OUTPUT_LOCATION
        },
        WorkGroup='primary'
    )

    if not wait:
        return True, response_query_execution_id['QueryExecutionId']
    else:
        response_get_query_details = client.get_query_execution(
            QueryExecutionId = response_query_execution_id['QueryExecutionId']
        )
        status = 'RUNNING'
        iterations = 3000 # 10 mins

        while (iterations > 0):
            iterations = iterations - 1
            response_get_query_details = client.get_query_execution(
                QueryExecutionId = response_query_execution_id['QueryExecutionId']
            )
            status = response_get_query_details['QueryExecution']['Status']['State']
            
            if (status == 'FAILED') or (status == 'CANCELLED') :
                failure_reason = response_get_query_details['QueryExecution']['Status']['StateChangeReason']
                print(failure_reason)
                return False, None 

            elif status == 'SUCCEEDED':
                location = response_get_query_details['QueryExecution']['ResultConfiguration']['OutputLocation']
                if not get_results:
                    return True, None

                globheader = None
                globresults = []
                nextToken = ''

                while True:
                    args = {}
                    args['QueryExecutionId'] = response_query_execution_id['QueryExecutionId']
                    if nextToken:
                        args['NextToken'] = nextToken

                    ## Function to get output results
                    response_query_result = client.get_query_results(**args)

                    #print (response_query_result)
                    result_data = response_query_result['ResultSet']
        
                    # no results
                    if len(response_query_result['ResultSet']['Rows']) < 1:
                        return True,None

                    rowIndex = 0
                    if not globheader:
                        header = response_query_result['ResultSet']['Rows'][0]
                        globheader = [obj['VarCharValue'] for obj in header['Data']]
                        rowIndex = rowIndex + 1

                    rows = response_query_result['ResultSet']['Rows'][rowIndex:]
                    #result = [dict(zip(header, get_var_char_values(row))) for row in rows]
                    results = [ get_var_char_values(row) for row in rows]
                    globresults.extend(results)

                    if 'NextToken' in response_query_result:
                        nextToken = response_query_result['NextToken']
                    else:
                        nextToken = ''

                    if not nextToken:
                        break
                    time.sleep(0.1) #sleep 100ms

                return True, (globheader, globresults)
            else:
                time.sleep(0.2) #sleep 2000ms

    return False, None

def create_ddl_query(tickers):
    query = 'INSERT INTO {} SELECT * FROM {} WHERE ticker IN ('.format(PARQUET_STOCKS_TABLE, STOCKS_TABLE)
    first = True
    for t in tickers:
        if not first:
            query = query + ', '
        else:
            first = False
        query = query + "'" + t + "'"

    query = query + ');'
    return query

query = 'SELECT DISTINCT ticker FROM ' + STOCKS_TABLE + ';'
location,result = query_results(query, wait=True, get_results=True)
tickers = [arr[0] for arr in result[1]]
tickers.sort()

batch_size = 100
ind = 0
while ind < len(tickers):
    insert_query = create_ddl_query(tickers[ind:ind+batch_size])
    print ("================================================")
    print (insert_query)
    query_succeeded,results = query_results(insert_query, wait=True, get_results=False)
    if query_succeeded:
        print ("QUERY SUCCEEDED")
    else:
        print ("QUERY FAILED")
    print ("")
    print ("")

    ind = ind + batch_size

