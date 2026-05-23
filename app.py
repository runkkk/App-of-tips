import json # модуль Python json для разбора и создания JSON-данных (ответ Mistral API).
import os  # чтение переменных
from datetime import datetime # Импортирует класс datetime для хранения времени входа пользователя в БД.

import requests  # бмблиотека для работы с запросами
from flask import Flask, render_template_string, request, redirect, \
    url_for  # создание приложения, рендер шаблонов из строки, объект запроса, редиректы и построение URL.
from flask_sqlalchemy import SQLAlchemy  # переводчик между питоном и бд
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, \
    current_user  # Flask-Login -помнит, кто вошёл - как браслет в парке: надел один раз, ходишь везде. login_user - запомнить человека.logout_user - забыть.@login_required - «только для вошедших».current_user - кто сейчас на сайте.
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)  # создаем экземпляр приложения
app.secret_key = os.getenv("APP_SECRET_KEY")

# --- НАСТРОЙКА SQLALCHEMY ---
app.config[  # app.config — тетрадь настроек. Пишем адрес, где лежит база данных.
    'SQLALCHEMY_DATABASE_URI'] = f"postgresql://{os.getenv('PG_USER', 'postgres')}:{os.getenv('PG_PASSWORD', '')}@{os.getenv('PG_HOST', 'localhost')}:5432/{os.getenv('PG_DB', 'adviceapp')}"
# Указывает приложению адрес БД, порт, имя и учётные данные. Позволяет легко переносить проект между средами (dev/prod).
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # отключает отслеживание изменений объекта, не тратим силы зря

db = SQLAlchemy(app)  # привязывает алхимию к приложению

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
PORT = 5002


# --- МОДЕЛИ БАЗЫ ДАННЫХ ---

class User(UserMixin, db.Model):  # orm, UserMixin — правила для входа.db.Model— «это строка в таблице».
    __tablename__ = 'users'
    username = db.Column(db.String, primary_key=True)
    password = db.Column(db.String, nullable=False)  # Здесь будет ХЕШ

    def get_id(self):  # создаем сессию через имя пользователя
        return self.username


class LoginLog(db.Model):  # задаем таблицу классом
    __tablename__ = 'logins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, db.ForeignKey('users.username'), nullable=False)
    login_at = db.Column(db.DateTime, default=datetime.utcnow)


