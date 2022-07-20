import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, ClientsideFunction
import plotly.express as px
import plotly.graph_objects as go

import numpy as np
import pandas as pd
import pmdarima as pm
from statsmodels.tsa.arima.model import ARIMA
import datetime
from datetime import datetime as dt
from sklearn.metrics import mean_squared_error
from prophet import Prophet
from supervised.automl import AutoML
import matplotlib
import pathlib
import os

matplotlib.pyplot.switch_backend('Agg')

app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
app.title = "Stock Data Analysis Dashboard"

server = app.server
app.config.suppress_callback_exceptions = True

# Path
BASE_PATH = pathlib.Path(__file__).parent.resolve()
DATA_PATH = BASE_PATH.joinpath("data").resolve()
STOCK_FILES_PATH = DATA_PATH.joinpath('generated/daily/').resolve()
MODELS_PATH = DATA_PATH.joinpath('generated/models/').resolve()

AUTOML_FILES_PATH = 'data/generated/automl'

AUTOML_MODELS_OUT_PATH = 'data/generated/automl/saved'
os.makedirs(AUTOML_MODELS_OUT_PATH, exist_ok=True)

# Read data
ticker_list = []
#for filename in os.listdir(STOCK_FILES_PATH):
#    ticker_list.append(filename.split('.')[0])
#ticker_list.sort()

ARIMA_ORDERS_DF = pd.read_csv(MODELS_PATH.joinpath('arima_orders.csv'))
ticker_list = ARIMA_ORDERS_DF['Company'].unique()

def description_panel():
    """

    :return: A Div containing dashboard title & descriptions.
    """
    return html.Div(
        id="description-panel",
        children=[
            html.H5("Stock Data Analysis"),
            html.Div(
                id="intro",
                children="Explore stock forecasting data by making a selection from the below dropdowns.",
            ),
        ],
    )


def generate_control_panel():
    """

    :return: A Div containing controls for graphs.
    """
    return html.Div(
        id="control-panel",
        children=[
            html.P("Select Ticker"),
            dcc.Dropdown(
                id="ticker-select",
                options=[{"label": i.upper(), "value": i} for i in ticker_list],
                value=ticker_list[0],
            ),
        ],
	style = {'width': '60%', 'display': 'inline-block'},
    )

app.layout = html.Div(
    id="app-container",
    children=[
        # Banner
        html.Div(
            id="banner",
            className="banner",
            children=[html.Img(src=app.get_asset_url("plotly_logo.png"))],
        ),
        # Left column
        html.Div(
            id="left-column",
            className="four columns",
            children=[description_panel(), generate_control_panel()]
        ),
        # Right column
        html.Div(
            id="right-column",
            className="eight columns",
            children=[
                # Stock Values graph for the selected time range
                html.Div(
                    id="stock_values_panel",
                    children=[
                        html.B("Stock values over time"),
                        html.Hr(),
                        dcc.Graph(id="stock_values_graph"),
                    ],
                ),
                html.Div(
                    id="stock_modeling_panel_arima",
                    children=[
                        dcc.Graph(id="stock_pmdarima_graph"),
                        html.Div(
                            id="arima_mape_div",
                            style = {'width': '49%', 'display': 'inline-block', 'text-align' : 'center'}
                        ),
                        html.Div(
                            id="arima_rmse_div",
                            style={'width': '49%', 'display': 'inline-block', 'text-align' : 'center'}
                        ),
                    ],
                    #style = {'width': '49%', 'display': 'inline-block'}
                ),
                html.Div(
                    id="stock_modeling_panel_prophet",
                    children=[
                        dcc.Graph(id="stock_prophet_graph"),
                        html.Div(
                            id="prophet_mape_div",
                            style = {'width': '49%', 'display': 'inline-block', 'text-align' : 'center'}
                        ),
                        html.Div(
                            id="prophet_rmse_div",
                            style={'width': '49%', 'display': 'inline-block', 'text-align' : 'center'}
                        ),
                    ],
                    #style = {'width': '49%', 'display': 'inline-block'}
                ),
                html.Div(
                    id="stock_modeling_panel_automl",
                    children=[
                        dcc.Graph(id="stock_automl_graph"),
                        html.Div(
                            id="automl_mape_div",
                            style = {'width': '49%', 'display': 'inline-block', 'text-align' : 'center'}
                        ),
                        html.Div(
                            id="automl_rmse_div",
                            style={'width': '49%', 'display': 'inline-block', 'text-align' : 'center'}
                        ),
                    ],
                ),
            ],
        ),
    ],
)

