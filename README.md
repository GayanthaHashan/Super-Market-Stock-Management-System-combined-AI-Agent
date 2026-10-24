
# AI-Powered Supermarket Stock Management System

An AI-powered web application designed to help supermarket owners manage inventory, monitor product availability, analyze sales data, and generate reports. The system combines a web-based dashboard with an AI assistant to make stock management and business analysis easier.

The application uses Python and Flask for the backend, MongoDB for data storage, Ollama for local AI model execution, and HTML, CSS, and JavaScript for the frontend.

## Features

- **Inventory Management** — Manage supermarket products and stock information.
- **Stock Monitoring** — Track product availability and identify stock-related issues.
- **Sales Analysis** — Analyze sales data to support business decisions.
- **AI Assistant** — Ask questions about products, inventory, and sales using natural language.
- **Dashboard** — View important supermarket information through a web interface.
- **PDF Reports** — Generate downloadable reports if supported by the application.
- **Database Integration** — Store and retrieve application data using MongoDB.
- **Responsive Interface** — Access the website on desktop and mobile screens.

> Note: Features depend on the functionality implemented in the source code.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| Flask | Web application framework |
| MongoDB Atlas | Cloud database |
| PyMongo | Python connection to MongoDB |
| Ollama | Local AI model execution |
| Llama 3.2 | AI language model |
| LangChain / LangGraph | AI agent workflows, if configured |
| HTML | Web page structure |
| CSS | Styling and responsive layouts |
| JavaScript | Frontend interactions |
| ReportLab | PDF report generation, if configured |
| Git and GitHub | Version control and project hosting |

## Project Structure

```text
AI-Powered-Supermarket-Stock-Management-System/
│
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── .env.example
│   └── reports/
│
├── frontend/
│   ├── index.html
│   ├── css/
│   └── js/
│
├── .gitignore
├── README.md
└── SETUP_GUIDE.md
```

*This is an example structure. Your actual folders and filenames may differ.*

## Requirements

Before running the application, install:

- Python 3.11 or 3.12 (recommended)
- Git
- A MongoDB Atlas account or another MongoDB deployment
- Ollama
- An internet connection for initial setup and cloud database access

## Installation and Setup

### 1. Clone the Repository

Replace `YOUR_USERNAME` with your GitHub username.

```bash
git clone https://github.com/YOUR_USERNAME/AI-Powered-Supermarket-Stock-Management-System.git
cd AI-Powered-Supermarket-Stock-Management-System
```

### 2. Open the Backend Folder

Open the project in PyCharm and navigate to the backend directory.

For Windows PowerShell:

```powershell
cd backend
```

### 3. Create a Python Virtual Environment

```powershell
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

For Windows Command Prompt:

```bat
.venv\Scripts\activate.bat
```

### 4. Install Dependencies

Ensure the virtual environment is activated, then run:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configure MongoDB Atlas

1. Create an account at https://www.mongodb.com/cloud/atlas.
2. Create a MongoDB deployment.
3. Create a database user with the permissions required by the application.
4. Add your public IP address under **Network Access**.
5. Select **Connect → Drivers** and copy the Python connection string.
6. Replace the username, password, and cluster placeholders with your actual details.

### 6. Configure Environment Variables

Create a file named `.env` inside the `backend` folder.

Use the following template:

```env
MONGO_URI=mongodb+srv://YOUR_USERNAME:YOUR_PASSWORD@YOUR_CLUSTER.mongodb.net/
DB_NAME=supermarket_db
OLLAMA_MODEL=llama3.2
CURRENCY=$
PORT=5000
```

Replace the MongoDB placeholders with your actual connection details. URL-encode special characters in your password if necessary.

**Security:** Never upload your real `.env` file, database credentials, or private connection strings to GitHub. Keep `.env.example` free of real secrets.

### 7. Install and Run Ollama

Download Ollama from:

https://ollama.com/download

Download the Llama 3.2 model:

```bash
ollama pull llama3.2
```

Verify that it is installed:

```bash
ollama list
```

If Ollama is not already running, start its service:

```bash
ollama serve
```

Keep Ollama running while using the AI features. If the project uses another model or AI provider, follow the configuration specified in the source code.

### 8. Run the Application

From the backend directory, execute:

```bash
python app.py
```

If the application starts successfully on the default Flask port, open:

http://127.0.0.1:5000

Keep the backend terminal open while using the application.

## Using the AI Assistant

Depending on the functionality implemented in the project, example questions may include:

- "Show me the current stock information for Fresh Milk."
- "Analyze the recent sales of milk, bread, and eggs."
- "Which products may need restocking?"
- "Summarize the supermarket's sales performance."
- "Generate a PDF report for the selected sales period."

The results depend on the data stored in the database and the capabilities of the AI assistant.

## Database Configuration

The application uses the `MONGO_URI` environment variable to connect to MongoDB.

The database name is configured using:

```env
DB_NAME=supermarket_db
```

Collection names, sample data, and automatic database initialization depend on the backend implementation. Check `app.py` before manually creating collections or importing data.

## Troubleshooting

### MongoDB Connection Error

- Check that `MONGO_URI` contains the correct connection string.
- Confirm that your IP address is allowed in MongoDB Atlas Network Access.
- Verify the database username and password.
- URL-encode special characters in the password.
- Ensure the application loads `.env` from the backend directory.

### Ollama or AI Model Error

- Confirm that Ollama is installed and running.
- Run `ollama list` to verify that the model is available.
- Run `ollama pull llama3.2` if the model is missing.
- Check that the configured model name matches the installed model.
- Review the backend terminal for error messages.

### Python Module Not Found

Activate the virtual environment and reinstall the required packages:

```bash
pip install -r requirements.txt
```

### Port Already in Use

If port 5000 is already occupied, stop the application using it or configure a different port if the project supports that setting.

## Security Best Practices

- Never commit `.env` or real credentials.
- Use `.env.example` to document required environment variables.
- Grant database users only the permissions they need.
- Restrict MongoDB Network Access where possible.
- Rotate credentials immediately if they are exposed.
- Exclude virtual environments, cache files, and unnecessary generated reports from version control.

## Uploading Changes to GitHub

Check the files Git will track:

```bash
git status
```

Add and commit your project:

```bash
git add .
git commit -m "Initial project setup"
git push origin main
```

Ensure `.env` is ignored before committing. Adding it to `.gitignore` does not automatically remove a file that Git is already tracking.

## Future Improvements

Potential future enhancements include:

- Low-stock alerts and reorder suggestions
- Detailed sales analytics
- Product category and supplier management
- Sales forecasting
- Inventory trend visualizations
- Improved AI-assisted business recommendations
- User authentication and role-based access
- Additional report formats

These are possible improvements and are not necessarily included in the current implementation.

## License

No license has been specified yet. Add a `LICENSE` file if you intend to distribute the project under an open-source license.

---

**AI-Powered Supermarket Stock Management System** — Smarter inventory management through data and AI.
