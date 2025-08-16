# 🚀 Quick Installation Guide

## Prerequisites
- Python 3.8 or higher
- Groq API Key ([](https://console.groq.com/))

## One-Command Setup
```bash
python setup.py
```

This will:
- ✅ Install all dependencies
- ✅ Initialize the SQLite database with test users
- ✅ Create the permissions Excel file with role hierarchy
- ✅ Run comprehensive tests to verify everything works
- ✅ Display next steps

## Start the Application
```bash
streamlit run app.py
```

Then open: http://localhost:8501

## Demo Credentials
| Employee ID | Password | Role | Allowed Packages |
|-------------|----------|------|------------------|
| EMP001 | password123 | Associate Software Engineer | 6 packages (numpy, pandas, etc.) |
| EMP002 | password456 | Senior Software Engineer | 12 packages (includes ML frameworks) |
| EMP003 | password789 | Lead Software Engineer | 17 packages (includes DevOps tools) |
| EMP004 | passwordabc | Principal Software Engineer | 23 packages (includes cloud platforms) |

## Key Features
- 🤖 **Dual AI Modes**: Q&A chat + Installation automation
- 🔐 **Role-based Security**: Hierarchical permission inheritance
- 📦 **Smart Installation**: LangGraph-powered workflow
- 📊 **Excel Integration**: Easy permission management
- 📝 **Complete Logging**: All requests tracked in SQLite
- 🎨 **Modern UI**: Streamlit-based interface

## Example Installation Request
1. Login with demo credentials
2. Enter your Groq API key in the sidebar
3. Go to "Installation" tab
4. Type: "Install scikit-learn"
5. System will check permissions, validate package, and install if allowed

## File Structure
```
AutomatedTool_Assessment2/
├── app.py                 # Main Streamlit app
├── setup.py              # One-command setup script
├── db_setup.py           # Database operations
├── langgraph_flow.py     # LangGraph workflow
├── permissions_manager.py # Role-based permissions
├── utils.py              # Utilities & validation
├── config.py             # Configuration management
├── test_system.py        # Comprehensive tests
├── requirements.txt      # Dependencies
├── README.md            # Full documentation
└── permissions.xlsx      # Auto-generated permissions
```

## Need Help?
- Check `README.md` for detailed documentation
- Review logs in the `logs/` directory
- Run `python test_system.py` to verify installation
- All components include comprehensive error handling and logging