def order_from_file(df, company_name):
    order_str = df[df['Company'] == company_name]['PMDARIMA_ORDER'].values[0]
    return tuple(map(lambda x: int(x.strip()), order_str[1:-1].split(',')))

def pmdarima_model_eval(df, company_name):
    data = df.values
    split = len(data) - 30
    train_pmdarima = df[:-30]['close']
    test_pmdarima = df[-30:]['close']
    arima_order = order_from_file(ARIMA_ORDERS_DF, company_name)

    history_pmd = [x for x in train_pmdarima]
    pmd_prediction = []
    ci_underline = []
    ci_overline = []
    for i in range(len(test_pmdarima)):
        model = ARIMA(history_pmd, order=arima_order)
        model_fit = model.fit()
        model_result = model_fit.get_forecast(steps=1)
        model_forecast = model_result.predicted_mean
        pmd_prediction.append(model_forecast[0])
        obs = test_pmdarima[i]
        history_pmd.append(obs)
        ci = model_result.conf_int(alpha=0.01)
        ci_underline.append(ci[0][0])
        ci_overline.append(ci[0][1])
    ci_underline = np.array(ci_underline)
    ci_overline = np.array(ci_overline)

    rng = np.array([i for i in range(0, len(test_pmdarima))])
    test_pmdarima = np.array(test_pmdarima)
    pmd_prediction = np.array(pmd_prediction)
    mse = mean_squared_error(test_pmdarima, pmd_prediction)
    pmdarima_rmse = np.sqrt(mse)
    pmdarima_mape = np.mean(np.abs(test_pmdarima - pmd_prediction) / np.abs(test_pmdarima))
    pmdarima_rmse_list = ((np.square(np.subtract(test_pmdarima, pmd_prediction))))
    pmdarima_mape_list = (np.abs(test_pmdarima - pmd_prediction) / np.abs(test_pmdarima))
    # pmdarima_rmse_list = list(map(lambda x :x[0], arima_rmse_list))
    # pmdarima_mape_list = list(map(lambda x :x[0], arima_mape_list))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rng, y=test_pmdarima,
                             mode='lines',
                             name='actual'))
    fig.add_trace(go.Scatter(x=rng, y=pmd_prediction,
                             mode='lines',
                             name='prediction'))
    fig.add_trace(go.Scatter(
        name='Upper Bound',
        x=rng,
        y=ci_overline,
        mode='lines',
        marker=dict(color="#444"),
        line=dict(width=0),
        showlegend=False
    ))

    fig.add_trace(go.Scatter(
        name='Lower Bound',
        x=rng,
        y=ci_underline,
        marker=dict(color="#444"),
        line=dict(width=0),
        mode='lines',
        fillcolor='rgba(68, 68, 68, 0.3)',
        fill='tonexty',
        showlegend=False
    ))

    fig.update_layout(
        title='Forecast of {} Stock Price for last 30 days (ARIMA{})'.format(company_name.upper(), arima_order),
        xaxis_title="Days",
        yaxis_title="Price",
        #legend_title="Legend Title",
    )

    return (fig, 'MAPE: ' + str(pmdarima_mape), 'RMSE: ' + str(pmdarima_rmse))


