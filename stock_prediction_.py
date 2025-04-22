

# Stock Analysis System for Google Colab
# This notebook performs real-time stock data collection, analysis and visualization

# Install required packages
!pip install yfinance pandas numpy matplotlib seaborn plotly scikit-learn statsmodels tensorflow  kaleido

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
from statsmodels.tsa.arima.model import ARIMA
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
import warnings
import io
import base64
from google.colab import files
warnings.filterwarnings('ignore')

# Set plotting style
plt.style.use('fivethirtyeight')
sns.set_style('whitegrid')

class StockAnalysisSystem:
    def __init__(self):
        self.stock_data = {}
        self.market_data = None
        self.models = {}
        self.predictions = {}
        self.technical_indicators = {}

    def collect_stock_data(self, symbols, period='1y', interval='1d'):
        """Collect historical stock data for analysis"""
        print(f"Collecting data for {len(symbols)} stocks...")

        for symbol in symbols:
            try:
                # Get stock data
                ticker = yf.Ticker(symbol)
                data = ticker.history(period=period, interval=interval)

                if not data.empty:
                    # Add symbol identifier
                    data['Symbol'] = symbol

                    # Calculate daily returns
                    data['Daily_Return'] = data['Close'].pct_change() * 100

                    # Calculate cumulative returns
                    data['Cum_Return'] = (1 + data['Daily_Return']/100).cumprod() - 1
                    data['Cum_Return'] = data['Cum_Return'] * 100

                    # Store data
                    self.stock_data[symbol] = data
                    print(f"✓ Successfully collected data for {symbol} ({len(data)} records)")
                else:
                    print(f"✗ No data returned for {symbol}")

            except Exception as e:
                print(f"✗ Error collecting data for {symbol}: {str(e)}")

        # Get market index data for comparison (S&P 500)
        try:
            self.market_data = yf.download('^GSPC', period=period, interval=interval)
            self.market_data['Daily_Return'] = self.market_data['Close'].pct_change() * 100
            self.market_data['Cum_Return'] = (1 + self.market_data['Daily_Return']/100).cumprod() - 1
            self.market_data['Cum_Return'] = self.market_data['Cum_Return'] * 100
            print(f"✓ Successfully collected market data (S&P 500)")
        except Exception as e:
            print(f"✗ Error collecting market data: {str(e)}")

        print("Data collection complete!")

    def calculate_technical_indicators(self):
        """Calculate technical indicators for each stock"""
        print("Calculating technical indicators...")

        for symbol, data in self.stock_data.items():
            # Create a copy of the data
            df = data.copy()

            # Simple Moving Averages
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['SMA_50'] = df['Close'].rolling(window=50).mean()
            df['SMA_200'] = df['Close'].rolling(window=200).mean()

            # Exponential Moving Averages
            df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
            df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()

            # MACD
            df['MACD'] = df['EMA_12'] - df['EMA_26']
            df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

            # Relative Strength Index (RSI)
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / avg_loss
            df['RSI'] = 100 - (100 / (1 + rs))

            # Bollinger Bands
            df['BB_Middle'] = df['Close'].rolling(window=20).mean()
            df['BB_Std'] = df['Close'].rolling(window=20).std()
            df['BB_Upper'] = df['BB_Middle'] + 2 * df['BB_Std']
            df['BB_Lower'] = df['BB_Middle'] - 2 * df['BB_Std']
            df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']

            # Momentum
            df['Momentum'] = df['Close'] / df['Close'].shift(10)

            # Store the calculated indicators
            self.technical_indicators[symbol] = df

            print(f"✓ Calculated indicators for {symbol}")

        print("Technical analysis complete!")

    def train_predict_lstm(self, symbol, prediction_days=30):
        """Train LSTM model for price prediction"""
        print(f"Training LSTM model for {symbol}...")

        # Get the stock data
        data = self.stock_data[symbol].copy()

        # Prepare data for LSTM
        close_prices = data['Close'].values.reshape(-1, 1)

        # Scale the data
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_data = scaler.fit_transform(close_prices)

        # Training data length
        training_data_len = int(np.ceil(len(scaled_data) * 0.8))

        # Create training dataset
        train_data = scaled_data[0:training_data_len, :]

        # Split into x_train and y_train
        time_steps = 60  # Number of time steps to look back

        x_train, y_train = [], []

        for i in range(time_steps, len(train_data)):
            x_train.append(train_data[i-time_steps:i, 0])
            y_train.append(train_data[i, 0])

        # Convert to numpy arrays
        x_train, y_train = np.array(x_train), np.array(y_train)

        # Reshape x_train for LSTM
        x_train = np.reshape(x_train, (x_train.shape[0], x_train.shape[1], 1))

        # Build LSTM model
        model = Sequential()
        model.add(LSTM(units=50, return_sequences=True, input_shape=(x_train.shape[1], 1)))
        model.add(Dropout(0.2))
        model.add(LSTM(units=50, return_sequences=False))
        model.add(Dropout(0.2))
        model.add(Dense(units=25))
        model.add(Dense(units=1))

        # Compile model
        model.compile(optimizer='adam', loss='mean_squared_error')

        # Train model
        model.fit(x_train, y_train, batch_size=32, epochs=20, verbose=0)

        # Test data
        test_data = scaled_data[training_data_len - time_steps:, :]

        x_test = []
        y_test = close_prices[training_data_len:, 0]

        for i in range(time_steps, len(test_data)):
            x_test.append(test_data[i-time_steps:i, 0])

        x_test = np.array(x_test)
        x_test = np.reshape(x_test, (x_test.shape[0], x_test.shape[1], 1))

        # Make predictions
        predictions = model.predict(x_test)
        predictions = scaler.inverse_transform(predictions)

        # Calculate metrics
        rmse = np.sqrt(mean_squared_error(y_test, predictions))

        # Make future predictions
        last_sequence = scaled_data[-time_steps:].reshape(1, time_steps, 1)
        future_predictions = []

        current_sequence = last_sequence

        for _ in range(prediction_days):
            # Get prediction
            pred = model.predict(current_sequence)[0][0]

            # Add to future predictions
            future_predictions.append(pred)

            # Update sequence for next prediction
            new_sequence = np.append(current_sequence[0][1:], pred)
            current_sequence = new_sequence.reshape(1, time_steps, 1)

        # Inverse transform
        future_predictions = scaler.inverse_transform(np.array(future_predictions).reshape(-1, 1))

        # Create dates for future predictions
        last_date = data.index[-1]
        future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=prediction_days)

        # Create DataFrame for future predictions
        future_df = pd.DataFrame(data={
            'Date': future_dates,
            'Predicted_Close': future_predictions.flatten()
        })
        future_df.set_index('Date', inplace=True)

        # Store model and predictions
        self.models[symbol] = model
        self.predictions[symbol] = {
            'historical': predictions,
            'future': future_df,
            'rmse': rmse,
            'scaler': scaler,
            'time_steps': time_steps
        }

        print(f"✓ LSTM model for {symbol} trained (RMSE: {rmse:.2f})")

        return model, predictions, future_df, rmse

    def visualize_stock_price(self, symbol):
        """Create interactive plot of stock price with technical indicators"""
        if symbol not in self.technical_indicators:
            print(f"No data available for {symbol}. Please run calculate_technical_indicators() first.")
            return None

        df = self.technical_indicators[symbol]

        # Create subplots
        fig = make_subplots(rows=4, cols=1,
                           shared_xaxes=True,
                           vertical_spacing=0.03,
                           row_heights=[0.5, 0.15, 0.15, 0.20])

        # Candlestick chart for price
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='Price'),
            row=1, col=1)

        # Add Moving Averages
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['SMA_20'],
            line=dict(color='blue', width=1),
            name='SMA 20'),
            row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['SMA_50'],
            line=dict(color='orange', width=1),
            name='SMA 50'),
            row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['SMA_200'],
            line=dict(color='red', width=1),
            name='SMA 200'),
            row=1, col=1)

        # Add Bollinger Bands
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['BB_Upper'],
            line=dict(color='gray', width=0.5),
            name='BB Upper'),
            row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['BB_Lower'],
            line=dict(color='gray', width=0.5),
            name='BB Lower',
            fill='tonexty'),
            row=1, col=1)

        # Add volume
        colors = ['green' if row['Open'] - row['Close'] <= 0
                  else 'red' for index, row in df.iterrows()]

        fig.add_trace(go.Bar(
            x=df.index,
            y=df['Volume'],
            marker_color=colors,
            name='Volume'),
            row=2, col=1)

        # Add MACD
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['MACD'],
            line=dict(color='blue', width=1),
            name='MACD'),
            row=3, col=1)

        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['MACD_Signal'],
            line=dict(color='red', width=1),
            name='Signal'),
            row=3, col=1)

        fig.add_trace(go.Bar(
            x=df.index,
            y=df['MACD_Hist'],
            marker_color=['green' if val >= 0 else 'red' for val in df['MACD_Hist']],
            name='Histogram'),
            row=3, col=1)

        # Add RSI
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['RSI'],
            line=dict(color='purple', width=1),
            name='RSI'),
            row=4, col=1)

        # Add RSI levels
        fig.add_trace(go.Scatter(
            x=df.index,
            y=[70] * len(df.index),
            line=dict(color='red', width=1, dash='dash'),
            name='Overbought'),
            row=4, col=1)

        fig.add_trace(go.Scatter(
            x=df.index,
            y=[30] * len(df.index),
            line=dict(color='green', width=1, dash='dash'),
            name='Oversold'),
            row=4, col=1)

        # Update layout
        fig.update_layout(
            title=f'{symbol} Technical Analysis',
            xaxis_rangeslider_visible=False,
            xaxis4_title='Date',
            yaxis_title='Price',
            yaxis2_title='Volume',
            yaxis3_title='MACD',
            yaxis4_title='RSI',
            height=900,
            width=1200,
            showlegend=False,
            template='plotly_white'
        )

        # Show figure
        fig.show()

        return fig

    def visualize_predictions(self, symbol):
        """Visualize historical and future predictions for a stock"""
        if symbol not in self.predictions:
            print(f"No predictions available for {symbol}. Please run train_predict_lstm() first.")
            return None

        # Get data
        stock_data = self.stock_data[symbol]
        predictions = self.predictions[symbol]

        # Create figure
        fig = go.Figure()

        # Add actual prices
        fig.add_trace(go.Scatter(
            x=stock_data.index,
            y=stock_data['Close'],
            mode='lines',
            name='Actual Price',
            line=dict(color='blue')
        ))

        # Add historical predictions
        train_len = len(stock_data) - len(predictions['historical'])

        fig.add_trace(go.Scatter(
            x=stock_data.index[train_len:],
            y=predictions['historical'].flatten(),
            mode='lines',
            name='Historical Predictions',
            line=dict(color='orange')
        ))

        # Add future predictions
        fig.add_trace(go.Scatter(
            x=predictions['future'].index,
            y=predictions['future']['Predicted_Close'],
            mode='lines',
            name='Future Predictions',
            line=dict(color='red')
        ))

        # Update layout
        fig.update_layout(
            title=f'{symbol} Price Predictions (RMSE: {predictions["rmse"]:.2f})',
            xaxis_title='Date',
            yaxis_title='Price',
            legend_title='Legend',
            height=600,
            width=1000,
            template='plotly_white'
        )

        # Show figure
        fig.show()

        return fig

    def portfolio_performance_analysis(self):
        """Analyze performance of all stocks in portfolio"""
        if not self.stock_data:
            print("No stock data available. Please run collect_stock_data() first.")
            return None

        # Extract cumulative returns for each stock
        cum_returns = pd.DataFrame()

        for symbol, data in self.stock_data.items():
            cum_returns[symbol] = data['Cum_Return']

        # Add market return
        cum_returns['S&P500'] = self.market_data['Cum_Return']

        # Set index name
        cum_returns.index.name = 'Date'

        # Calculate performance metrics
        latest_date = cum_returns.index.max()
        performance = pd.DataFrame(index=cum_returns.columns)

        # YTD Return
        start_of_year = datetime(latest_date.year, 1, 1)
        ytd_returns = []

        for col in cum_returns.columns:
            try:
                first_date = cum_returns.index[cum_returns.index >= start_of_year][0]
                first_value = cum_returns.loc[first_date, col]
                latest_value = cum_returns.loc[latest_date, col]
                ytd_return = ((latest_value - first_value) / (1 + first_value/100)) * 100
                ytd_returns.append(ytd_return)
            except:
                ytd_returns.append(np.nan)

        performance['YTD Return (%)'] = ytd_returns

        # 1 Month Return
        one_month_ago = latest_date - timedelta(days=30)
        monthly_returns = []

        for col in cum_returns.columns:
            try:
                first_date = cum_returns.index[cum_returns.index >= one_month_ago][0]
                first_value = cum_returns.loc[first_date, col]
                latest_value = cum_returns.loc[latest_date, col]
                monthly_return = ((latest_value - first_value) / (1 + first_value/100)) * 100
                monthly_returns.append(monthly_return)
            except:
                monthly_returns.append(np.nan)

        performance['1-Month Return (%)'] = monthly_returns

        # Daily volatility
        volatility = []

        for symbol, data in self.stock_data.items():
            vol = data['Daily_Return'].std()
            volatility.append(vol)

        # Add market volatility
        volatility.append(self.market_data['Daily_Return'].std())

        performance['Daily Volatility (%)'] = volatility

        # Annualized volatility
        performance['Annualized Volatility (%)'] = performance['Daily Volatility (%)'] * np.sqrt(252)

        # Create correlation matrix
        correlation = cum_returns.corr()

        # Plot cumulative returns
        fig1 = px.line(cum_returns,
                      title='Cumulative Returns Comparison',
                      labels={'value': 'Cumulative Return (%)', 'Date': 'Date'},
                      template='plotly_white',
                      height=600,
                      width=1000)

        fig1.update_layout(legend_title='Stocks')

        # Plot performance metrics
        fig2 = px.bar(performance.sort_values('YTD Return (%)'),
                     y='YTD Return (%)',
                     title='YTD Performance',
                     template='plotly_white',
                     height=500,
                     width=800)

        # Plot correlation heatmap
        fig3 = px.imshow(correlation,
                        text_auto=True,
                        color_continuous_scale='RdBu_r',
                        title='Correlation Matrix',
                        template='plotly_white',
                        height=700,
                        width=700)

        # Show figures
        fig1.show()
        fig2.show()
        fig3.show()

        return performance, correlation, fig1, fig2, fig3

   # At the beginning of the notebook, add kaleido installation
