# Springboard Data Science Career Track
Springboard Data Science track project work

# Capstone Pojects completed

#### [Cloud Computing and AutoML applied to Time Series Forecasting](projects/interactive_time_series_forecasting)

**Development Environment:** Python and Pandas, Dask Yarn Cluster (Amazon EMR), Plotly Dash, and CSV/Parquet files (on Amazon S3).

- Transformed existing end-to-end stock time series forecasting notebooks for distributed processing on a 3-node Dask Yarn Cluster running over Amazon EMR and processing data from Amazon S3.
- Generated Supervised learning datasets by doing feature engineering over stock datasets to run AutoML framework.
- Created an interactive web application using Plotly Dash that accepts as input a stock ticker symbol and a time-range for time series forecasting to compute forecasts, which are visualized, based on the data curated from the batch processing job.

#### [Time Series Forecasting of Stock Market Data](projects/stock_price_timeseries)

**Development Environment:** Anaconda, Python, Pandas, NumPy, MatplotLib, Seaborn, and other Python libraries

- Scraped 15+ year comprehensive stock market datasets from sources like Kaggle, macrotrends.net, and partitioned them into six sectors based on industry type.
- Performed data wrangling to impute missing days based on NYSE calendar and removed other inconsistencies; and conducted extensive Exploratory Data Analysis.
- Evaluated the performance of multiple models using the PMDARIMA, and FBPROPHET packages, for each company, and identified the model with best performance, using which companies were ranked by the best performing model within each sector.
- Computed the forecast for short-term gain (1 month) and long-term gain (1-5 years) for the top performers in each sector along with confidence intervals.