def prophet_model_eval(df, company_name):
    df_prophet = df.copy()
    df_prophet.reset_index(inplace=True)
    df_prophet = df_prophet.rename(columns={'date': 'ds', 'close': 'y'})

    print (df_prophet)

    prophet_train = df_prophet.drop(df_prophet.index[-30:])
    date_list = df_prophet['ds'].tail(30).tolist()
    model_hold_out = Prophet()
    model_hold_out.fit(prophet_train)
    future_hold_out = list()

    # define the period for which we want a prediction
    for i in range(0, 30):
        date = date_list[i]
        future_hold_out.append([date])
    future_hold_out = pd.DataFrame(future_hold_out)
    future_hold_out.columns = ['ds']

    # use the model to make a forecast
    forecast_hold_out = model_hold_out.predict(future_hold_out)
    print (forecast_hold_out)
    y_pred = forecast_hold_out['yhat'].values
    y_true = df_prophet['y'][-30:].values
    mse = mean_squared_error(y_true, y_pred)
    prophet_rmse = np.sqrt(mse)
    prophet_mape = np.mean(np.abs(y_true - y_pred) / np.abs(y_true))
    prophet_rmse_list = ((np.square(np.subtract(y_true, y_pred))))
    prophet_mape_list = (np.abs(y_true - y_pred) / np.abs(y_true))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=forecast_hold_out.index, y=y_true,
                             mode='lines',
                             name='actual'))
    fig.add_trace(go.Scatter(x=forecast_hold_out.index, y=y_pred,
                             mode='lines',
                             name='prediction'))

    fig.add_trace(go.Scatter(
        name='Upper Bound',
        x=forecast_hold_out.index,
        y=forecast_hold_out['yhat_upper'],
        mode='lines',
        marker=dict(color="#444"),
        line=dict(width=0),
        showlegend=False
    ))

    fig.add_trace(go.Scatter(
        name='Lower Bound',
        x=forecast_hold_out.index,
        y=forecast_hold_out['yhat_lower'],
        marker=dict(color="#444"),
        line=dict(width=0),
        mode='lines',
        fillcolor='rgba(68, 68, 68, 0.3)',
        fill='tonexty',
        showlegend=False
    ))

    fig.update_layout(
        title='Forecast of {} Stock Price for last 30 days (PROPHET)'.format(company_name.upper()),
        xaxis_title="Days",
        yaxis_title="Price",
        # legend_title="Legend Title",
    )

    return (fig, 'MAPE: ' + str(prophet_mape), 'RMSE: ' + str(prophet_rmse))