!pip install yfinance pandas numpy matplotlib seaborn plotly scikit-learn statsmodels tensorflow kaleido

# The rest of your code stays the same, but let's modify the export_analysis_report method to handle potential errors:

def export_analysis_report(self, symbols):
    """Generate a comprehensive analysis report"""
    from IPython.display import HTML, display
    import base64
    from io import BytesIO

    report = """
    <h1 style="text-align:center;">Stock Market Analysis Report</h1>
    <h3 style="text-align:center;">Generated on {}</h3>
    <hr>
    """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # 1. Market Overview
    report += """
    <h2>1. Market Overview</h2>
    <p>S&P 500 Performance:</p>
    """

    # Function to safely convert plot to image
    def fig_to_base64(fig, width=800, height=400):
        try:
            # First try using kaleido
            img_bytes = fig.to_image(format="png", width=width, height=height)
            return base64.b64encode(img_bytes).decode('ascii')
        except Exception as e:
            print(f"Warning: Could not convert figure to image: {str(e)}")
            print("Showing interactive plot instead. You can take a screenshot manually.")
            fig.show()
            # Return a placeholder image or empty string
            return ""

    # S&P 500 chart
    fig = px.line(self.market_data['Close'],
                  title='S&P 500 Index',
                  labels={'value': 'Price', 'Date': 'Date'})

    img_base64 = fig_to_base64(fig)
    if img_base64:
        report += f'<img src="data:image/png;base64,{img_base64}" width="800px">'
    else:
        report += "<p>Interactive chart displayed in notebook. Screenshot manually if needed.</p>"

    # 2. Individual Stock Analysis
    report += """
    <h2>2. Individual Stock Analysis</h2>
    """

    for symbol in symbols:
        report += f"<h3>{symbol} Analysis</h3>"

        # Basic info
        ticker = yf.Ticker(symbol)
        try:
            info = ticker.info

            report += f"""
            <table style="width:80%; border-collapse: collapse; margin-bottom: 20px;">
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>Company Name</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{info.get('longName', 'N/A')}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>Industry</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{info.get('industry', 'N/A')}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>Current Price</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${self.stock_data[symbol]['Close'].iloc[-1]:.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>Market Cap</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${info.get('marketCap', 0) / 1e9:.2f}B</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>52-Week High</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${info.get('fiftyTwoWeekHigh', 'N/A')}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;"><strong>52-Week Low</strong></td>
                    <td style="border: 1px solid #ddd; padding: 8px;">${info.get('fiftyTwoWeekLow', 'N/A')}</td>
                </tr>
            </table>
            """
        except Exception as e:
            report += f"<p>Detailed information not available: {str(e)}</p>"

        # Technical chart - display interactively and provide screenshot instructions
        fig = self.visualize_stock_price(symbol)
        img_base64 = fig_to_base64(fig, width=800, height=600)
        if img_base64:
            report += f'<img src="data:image/png;base64,{img_base64}" width="800px">'
        else:
            report += "<p>Technical chart displayed interactively. Please screenshot if needed.</p>"

        # Prediction chart if available
        if symbol in self.predictions:
            fig = self.visualize_predictions(symbol)
            img_base64 = fig_to_base64(fig, width=800, height=400)
            report += f'<h4>Price Predictions</h4>'
            if img_base64:
                report += f'<img src="data:image/png;base64,{img_base64}" width="800px">'
            else:
                report += "<p>Prediction chart displayed interactively. Please screenshot if needed.</p>"

    # 3. Portfolio Analysis
    report += """
    <h2>3. Portfolio Analysis</h2>
    """

    # Performance metrics
    try:
        performance, correlation, fig1, fig2, fig3 = self.portfolio_performance_analysis()

        # Convert performance table to HTML
        performance_html = performance.to_html(classes='table table-striped', float_format=lambda x: f"{x:.2f}")
        report += performance_html

        # Add interactive charts and provide screenshot instructions
        fig1.show()
        fig2.show()
        fig3.show()

        report += "<p>Portfolio analysis charts are displayed interactively. Please take screenshots if needed.</p>"

    except Exception as e:
        report += f"<p>Portfolio analysis could not be completed: {str(e)}</p>"

    # 4. Conclusion
    report += """
    <h2>4. Conclusion and Recommendations</h2>
    <p>Based on the analysis conducted:</p>
    <ul>
    """

    # Generate simple recommendations
    for symbol in symbols:
        if symbol in self.predictions:
            try:
                last_price = self.stock_data[symbol]['Close'].iloc[-1]
                future_price = self.predictions[symbol]['future']['Predicted_Close'].iloc[-1]

                if future_price > last_price * 1.05:
                    report += f"<li><strong>{symbol}</strong>: Consider buying. The model predicts a potential {((future_price/last_price)-1)*100:.2f}% increase in the next 30 days.</li>"
                elif future_price < last_price * 0.95:
                    report += f"<li><strong>{symbol}</strong>: Consider selling. The model predicts a potential {((last_price/future_price)-1)*100:.2f}% decrease in the next 30 days.</li>"
                else:
                    report += f"<li><strong>{symbol}</strong>: Consider holding. The model predicts relatively stable price movement in the next 30 days.</li>"
            except Exception as e:
                report += f"<li><strong>{symbol}</strong>: Unable to generate recommendation due to error: {str(e)}</li>"

    report += """
    </ul>
    <p><em>Disclaimer: This analysis is for informational purposes only and should not be considered financial advice. Always conduct your own research before making investment decisions.</em></p>
    """

    # Display the report
    display(HTML(report))

    # Save report to HTML file
    with open("stock_analysis_report.html", "w") as f:
        f.write(report)

    # Download the file in Colab
    try:
        from google.colab import files
        files.download("stock_analysis_report.html")
        print("Report generated and downloaded successfully!")
    except Exception as e:
        print(f"Could not automatically download the report: {str(e)}")
        print("The report is saved as 'stock_analysis_report.html' in your current directory.")

# Replace the original method with this improved version
StockAnalysisSystem.export_analysis_report = export_analysis_report
# Example usage
if __name__ == "__main__":
    # Define stock symbols
    symbols = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META']

    # Create analysis system
    analysis_system = StockAnalysisSystem()

    # Collect data
    analysis_system.collect_stock_data(symbols)

    # Calculate technical indicators
    analysis_system.calculate_technical_indicators()

    # Train prediction models
    for symbol in symbols:
        analysis_system.train_predict_lstm(symbol)

    # Generate and download report
    analysis_system.export_analysis_report(symbols)
