# Digital Hub

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![Django Version](https://img.shields.io/badge/django-4.2.6-blue)

## 📖 Overview

**Digital Hub** is a Django-based project designed to provide a flexible and scalable foundation for building modern web applications. It leverages Django Rest Framework for API development and integrates with tools like Langchain for AI-driven features.

## 🚀 Features

- 🔗 **API Development** with Django Rest Framework.
- 🔐 **JWT Authentication** using SimpleJWT.
- 🌐 **CORS Support** for cross-origin requests.
- 🧠 **AI Integration** with Langchain and related modules.
- 📁 **File Handling** with PyMuPDF and python-magic-bin.
- 📊 **Environment Management** using python-dotenv.

## 📂 Project Structure

```bash
digital-hub/
├── manage.py
├── digital_hub/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   └── ...
├── pyproject.toml
└── README.md
```

## ⚙️ Installation

1. **Clone the repository:**

```bash
git clone https://github.com/your-username/digital-hub.git
cd digital-hub
```

2. **Install Poetry:**

```bash
pip install poetry
```

3. **Install dependencies using Poetry:**

```bash
poetry install
```

4. **Set up environment variables:**

Create a `.env` file in the project root:

```env
SECRET_KEY=your_secret_key
DEBUG=True
ALLOWED_HOSTS=*
```

5. **Run migrations:**

```bash
poetry run python manage.py migrate
```

6. **Start the development server:**

```bash
poetry run python manage.py runserver
```

Visit `http://localhost:8000/` in your browser.

## Production Deployment

1. Copy environment template and fill real values:
   ```bash
   cp .env.example .env
   ```
2. Set production env values in `.env`:
   - `DEBUG=False`
   - `SECRET_KEY=<long-random-secret>`
   - `ALLOWED_HOSTS=<comma-separated-hosts>`
   - `USE_SQLITE=False` with Postgres credentials
   - `CSRF_TRUSTED_ORIGINS` and `CORS_ALLOWED_ORIGINS`
3. Run deployment checks:
   ```bash
   python core/manage.py check --deploy
   ```
4. Run migrations and collect static:
   ```bash
   python core/manage.py migrate
   python core/manage.py collectstatic --noinput
   ```
5. Start ASGI app with Daphne (example):
   ```bash
   daphne -b 0.0.0.0 -p 8000 project.asgi:application
   ```
6. Run Celery worker separately:
   ```bash
   celery -A project worker -l info
   ```



# Server Installation (Linux)

1. **Install Celery**:
   ```bash
   pip install celery
   ```

2. **Install RabbitMQ**:
   ```bash
   sudo apt-get install rabbitmq-server
   ```

3. **Enable and start RabbitMQ**:
   ```bash
   sudo systemctl enable rabbitmq-server
   sudo systemctl start rabbitmq-server
   ```

4. **Check RabbitMQ server status**:
   ```bash
   systemctl status rabbitmq-server
   ```

5. **Run Celery worker**:
   ```bash
   celery -A project worker -l info
   ```

## 📦 Dependencies

- Django `==4.2.6`
- djangorestframework `>=3.15.2,<4.0.0`
- Pillow `>=11.1.0,<12.0.0`
- django-cors-headers `>=4.7.0,<5.0.0`
- djangorestframework-simplejwt `>=5.4.0,<6.0.0`
- langchain `>=0.3.18,<0.4.0`
- langchain-ollama `>=0.2.3,<0.3.0`
- langchain-chroma `>=0.2.2,<0.3.0`
- langchain-community `>=0.3.17,<0.4.0`
- pymupdf `>=1.25.3,<2.0.0`
- rest-framework-simplejwt `>=0.0.2,<0.0.3`
- python-magic-bin `>=0.4.14,<0.5.0`
- python-dotenv `>=1.0.1,<2.0.0`

## 🧑‍💻 Authors

- **Mikiyas Degefu**  
  📧 [mikiyas.m.degefu@gmail.com](mailto:mikiyas.m.degefu@gmail.com)

- **Kaleab Hegie**  
  📧 [benjiyg400@gmail.com](mailto:benjiyg400@gmail.com)