def automl_model_eval(final_prediction_df, company_name):
    train = final_prediction_df.iloc[:-30, :]
    test = final_prediction_df.iloc[-30:, :]
    X_train = train.iloc[:, 1:]
    y_train = train.iloc[:, 0]
    X_test = test.iloc[:, 1:]
    y_test = (test.iloc[:, 0]).values

    results_path = os.path.join(AUTOML_MODELS_OUT_PATH, company_name.lower())
    os.makedirs(results_path, exist_ok=True)
    automl = AutoML(results_path=results_path, explain_level=0)
    automl.fit(X_train, y_train)

    prediction = []
    first = True
    for rows in range(-30, 0):
        if not first:
            # Update moving average over last 30 days
            # by taking into consideration the last predicted value
            final_prediction_df.iloc[rows]['close[t-1]'] = prediction[-1]

            if rows == -1:
                final_prediction_df.iloc[rows]['close[t-1]_7_min'] = final_prediction_df.iloc[rows - 6:][
                    'close[t-1]'].min()
                final_prediction_df.iloc[rows]['close[t-1]_7_max'] = final_prediction_df.iloc[rows - 6:][
                    'close[t-1]'].max()
                final_prediction_df.iloc[rows]['close[t-1]_7_mean'] = final_prediction_df.iloc[rows - 6:][
                    'close[t-1]'].mean()
                final_prediction_df.iloc[rows]['close[t-1]_7_std'] = final_prediction_df.iloc[rows - 6:][
                    'close[t-1]'].std()
            else:
                final_prediction_df.iloc[rows]['close[t-1]_7_min'] = final_prediction_df.iloc[rows - 6:rows + 1][
                    'close[t-1]'].min()
                final_prediction_df.iloc[rows]['close[t-1]_7_max'] = final_prediction_df.iloc[rows - 6:rows + 1][
                    'close[t-1]'].max()
                final_prediction_df.iloc[rows]['close[t-1]_7_mean'] = final_prediction_df.iloc[rows - 6:rows + 1][
                    'close[t-1]'].mean()
                final_prediction_df.iloc[rows]['close[t-1]_7_std'] = final_prediction_df.iloc[rows - 6:rows + 1][
                    'close[t-1]'].std()
            final_prediction_df.iloc[rows]['close[t-1]_14_min'] = final_prediction_df.iloc[rows - 7]['close[t-1]_7_min']
            final_prediction_df.iloc[rows]['close[t-1]_14_max'] = final_prediction_df.iloc[rows - 7]['close[t-1]_7_max']
            final_prediction_df.iloc[rows]['close[t-1]_14_mean'] = final_prediction_df.iloc[rows - 7][
                'close[t-1]_7_mean']
            final_prediction_df.iloc[rows]['close[t-1]_14_std'] = final_prediction_df.iloc[rows - 7]['close[t-1]_7_std']

        a = automl.predict(X_test.iloc[[rows]])[0]
        prediction.append(a)
        first = False
        # report performance

    mse = mean_squared_error(y_test, prediction)
    automl_rmse = np.sqrt(mse)
    automl_mape = np.mean(np.abs(y_test - prediction) / np.abs(y_test))
    # print('RMSE: %.3f' % rmse,  'MAPE: %.3f' % mape)

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=y_test,
                             mode='lines',
                             name='actual'))
    fig.add_trace(go.Scatter(y=prediction,
                             mode='lines',
                             name='prediction'))
    fig.update_layout(
        title='Forecast of {} Stock Price for last 30 days (AutoML)'.format(company_name.upper()),
        xaxis_title="Days",
        yaxis_title="Price",
        # legend_title="Legend Title",
    )

    return fig

@app.callback(
    Output("stock_values_graph", "figure"),
    [
        Input("ticker-select", "value"),
    ],
)
def update_stock_values_graph(ticker):
    stocks_df = pd.read_csv(STOCK_FILES_PATH.joinpath(ticker + '.csv'))
    stocks_df = stocks_df[['date', 'close']]
    fig = px.line(stocks_df, x="date", y="close",
		title='Stock Trend for {} over time'.format(ticker.upper()))
    return fig

@app.callback(
    [
        Output("stock_pmdarima_graph", "figure"),
        Output("arima_mape_div", "children"),
        Output("arima_rmse_div", "children"),
    ],
    [
        Input("ticker-select", "value"),
    ],
)
def update_stock_pmdarima_graph(ticker):
    stocks_df = pd.read_csv(STOCK_FILES_PATH.joinpath(ticker + '.csv'))
    stocks_df = stocks_df.set_index('date')
    stocks_df = stocks_df[['close']]
    return pmdarima_model_eval(stocks_df, ticker)

@app.callback(
    [
        Output("stock_prophet_graph", "figure"),
        Output("prophet_mape_div", "children"),
        Output("prophet_rmse_div", "children"),
    ],
    [
        Input("ticker-select", "value"),
    ],
)
def update_stock_prophet_graph(ticker):
    stocks_df = pd.read_csv(STOCK_FILES_PATH.joinpath(ticker + '.csv'))
    stocks_df = stocks_df.set_index('date')
    stocks_df = stocks_df[['close']]
    return prophet_model_eval(stocks_df, ticker)

@app.callback(
    Output("stock_automl_graph", "figure"),
    [
        Input("ticker-select", "value"),
    ],
)
def update_stock_automl_graph(ticker):
    stocks_df = pd.read_csv(os.path.join(AUTOML_FILES_PATH, ticker + '.csv'))
    stocks_df['date'] = stocks_df['date'].astype('datetime64')
    stocks_df = stocks_df.set_index('date')

    return automl_model_eval(stocks_df, ticker)


# Run the server
if __name__ == "__main__":
    app.run_server(debug=True, port=8080)
