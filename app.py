
from flask import Flask, render_template, request, redirect, url_for, abort
from pathlib import Path
import sqlite3

app = Flask(__name__)

DB_PATH = Path(__file__).resolve().parent / "contatos.db"


def conectar_banco():
    conexao = sqlite3.connect(DB_PATH)
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_tabela():
    caminho_sql = Path(__file__).resolve().parent / "schema.sql"
    sql = caminho_sql.read_text(encoding="utf-8")

    conexao = conectar_banco()

    try:
        conexao.executescript(sql)
        conexao.commit()
    finally:
        conexao.close()


criar_tabela()


@app.route("/")
def inicio():
    return render_template("inicio.html")


@app.route("/sobre")
def sobre():
    return render_template("sobre.html")


@app.route("/ajuda")
def ajuda():
    return render_template("ajuda.html")


@app.route("/contato", methods=["GET", "POST"])
def contato():
    nome = ""
    email = ""
    erro = ""
    enviado = False

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip()

        if nome and email:
            conexao = conectar_banco()

            try:
                conexao.execute(
                    "INSERT INTO contatos (nome, email) VALUES (?, ?)",
                    (nome, email)
                )
                conexao.commit()
            finally:
                conexao.close()

            enviado = True
        else:
            erro = "Preencha seu nome e seu e-mail."

    conexao = conectar_banco()

    try:
        contatos = conexao.execute(
            "SELECT id, nome, email FROM contatos ORDER BY id DESC"
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
def editar_contato(id):
    conexao = conectar_banco()

    try:
        contato = conexao.execute(
            "SELECT id, nome, email FROM contatos WHERE id = ?",
            (id,)
        ).fetchone()

        if contato is None:
            abort(404)

        nome = contato["nome"]
        email = contato["email"]
        erro = ""

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            email = request.form.get("email", "").strip()

            if nome and email:
                conexao.execute(
                    "UPDATE contatos SET nome = ?, email = ? WHERE id = ?",
                    (nome, email, id)
                )
                conexao.commit()

                return redirect(url_for("contato"))
            else:
                erro = "Preencha seu nome e seu e-mail."

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
def excluir_contato(id):
    conexao = conectar_banco()

    try:
        conexao.execute(
            "DELETE FROM contatos WHERE id = ?",
            (id,)
        )
        conexao.commit()
    finally:
        conexao.close()

    return redirect(url_for("contato"))


if __name__ == "__main__":
    app.run(debug=True)
