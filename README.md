
# Stock Sense — AI-Powered Supermarket Stock Management System

Stock Sense is a supermarket stock management web application designed to help supermarket owners manage products, monitor inventory, analyze sales, and generate reports. It combines a web-based dashboard with an AI assistant to make stock and sales information easier to understand.

The system uses Python and Flask for the backend, MongoDB for data storage, Ollama for local AI model execution, and HTML, CSS, and JavaScript for the frontend.

## Features

- **Inventory Management** — Manage supermarket products and their stock information.
- **Stock Monitoring** — View product availability and identify stock-related issues.
- **Sales Analysis** — Analyze sales information to support business decisions.
- **AI Assistant** — Ask questions about products, inventory, and sales using natural language.
- **Dashboard** — Access important supermarket information through a web interface.
- **PDF Reports** — Generate downloadable reports when supported by the application.
- **Database Integration** — Store and retrieve application data using MongoDB.
- **Responsive Interface** — Use the website on desktop and mobile screens.

> Note: The available features depend on the implementation in the project source code.

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
supermarket-agent/
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

The structure above is illustrative. Your actual folders and filenames may differ.

## Requirements

Install the following before running the application:

- Python 3.11 or 3.12 recommended
- Git
- MongoDB Atlas account, or another MongoDB deployment
- Ollama
- An internet connection for initial installation and cloud database access

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/stock-sense-ai-supermarket-management.git
cd stock-sense-ai-supermarket-management
```

Replace `YOUR_USERNAME` with your GitHub username and use your actual repository URL.

### 2. Open the Backend Folder

Open the project in PyCharm and navigate to the backend directory.

For Windows PowerShell:

```powershell
cd "backend"
```

### 3. Create a Python Virtual Environment

```powershell
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If you use Command Prompt instead:

```bat
.venv\Scripts\activate.bat
```

### 4. Install Dependencies

Make sure the virtual environment is active, then run:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configure MongoDB Atlas

1. Create an account at https://www.mongodb.com/cloud/atlas.
2. Create a MongoDB deployment.
3. Create a database user with the permissions required by the application.
4. Add your current public IP address under **Network Access**.
5. Select **Connect → Drivers** and copy the Python connection string.
6. Replace the username, password, and cluster placeholders with your actual credentials.

### 6. Configure Environment Variables

Create a file named `.env` inside the `backend` folder. Use the following as a template:

```env
MONGO_URI=mongodb+srv://YOUR_USERNAME:YOUR_PASSWORD@YOUR_CLUSTER.mongodb.net/
DB_NAME=supermarket_db
OLLAMA_MODEL=llama3.2
CURRENCY=$
PORT=5000
```

Replace the MongoDB placeholders with your actual connection details.

If your MongoDB password contains special characters, URL-encode those characters in the connection string.

Keep `.env` private. Never upload it to GitHub or share your real database credentials.

Your `.env.example` file should contain only placeholder values, never real secrets.

### 7. Install and Run Ollama

Download Ollama from:

https://ollama.com/download

After installation, open a terminal and download the model:

```bash
ollama pull llama3.2
```

Check that the model is available:

```bash
ollama list
```

If Ollama is not already running, start its service using:

```bash
ollama serve
```

Keep the Ollama service running while using AI features. If your application uses a different model or AI provider, follow the corresponding configuration.

### 8. Start the Application

From the backend directory, run:

```bash
python app.py
```

If the application starts successfully, open the address shown in the terminal. If it uses the default Flask port, visit:

http://127.0.0.1:5000

Keep the backend terminal open while using the application.

## Using the AI Assistant

Depending on the tools implemented in the application, you may be able to ask questions such as:

- "Show me the current stock information for Fresh Milk."
- "Analyze the recent sales of milk, bread, and eggs."
- "Which products may need restocking?"
- "Summarize the supermarket's sales performance."
- "Generate a PDF report for the selected sales period."

The answers depend on the information stored in the database and the capabilities implemented in the AI agent.

## Database Configuration

The application is configured to use MongoDB through the `MONGO_URI` environment variable.

The database name is configured through:

```env
DB_NAME=supermarket_db
```

Collection names, initial sample data, and automatic database initialization depend on the backend implementation. Verify these details in `app.py` before manually creating collections or importing data.

## Troubleshooting

### MongoDB Connection Error

If the application reports a connection failure:

- Verify that `MONGO_URI` contains the correct Atlas connection string.
- Confirm that your IP address is allowed in MongoDB Atlas Network Access.
- Check the database username and password.
- Ensure special characters in the password are URL-encoded.
- Confirm that the application loads `.env` from the backend directory.

### Ollama or AI Model Error

If the AI assistant does not respond:

- Confirm Ollama is installed.
- Run `ollama list` to verify that the model is available.
- Run `ollama pull llama3.2` if the model is missing.
- Ensure the configured model name matches the installed model.
- Check the backend terminal for error messages.

### Python Module Not Found

Activate the virtual environment and install the dependencies again:

```bash
pip install -r requirements.txt
```

### Port Already in Use

If port 5000 is occupied, stop the other application using it or configure a different port if the application supports that setting.

## Security

- Never commit `.env` or real credentials.
- Use `.env.example` to document required configuration variables.
- Do not publish database passwords, API keys, or private connection strings.
- Grant the database user only the permissions it needs.
- Restrict MongoDB Network Access instead of allowing unrestricted access where possible.
- Rotate credentials immediately if they are accidentally exposed.
- Do not commit virtual environments, cache files, or generated reports unnecessarily.

## Version Control

To check the files Git is tracking:

```bash
git status
```

To add and commit your project:

```bash
git add .
git commit -m "Initial Stock Sense project"
git push origin main
```

Ensure that `.env` is ignored before committing. If it was committed previously, removing it from `.gitignore` tracking requires additional Git steps; changing `.gitignore` alone does not remove it from earlier commits.

## Future Improvements

Possible improvements include:

- Low-stock alerts and reorder suggestions
- More detailed sales analytics
- Product category and supplier management
- Sales forecasting
- Inventory trend visualizations
- Improved AI-assisted business recommendations
- User authentication and role-based access
- Additional report formats

These are potential enhancements and are not necessarily implemented in the current version.

## License

No license has been specified yet. Add a `LICENSE` file if you intend to publish the project under an open-source license.

---

**Stock Sense** — Smarter inventory management through data and AI.
