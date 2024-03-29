# Introduction
This project contains scripts that process 15 years of Stock Market data (obtained from a Kaggle dataset) and performs Data Wrangling and Predictive Modeling. The provided scripts use Dask for performing parallel computations on stock datasets.

# Data Preparation workflow
Upload all the data artifacts within ./data/ to a Bucket on Amazon S3 Object store. Then spin off a 3-node Amazon EMR cluster with Hadoop Yarn setup. Then set up a Dask-Yarn cluster setup on the master node of the EMR cluster using the provided bootstrap action by Dask. Next, execute the provided scripts that read all the stock data files from AWS S3; performed wrangling, exploring and modeling in the EMR cluster and write back to the Amazon S3 filesystem. 

![data-preparation-workflow](data/data-preparation-workflow.png)

# Deployment
## Running on Local machine
For running on local machine, setup a virtual environment and then install the recommended packages

## Data Upload to Amazon S3
You may use the provided scripts within ./scripts/misc/ to upload the provided data files to your Amazon S3 bucket

## Dask Yarn on Amazon EMR cluster
For deploying a Dask Yarn cluster on Amazon EMR, follow the Deployment section from Dask documentation:
https://yarn.dask.org/en/latest/aws-emr.html 

Note: You would have to allow inbound traffic to port 22 within your Master Node's security group policy (not recommended for production deployment)

Once, the EMR cluster is ready, SSH to your master node and access the scripts and data from your AWS S3 Bucket (that you previously uploaded).

## Changes to the scripts for execution on EMR cluster
Instead of using `LocalCluster()` within your Dask Client, you would replace it with `YarnCluster()`
All the path referenced to local file system must be replaced with correcponding references to paths on your Amazon S3 Bucket. For example, replace, './data/stock_data' with 's3://<bucket-name>/stock_data'

# Files Organization
## Scripts
```
./scripts/
./scripts/wrangling         <== Data Wrangling scripts that generate daily/quarterly data files
./scripts/modeling          <== Data Modeling scripts to be run on local / EMR cluster
./scripts/misc              <== Miscellaneous scripts like Data upload/download to/from Amazon S3
```

## Data
```
./data
./data/stock_data           <== Stock data text files (from Kaggle dataset)
./data/ticker_sector_name   <== Ticker to Sector mapping files (from web scraping)
./data/macrotrends          <== Generated by wrangling scripts
./data/wrangled_data_files  <== Generated by wrangling scripts
./data/modeling_data_files  <== Generated by Modeling scripts
```

## Modeling Data
### Auto ML
For running AutoML, the wrangled stock data files were updated with additional features generated as a result of feature engineering and the output files were saved in ./data/modeling_data_files/automl directory.

## PMDARIMA orders
The orders generated by PMDARIMA were saved for each stock file that was modeled and the outputs are referred for running ARIMA modeling in response to a user selected ticker symbol through web application.


# Web Application
[app/dash-time-series-forecasting](./app/dash-time-series-forecasting)

It features an interactive web application created using Plotly Dash where users can provide selection for a company ticker and a time-range and the web application fetches the stock data/model file based on the user input from Amazon S3 and runs the various models like ARIMA, Prophet and AutoML and creates figures that visualise the stock forecasts over the last 30 days.   
