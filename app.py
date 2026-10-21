
from flask import Flask, render_template, request, redirect, url_for, abort, session
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
from functools import wraps
import sqlite3
import os

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "FLASK_SECRET_KEY",
    "chave-temporaria-apenas-para-estudo"
)

CSRFProtect(app)

DB_PATH = Path(__file__).resolve().parent / "contatos.db"


def conectar_banco():
    conexao = sqlite3.connect(DB_PATH)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def validar_contato(nome, email):
    if not nome or not email:
        return "Preencha seu nome e seu e-mail."

    if len(nome) > 100:
        return "O nome deve ter no máximo 100 caracteres."

    if len(email) > 254:
        return "O e-mail é muito longo."

    if email.count("@") != 1:
        return "Digite um e-mail válido."

    parte_local, dominio = email.rsplit("@", 1)

    if (
        not parte_local
        or "." not in dominio
        or dominio.startswith(".")
        or dominio.endswith(".")
    ):
        return "Digite um e-mail válido."

    return ""


def criar_tabela():
    caminho_sql = Path(__file__).resolve().parent / "schema.sql"
    sql = caminho_sql.read_text(encoding="utf-8")

    conexao = conectar_banco()

    try:
        conexao.executescript(sql)

        colunas = {
            linha["name"]
            for linha in conexao.execute(
                "PRAGMA table_info(contatos)"
            ).fetchall()
        }

        if "usuario_id" not in colunas:
            conexao.execute("""
                ALTER TABLE contatos
                ADD COLUMN usuario_id INTEGER
                REFERENCES usuarios(id) DEFAULT NULL
            """)

        conexao.commit()
    finally:
        conexao.close()


criar_tabela()


def login_requerido(funcao):
    @wraps(funcao)
    def decorada(*args, **kwargs):
        if session.get("usuario_id") is None:
            return redirect(url_for("login"))

        return funcao(*args, **kwargs)

    return decorada


@app.route("/")
def inicio():
    return render_template("inicio.html")


@app.route("/sobre")
def sobre():
    return render_template("sobre.html")


@app.route("/ajuda")
def ajuda():
    return render_template("ajuda.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    nome = ""
    email = ""
    erro = ""

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        erro = validar_contato(nome, email)

        if not erro and len(senha) < 8:
            erro = "A senha deve ter pelo menos 8 caracteres."

        if not erro:
            senha_hash = generate_password_hash(senha)
            conexao = conectar_banco()

            try:
                conexao.execute(
                    """
                    INSERT INTO usuarios (nome, email, senha_hash)
                    VALUES (?, ?, ?)
                    """,
                    (nome, email, senha_hash)
                )
                conexao.commit()
            except sqlite3.IntegrityError:
                erro = "Já existe uma conta com esse e-mail."
            finally:
                conexao.close()

            if not erro:
                return redirect(url_for("login"))

    return render_template(
        "cadastro.html",
        nome=nome,
        email=email,
        erro=erro
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    email = ""
    erro = ""

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        conexao = conectar_banco()

        try:
            usuario = conexao.execute(
                """
                SELECT id, nome, email, senha_hash
                FROM usuarios
                WHERE email = ?
                """,
                (email,)
            ).fetchone()
        finally:
            conexao.close()

        if usuario and check_password_hash(
            usuario["senha_hash"], senha
        ):
            session.clear()
            session["usuario_id"] = usuario["id"]

            return redirect(url_for("painel"))

        erro = "E-mail ou senha incorretos."

    return render_template(
        "login.html",
        email=email,
        erro=erro
    )


@app.route("/painel")
@login_requerido
def painel():
    usuario_id = session["usuario_id"]
    conexao = conectar_banco()

    try:
        usuario = conexao.execute(
            """
            SELECT id, nome, email
            FROM usuarios
            WHERE id = ?
            """,
            (usuario_id,)
        ).fetchone()
    finally:
        conexao.close()

    if usuario is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template("painel.html", usuario=usuario)


@app.route("/sair", methods=["POST"])
def sair():
    session.clear()
    return redirect(url_for("inicio"))


@app.route("/contato", methods=["GET", "POST"])
@login_requerido
def contato():
    usuario_id = session["usuario_id"]
    nome = ""
    email = ""
    erro = ""
    enviado = False

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip()

        erro = validar_contato(nome, email)

        if not erro:
            conexao = conectar_banco()

            try:
                conexao.execute(
                    """
                    INSERT INTO contatos (nome, email, usuario_id)
                    VALUES (?, ?, ?)
                    """,
                    (nome, email, usuario_id)
                )
                conexao.commit()
                enviado = True
            finally:
                conexao.close()

    conexao = conectar_banco()

    try:
        contatos = conexao.execute(
            """
            SELECT id, nome, email
            FROM contatos
            WHERE usuario_id = ?
            ORDER BY id DESC
            """,
            (usuario_id,)
        ).fetchall()
    finally:
        conexao.close()

    return render_template(
        "contato.html",
        nome=nome,
        email=email,
        erro=erro,
        enviado=enviado,
        contatos=contatos
    )


@app.route("/contato/<int:id>/editar", methods=["GET", "POST"])
@login_requerido
def editar_contato(id):
    usuario_id = session["usuario_id"]
    conexao = conectar_banco()

    try:
        contato_db = conexao.execute(
            """
            SELECT id, nome, email
            FROM contatos
            WHERE id = ? AND usuario_id = ?
            """,
            (id, usuario_id)
        ).fetchone()

        if contato_db is None:
            abort(404)

        nome = contato_db["nome"]
        email = contato_db["email"]
        erro = ""

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            email = request.form.get("email", "").strip()

            erro = validar_contato(nome, email)

            if not erro:
                conexao.execute(
                    """
                    UPDATE contatos
                    SET nome = ?, email = ?
                    WHERE id = ? AND usuario_id = ?
                    """,
                    (nome, email, id, usuario_id)
                )
                conexao.commit()

                return redirect(url_for("contato"))

        return render_template(
            "editar_contato.html",
            contato_id=id,
            nome=nome,
            email=email,
            erro=erro
        )
    finally:
        conexao.close()


@app.route("/contato/<int:id>/excluir", methods=["POST"])
@login_requerido
def excluir_contato(id):
    usuario_id = session["usuario_id"]
    conexao = conectar_banco()

    try:
        conexao.execute(
            """
            DELETE FROM contatos
            WHERE id = ? AND usuario_id = ?
            """,
            (id, usuario_id)
        )
        conexao.commit()
    finally:
        conexao.close()

    return redirect(url_for("contato"))


if __name__ == "__main__":
    app.run(debug=True)