# --- ДИЗАЙН (LOGIN_HTML) ---
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Graphite Login</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: #121212;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    color: #e0e0e0;
  }

  .card {
    width: 100%;
    max-width: 400px;
    background: #1e1e1e;
    border: 1px solid #2d2d2d;
    border-radius: 4px; /* Sharp modern borders */
    padding: 50px 40px;
    box-shadow: 0 20px 50px rgba(0,0,0,0.8);
  }

  .brand {
    text-align: center;
    margin-bottom: 40px;
  }

  .brand-icon {
    font-size: 32px;
    margin-bottom: 15px;
    color: #60a5fa;
  }

  .brand h2 {
    font-size: 22px;
    font-weight: 300;
    color: #ffffff;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .field {
    margin-bottom: 20px;
  }

  .field label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    color: #666;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 8px;
  }

  .field input {
    width: 100%;
    padding: 12px;
    background: #121212;
    border: 1px solid #333;
    border-radius: 2px;
    color: #fff;
    font-size: 14px;
    outline: none;
    transition: all 0.2s;
  }

  .field input:focus {
    border-color: #60a5fa;
    background: #181818;
  }

  button[type=submit] {
    width: 100%;
    padding: 14px;
    background: #fdfdfd;
    border: none;
    border-radius: 2px;
    color: #000;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    cursor: pointer;
    transition: background 0.2s;
    margin-top: 10px;
  }

  button[type=submit]:hover { background: #60a5fa; color: #fff; }

  .error-msg {
    margin-top: 20px;
    padding: 10px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid #ef4444;
    color: #ef4444;
    font-size: 12px;
    text-align: center;
  }

  .hint {
    margin-top: 25px;
    text-align: center;
    font-size: 11px;
    color: #444;
  }
</style>
</head>
<body>
<div class="card">
  <div class="brand">
    <div class="brand-icon">⬢</div>
    <h2>Система</h2>
  </div>
  <form method="post">
    <div class="field">
      <label>User ID</label>
      <input name="username" placeholder="Login" autocomplete="username">
    </div>
    <div class="field">
      <label>Keyphrase</label>
      <input name="password" type="password" placeholder="Password" autocomplete="current-password">
    </div>
    <button type="submit">Access System</button>
  </form>
  {% if error %}<div class="error-msg">{{ error }}</div>{% endif %}
  <p class="hint">Auto-registration enabled for new identifiers.</p>
</div>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Graphite Intelligence</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    min-height: 100vh;
    background-color: #121212;
    font-family: 'Inter', system-ui, sans-serif;
    color: #a0a0a0;
    display: flex;
    justify-content: center;
    padding: 60px 20px;
  }

  .layout { width: 100%; max-width: 600px; }

  .topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 40px;
    padding-bottom: 20px;
    border-bottom: 1px solid #222;
  }

  .topbar-brand { font-weight: 700; color: #fff; letter-spacing: 0.1em; text-transform: uppercase; font-size: 14px; }

  .user-info { font-size: 12px; color: #555; }
  .logout-btn { color: #60a5fa; text-decoration: none; margin-left: 15px; }

  .card {
    background: #1e1e1e;
    border: 1px solid #2d2d2d;
    padding: 40px;
    border-radius: 4px;
    box-shadow: 0 30px 60px rgba(0,0,0,0.4);
  }

  .card-title {
    color: #ffffff;
    font-size: 24px;
    font-weight: 300;
    margin-bottom: 10px;
  }

  .card-subtitle {
    font-size: 13px;
    color: #555;
    margin-bottom: 30px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .btn-generate {
    background: transparent;
    border: 1px solid #444;
    color: #fff;
    padding: 12px 24px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    cursor: pointer;
    transition: all 0.3s;
  }

  .btn-generate:hover {
    background: #fff;
    color: #000;
    border-color: #fff;
  }

  .original-box {
    margin-top: 40px;
    font-size: 18px;
    color: #eee;
    line-height: 1.6;
    padding-left: 20px;
    border-left: 2px solid #60a5fa;
  }

  .result-container {
    margin-top: 40px;
    display: grid;
    grid-template-columns: 1fr;
    gap: 20px;
  }

  .tile {
    background: #161616;
    border: 1px solid #252525;
    padding: 20px;
  }

  .tile-label {
    font-size: 10px;
    font-weight: 800;
    color: #60a5fa;
    text-transform: uppercase;
    margin-bottom: 10px;
    letter-spacing: 0.1em;
  }

  .tile-content {
    font-size: 14px;
    color: #bbb;
    line-height: 1.7;
  }

  .error-box {
    margin-top: 20px;
    color: #ef4444;
    font-size: 13px;
    border: 1px solid #ef4444;
    padding: 10px;
  }
</style>
</head>
<body>
<div class="layout">
  <div class="topbar">
    <div class="topbar-brand">Graphite.AI</div>
    <div class="user-info">
      IDENT: {{ user }}
      <a href="/logout" class="logout-btn">DISCONNECT</a>
    </div>
  </div>

  <div class="card">
    <h1 class="card-title">Intelligence Feed</h1>
    <p class="card-subtitle">Mistral-Powered Logic Processing</p>

    <form method="POST">
      <button type="submit" class="btn-generate">Generate Advice</button>
    </form>

    {% if error %}<div class="error-box">{{ error }}</div>{% endif %}

    {% if original %}
      <div class="original-box">"{{ original }}"</div>

      <div class="result-container">
        {% if result %}
        <div class="tile">
          <div class="tile-label">Localization</div>
          <div class="tile-content">{{ result['translation'] }}</div>
        </div>
        <div class="tile">
          <div class="tile-label">Contextual Meaning</div>
          <div class="tile-content">{{ result['meaning'] }}</div>
        </div>
        {% endif %}
      </div>
    {% endif %}
  </div>
</div>
</body>
</html>
"""

# --- LOGIN ---

login_manager = LoginManager()  # создаем и привязываем сессию
login_manager.init_app(app)
login_manager.login_view = "login"  # не авторизовался, иди на страницу логин


@login_manager.user_loader  # получаем пользоваетелей из базы данных
def load_user(user_id):  # ищем по имени
    return User.query.get(user_id)  # если нет, ноне


@app.route('/login', methods=['GET', 'POST'])  # регистрируем маршрут страницы
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get("username", "").strip()  # обрабатываем данные
        password = request.form.get("password", "").strip()

        user = User.query.get(username)  # ищет в таблице
        if user:
            if not check_password_hash(user.password, password):
                error = "Неверный пароль"
                return render_template_string(LOGIN_HTML, error=error)  # возвращаем на страницу
        else:
            new_user = User(username=username, password=generate_password_hash(password))
            db.session.add(new_user)  # добавляет обьекты в сессию, пока не в бд
            db.session.commit()  # отправляем данные
            user = new_user

        login_entry = LoginLog(username=user.username)  # Создаёт запись в таблице logins с именем пользователя.
        db.session.add(login_entry)
        db.session.commit()

        login_user(user)
        return redirect(url_for('index'))  # перенаправление на главную страницу

    return render_template_string(LOGIN_HTML, error=error)  # Если форму не отправляли — показать пустую форму взхода


@app.route('/logout')  # выход из системы
def logout():
    logout_user()  # Flask-Login: очищает сессию текущего пользователя.
    return redirect(url_for('login'))  # редирект на страницу входа


@app.route('/', methods=['GET', 'POST'])  # тоже для главное страницы
@login_required  # только для вошедших
def index():  # обработчик главной страницы
    original, result, error = None, None, None
    if request.method == 'POST':  # обработка нажатия генерации совета
        try:  # начала блока перехвата ошибок, работай пока не сломалось и поймай ошибку
            slip = requests.get("https://api.adviceslip.com/advice", timeout=5).json()  # запрос к сайту с советами
            original = slip['slip']['advice']  # достаем текст совета

            headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}",
                       "Content-Type": "application/json"}  # паспорт запроса, отправь в формате json
            payload = {  # тело запроса
                "model": "mistral-small-latest",
                "messages": [
                    {"role": "system", "content": "Переведи и объясни смысл. Ответ строго JSON."},  # системный промпт
                    {"role": "user", "content": f"{original} " + '{"translation":"...","meaning":"..."}'}
                    # пользовательское соо,
                ],
                "response_format": {"type": "json_object"}  # возвращаем ответ
            }
            resp = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload,
                                 # отправить данные на сервер мистраль
                                 timeout=10)
            result = json.loads(
                resp.json()['choices'][0]['message']['content'])  # парсим ответ (достаем перевод и смысл)
        except Exception as e:  # ловим и сохраняем ошбку
            error = str(e)

    return render_template_string(HTML_TEMPLATE, original=original, result=result, error=error,
                                  # рендер нововой страницы
                                  user=current_user.username)  # подставляем юзера


if __name__ == '__main__':  # работа только в этом файле
    with app.app_context():  # включаем фласк для работы с базой
        db.create_all()  # создаем талицы
    app.run(debug=True, port=PORT)  # запуск сервера
