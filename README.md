# 📈 Wall Street Weekly - Portfolio Newsletter Service

A professional portfolio newsletter service that automatically generates personalized market analysis and performance reports for your investment portfolio.

## 🚀 Features

- **📤 Portfolio Upload**: Upload PDF, DOCX, Excel, or CSV files containing your portfolio holdings
- **🤖 AI-Powered Analysis**: Uses OpenAI to extract and analyze portfolio data
- **📊 Real-time Market Data**: Fetches current stock prices and historical performance
- **📧 Automated Newsletters**: Generates personalized weekly newsletters with market insights
- **💾 Google Sheets Integration**: Stores portfolio data securely in Google Sheets
- **🎨 Professional UI**: Beautiful, modern interface with responsive design

## 🛠️ Technology Stack

- **Frontend**: Streamlit (Python)
- **AI/ML**: OpenAI GPT-4
- **Data Storage**: Google Sheets API
- **Email**: Gmail SMTP
- **Stock Data**: OpenAI Web Search (replaces Yahoo Finance)

## 📋 Prerequisites

- Python 3.8+
- OpenAI API key
- Google Sheets API credentials
- Gmail App Password

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd portfolio-newsletter-main
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Up Configuration

Create a `.streamlit/secrets.toml` file with your API keys:

```toml
OPENAI_API_KEY = "your-openai-api-key"
GMAIL_APP_PASSWORD = "your-gmail-app-password"

[sheets_credentials]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "your-private-key"
client_email = "your-service-account-email"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "your-cert-url"
```

### 4. Run the Application
```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`

## 📁 Project Structure

```
portfolio-newsletter-main/
├── app.py                      # Main Streamlit application
├── main.py                     # Newsletter generation logic
├── portfolio_analysis.py       # Portfolio analysis functions
├── stock_data_service.py       # Stock data fetching service
├── google_sheets_storage.py    # Google Sheets integration
├── market_recap.py             # Market analysis generation
├── requirements.txt            # Python dependencies
├── templates/                  # Email templates
│   ├── weekly_pulse.html      # HTML email template
│   └── weekly_pulse.txt       # Text email template
└── .streamlit/                 # Streamlit configuration
    ├── config.toml            # App configuration
    └── secrets.toml           # API keys (not in repo)
```

## 🔧 Configuration

### Streamlit Configuration
The app uses a custom Streamlit configuration to disable XSRF protection for file uploads:

```toml
[server]
enableXsrfProtection = false

[browser]
gatherUsageStats = false
```

### Google Sheets Setup
1. Create a Google Cloud Project
2. Enable Google Sheets API
3. Create a service account
4. Download credentials JSON
5. Share your Google Sheet with the service account email

## 📧 Newsletter Features

- **Portfolio Performance Summary**: Weekly and YTD performance analysis
- **Market Highlights**: AI-generated market recap and insights
- **Holdings Analysis**: Individual stock analysis with news and trends
- **Professional Design**: Beautiful HTML email template with responsive design

## 🔒 Security

- API keys are stored securely in Streamlit secrets
- Google Sheets credentials are encrypted
- No sensitive data is logged or stored in plain text

## 🚀 Deployment

### Streamlit Cloud
1. Push your code to GitHub
2. Connect your repository to Streamlit Cloud
3. Add your secrets in the Streamlit Cloud dashboard
4. Deploy!

### Other Platforms
The app can be deployed on any platform that supports Streamlit:
- Heroku
- AWS
- Google Cloud Platform
- DigitalOcean

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support or questions, please contact:
- Email: [your-email]
- GitHub Issues: [repository-issues]

## 🔄 Updates

- **v1.0**: Initial release with basic portfolio analysis
- **v1.1**: Added AI-powered market analysis
- **v1.2**: Enhanced UI/UX with professional styling
- **v1.3**: Improved file upload and error handling

---

**Built with ❤️ for professional portfolio management** 