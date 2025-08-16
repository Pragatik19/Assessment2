# 🔧 Automated System Setup Tool

A comprehensive automated system setup tool with dual AI interaction modes, featuring Groq LLM for general Q&A and LangGraph-powered workflow for installation automation.

## ✨ Features

### 🤖 Dual AI Interaction Modes
- **Q&A Mode**: General chat interface powered by Groq LLM
- **Install Mode**: Automated package installation via LangGraph workflow

### 🔐 Authentication & Authorization
- SQLite-based user authentication
- Role-based permission system with hierarchical inheritance
- Excel-based permission configuration

### 📦 Package Management
- Automated package installation using subprocess/pip
- Version checking and validation
- Comprehensive request logging and tracking

### 🎨 User Interface
- Modern Streamlit-based web interface
- Responsive design with sidebar navigation
- Real-time status updates and progress tracking

## 🏗️ Architecture

```
├── app.py                 # Main Streamlit application
├── db_setup.py           # Database schema and operations
├── langgraph_flow.py     # LangGraph workflow implementation
├── permissions_manager.py # Role-based permission system
├── utils.py              # Utility functions and validation
├── config.py             # Configuration management
├── test_system.py        # Comprehensive test suite
├── requirements.txt      # Python dependencies
├── permissions.xlsx      # Role-permission mappings (auto-generated)
└── README.md            # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Groq API Key ([Get one here](https://console.groq.com/))
- Write permissions in your Python environment (for package installation)

### Installation

1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd AutomatedTool_Assessment2
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Setup environment variables**
   ```bash
   cp env.example .env
   # Edit .env file and add your GROQ_API_KEY
   ```

4. **Initialize the system**
   ```bash
   python db_setup.py
   python permissions_manager.py
   ```

5. **Run tests (optional)**
   ```bash
   python test_system.py
   python test_real_installation.py  # Test actual package installation
   ```

6. **Start the application**
   ```bash
   streamlit run app.py
   ```

7. **Access the application**
   - Open your browser to `http://localhost:8501`
   - Use the demo credentials provided on the login page

## 🔑 Demo Credentials

| Employee ID | Password | Role |
|-------------|----------|------|
| EMP001 | password123 | Associate Software Engineer |
| EMP002 | password456 | Senior Software Engineer |
| EMP003 | password789 | Lead Software Engineer |
| EMP004 | passwordabc | Principal Software Engineer |

## 📋 User Guide

### 1. Login
- Enter your Employee ID and Password
- The system will identify your role and permissions

### 2. Configuration
- Enter your Groq API Key in the sidebar
- Without an API key, only basic functionality is available

### 3. Q&A Chat
- Ask general questions in the chat interface
- Powered by Groq's Mixtral model
- No logging for general queries

### 4. Package Installation
- Use natural language to request installations:
  - "Install TensorFlow"
  - "Set up Python 3.11"
  - "Add scikit-learn latest version"
- The system will:
  - Parse your intent
  - Check permissions
  - Validate the package
  - Execute installation
  - Log the request

### 5. View Permissions
- Check your allowed packages in the Permissions tab
- Understand the role hierarchy
- Search and filter available packages

## 🔒 Permission System

### Role Hierarchy (with inheritance)
1. **Associate Software Engineer**: Basic packages (numpy, pandas, requests, etc.)
2. **Senior Software Engineer**: Inherits Associate + ML frameworks (tensorflow, pytorch, etc.)
3. **Lead Software Engineer**: Inherits Senior + DevOps tools (kubernetes, terraform, etc.)
4. **Principal Software Engineer**: Inherits Lead + Cloud platforms (aws-cli, azure-cli, etc.)

### Permission Rules
- Higher roles inherit ALL permissions from lower roles
- Permissions are defined in `permissions.xlsx`
- The system supports hierarchical inheritance automatically

## 🛠️ Technical Details

### Tech Stack
- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: SQLite
- **LLM**: Groq (Mixtral-8x7b-32768)
- **Workflow**: LangGraph
- **Permissions**: Excel (XLSX)

### Database Schema

#### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    employee_id TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Requests Table
```sql
CREATE TABLE requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    package_name TEXT NOT NULL,
    version TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    complete_time TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
```

### LangGraph Workflow

The installation workflow follows these steps:

1. **Intent Interpretation**: Parse user input to detect installation requests
2. **Request Logging**: Log the request to the database
3. **Permission Check**: Verify user has permission for the package
4. **Version Validation**: Check available package versions
5. **Installation Execution**: Run pip install with proper error handling
6. **Status Update**: Update database with completion status

### Security Features

- Password hashing (SHA-256)
- Input sanitization and validation
- Package name validation to prevent injection
- Blocked package list for security
- Timeout protection for installations
- Comprehensive logging and audit trails

## 🧪 Testing

Run the comprehensive test suite:

```bash
python test_system.py
```

The test suite covers:
- Database operations
- Permission management
- Utility functions
- Configuration validation
- Component integration

## 📁 File Descriptions

### Core Files

- **`app.py`**: Main Streamlit application with UI and user interactions
- **`db_setup.py`**: Database schema, initialization, and CRUD operations
- **`langgraph_flow.py`**: LangGraph workflow for installation automation
- **`permissions_manager.py`**: Role-based permission system with Excel integration

### Supporting Files

- **`utils.py`**: Utility functions, validation, and error handling
- **`config.py`**: Configuration management and logging setup
- **`test_system.py`**: Comprehensive test suite
- **`requirements.txt`**: Python package dependencies

### Generated Files

- **`permissions.xlsx`**: Auto-generated Excel file with role-permission mappings
- **`system_setup.db`**: SQLite database (created on first run)
- **`logs/`**: Directory containing application logs

## 🚨 Troubleshooting

### Common Issues

1. **"Module not found" errors**
   - Ensure all dependencies are installed: `pip install -r requirements.txt`

2. **Database initialization fails**
   - Check write permissions in the project directory
   - Ensure SQLite is available

3. **Permission denied for package installation**
   - Check your role's allowed packages in the Permissions tab
   - Contact admin to add packages to your role

4. **Groq API errors**
   - Verify your API key is correct
   - Check your Groq account quota and limits

5. **Installation timeouts**
   - Large packages may take time to install
   - Check your internet connection
   - Some packages may require additional system dependencies

### Logging

- Application logs are stored in the `logs/` directory
- Error logs are separated into `error.log`
- Set `LOG_LEVEL` environment variable to control verbosity

## 🔧 Configuration

### Environment Variables

- `GROQ_API_KEY`: Your Groq API key
- `DEBUG`: Set to "true" for debug mode
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `DATABASE_URL`: Custom database path
- `PERMISSIONS_FILE`: Custom permissions file path

### Feature Flags

Modify `config.py` to enable/disable features:

```python
FEATURE_FLAGS = {
    "enable_version_checking": True,
    "enable_package_validation": True,
    "enable_installation_logging": True,
    "enable_permission_inheritance": True,
    "enable_dry_run_mode": False
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the test suite
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support, please:
1. Check the troubleshooting section
2. Review the logs in the `logs/` directory
3. Run the test suite to identify issues
4. Contact the development team

---

**Built with ❤️ using Groq LLM, LangGraph, and Streamlit**
