#sistema_reabilitação.py
"""
Sistema de Atendimento em rede local — Centro de Reabilitação de Açailândia
Versão com Visual Aprimorado 
"""

import argparse
import ctypes
import html
import getpass
import hmac
import http.server
import ipaddress
from http.cookies import CookieError, SimpleCookie
import json
import os
import queue
import secrets
import socket
import ssl
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import hashlib
from datetime import datetime
import threading
import time
import unicodedata
import urllib.error
from urllib.parse import parse_qs, urlsplit
import urllib.request

# ==================== CORES E ESTILOS ====================
COR_PRIMARIA = "#2c5f97"
COR_SECUNDARIA = "#4a90d9"
COR_SUCESSO = "#27ae60"
COR_AVISO = "#f39c12"
COR_ERRO = "#e74c3c"
COR_FUNDO = "#f0f4f8"
COR_CARTA = "#ffffff"
COR_TEXTO = "#2c3e50"
COR_TEXTO_CLARO = "#7f8c8d"
COR_BRASIL_VERDE = "#159447"
COR_BRASIL_VERDE_ESCURO = "#075b3b"
COR_BRASIL_AMARELO = "#ffcb2f"
COR_BRASIL_AZUL = "#1766a8"
COR_FUNDO_PAINEL = "#f1f7f2"

CORES_FUNDO_ESCURO = {
    "#ffffff": "#232b34",
    "white": "#232b34",
    COR_FUNDO: "#1c232b",
    COR_FUNDO_PAINEL: "#151b21",
    COR_PRIMARIA: "#244c73",
    COR_SECUNDARIA: "#326897",
    COR_SUCESSO: "#218653",
    COR_AVISO: "#9d6610",
    COR_ERRO: "#a93832",
    COR_BRASIL_VERDE: "#126d3e",
    COR_BRASIL_VERDE_ESCURO: "#123c2d",
    COR_BRASIL_AMARELO: "#8d701c",
    COR_BRASIL_AZUL: "#205987",
    "#fff0ef": "#472b2a",
    "#ffe3e0": "#5a3431",
    "#e9f6ee": "#24392c",
    "#fff4df": "#403820",
    "#d8e6db": "#344139",
    "#dceeff": "#145b90",
}
CORES_TEXTO_ESCURO = {
    "white": "#f1f4f6",
    "black": "#e6edf2",
    "#000000": "#e6edf2",
    COR_TEXTO: "#e2e8ee",
    COR_TEXTO_CLARO: "#aab5bf",
    COR_PRIMARIA: "#80b9ea",
    COR_BRASIL_VERDE: "#66d792",
    COR_BRASIL_VERDE_ESCURO: "#74d19d",
    COR_BRASIL_AMARELO: "#f1c95d",
    COR_BRASIL_AZUL: "#82c1f3",
    COR_ERRO: "#ff8276",
    "#a33b36": "#f08b82",
    "#8f302b": "#f2a19a",
    "#24734d": "#71d49c",
    "#9a6500": "#f2c56f",
    "#f0b91e": "#26303a",
}

FONTE_TITULO = ("Segoe UI", 18, "bold")
FONTE_SUBTITULO = ("Segoe UI", 12, "bold")
FONTE_NORMAL = ("Segoe UI", 10)
FONTE_PEQUENA = ("Segoe UI", 9)
# ==========================================================

ARQUIVO_BD_LOCAL = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "servidor_local.db"
)
PORTA_SERVIDOR = 8765
URL_TESTE_INTERNET = "http://www.msftconnecttest.com/connecttest.txt"
ITERACOES_HASH_SENHA = 600_000
TIPOS_ATENDIMENTO = (
    "Psicologo",
    "Terapia Ocupacional",
    "Psiquiatra",
    "Fonoaudiologia",
    "Fisioterapia",
)
OPERACOES_RECEPCAO = frozenset(
    {
        "verificar_conexao",
        "obter_funcao",
        "atualizar_acesso",
        "listar_pacientes",
        "listar_pacientes_para_exclusao",
        "listar_historico",
        "cadastrar_paciente",
        "encerrar_sessao",
    }
)
ROTAS_WEB_RECEPCAO = frozenset({"/web/cadastrar", "/web/sair"})


def funcao_somente_cadastro(funcao, usuario=""):
    nomes_recepcao = {"recepcao", "recepcionista"}
    valores = (funcao, usuario)
    for valor in valores:
        valor_normalizado = "".join(
            caractere
            for caractere in unicodedata.normalize("NFKD", valor or "").casefold()
            if not unicodedata.combining(caractere)
        )
        if valor_normalizado.strip() in nomes_recepcao:
            return True
    return False


def operacao_permitida(funcao, operacao, usuario=""):
    return (
        not funcao_somente_cadastro(funcao, usuario)
        or operacao in OPERACOES_RECEPCAO
    )


def dispositivo_conectado_a_rede():
    if os.name == "nt":
        try:
            flags = ctypes.c_ulong()
            conectado = ctypes.windll.wininet.InternetGetConnectedState(
                ctypes.byref(flags), 0
            )
        except (AttributeError, OSError):
            pass
        else:
            return bool(conectado or flags.value & 0x03)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as conexao:
            conexao.connect(("192.0.2.1", 80))
            endereco_local = conexao.getsockname()[0]
        conectado_a_rede = (
            endereco_local != "0.0.0.0" and not endereco_local.startswith("127.")
        )
    except OSError:
        conectado_a_rede = False

    if not conectado_a_rede and os.name != "nt":
        try:
            enderecos = socket.getaddrinfo(socket.gethostname(), None)
        except OSError:
            enderecos = ()
        for informacao in enderecos:
            endereco_texto = informacao[4][0]
            if not isinstance(endereco_texto, str):
                continue
            try:
                endereco = ipaddress.ip_address(
                    endereco_texto.split("%", 1)[0]
                )
            except ValueError:
                continue
            if not endereco.is_loopback and not endereco.is_unspecified:
                conectado_a_rede = True
                break
    return conectado_a_rede


def verificar_conectividade_dispositivo():
    conectado_a_rede = dispositivo_conectado_a_rede()
    if not conectado_a_rede:
        return False, False

    try:
        with urllib.request.urlopen(URL_TESTE_INTERNET, timeout=2) as resposta:
            tem_internet = (
                resposta.status == 200
                and resposta.read(64).strip() == b"Microsoft Connect Test"
            )
    except (urllib.error.URLError, TimeoutError, OSError):
        tem_internet = False
    return True, tem_internet


SCRIPT_MASCARA_FORMULARIO = r"""(function () {
  const campoUsuario = document.getElementById("usuario");
  const campoSenha = document.getElementById("senha");
  if (campoUsuario && campoSenha) {
    campoUsuario.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" || event.isComposing || !campoUsuario.checkValidity()) {
        return;
      }
      event.preventDefault();
      campoSenha.focus();
    });
  }

  const campoNome = document.getElementById("nome");
  if (campoNome) {
    campoNome.addEventListener("input", function () {
      campoNome.value = campoNome.value
        .replace(/[^\p{L} ]/gu, "")
        .toUpperCase();
    });
  }

  const campoAcompanhante = document.getElementById("acompanhante");
  const semAcompanhante = document.getElementById("sem_acompanhante");
  if (campoAcompanhante && semAcompanhante) {
    const atualizarCampoAcompanhante = function () {
      campoAcompanhante.disabled = semAcompanhante.checked;
      if (semAcompanhante.checked) campoAcompanhante.value = "";
    };
    semAcompanhante.addEventListener("change", atualizarCampoAcompanhante);
    atualizarCampoAcompanhante();
  }
  if (campoAcompanhante) {
    campoAcompanhante.addEventListener("input", function () {
      campoAcompanhante.value = campoAcompanhante.value
        .replace(/[^\p{L} ]/gu, "")
        .toUpperCase();
    });
  }

  const campo = document.getElementById("cpf");
  if (campo) {
    campo.addEventListener("input", function () {
      const texto = campo.value;
      const digitosAntes = texto.slice(0, campo.selectionStart).replace(/\D/g, "").length;
      const digitos = texto.replace(/\D/g, "").slice(0, 11);
      let formatado;
      if (digitos.length <= 3) {
        formatado = digitos.length === 3 ? digitos + "." : digitos;
      } else if (digitos.length <= 6) {
        formatado = digitos.slice(0, 3) + "." + digitos.slice(3);
        if (digitos.length === 6) formatado += ".";
      } else if (digitos.length <= 9) {
        formatado = digitos.slice(0, 3) + "." + digitos.slice(3, 6) + "." + digitos.slice(6);
        if (digitos.length === 9) formatado += "-";
      } else {
        formatado = digitos.slice(0, 3) + "." + digitos.slice(3, 6) + "." +
          digitos.slice(6, 9) + "-" + digitos.slice(9);
      }

      campo.value = formatado;
      let posicao = 0;
      let encontrados = 0;
      while (posicao < formatado.length && encontrados < digitosAntes) {
        if (/[0-9]/.test(formatado[posicao])) encontrados++;
        posicao++;
      }
      if ([3, 6, 9].includes(digitosAntes) && /[.-]/.test(formatado[posicao] || "")) {
        posicao++;
      }
      campo.setSelectionRange(posicao, posicao);
    });
  }

  const campoData = document.getElementById("data_nascimento");
  if (campoData) {
    function formatarData(digitos) {
      digitos = digitos.slice(0, 8);
      if (digitos.length <= 2) {
        return digitos.length === 2 ? digitos + "/" : digitos;
      }
      if (digitos.length <= 4) {
        const parcial = digitos.slice(0, 2) + "/" + digitos.slice(2);
        return digitos.length === 4 ? parcial + "/" : parcial;
      }
      return digitos.slice(0, 2) + "/" + digitos.slice(2, 4) + "/" + digitos.slice(4);
    }

    function posicionTrasDigitos(texto, cantidad) {
      let posicion = 0;
      let encontrados = 0;
      while (posicion < texto.length && encontrados < cantidad) {
        if (/[0-9]/.test(texto[posicion])) encontrados++;
        posicion++;
      }
      if ([2, 4].includes(cantidad) && texto[posicion] === "/") posicion++;
      return posicion;
    }

    campoData.addEventListener("keydown", function (event) {
      const cursor = campoData.selectionStart;
      if (
        event.key !== "Backspace" ||
        cursor !== campoData.selectionEnd ||
        campoData.value[cursor - 1] !== "/"
      ) {
        return;
      }
      event.preventDefault();
      const digitosAntes = campoData.value.slice(0, cursor).replace(/\D/g, "").length;
      const digitos = campoData.value.replace(/\D/g, "");
      const atualizados = digitos.slice(0, digitosAntes - 1) + digitos.slice(digitosAntes);
      campoData.value = formatarData(atualizados);
      const posicao = posicionTrasDigitos(campoData.value, digitosAntes - 1);
      campoData.setSelectionRange(posicao, posicao);
    });

    campoData.addEventListener("input", function () {
      const texto = campoData.value;
      const digitosAntes = texto.slice(0, campoData.selectionStart).replace(/\D/g, "").length;
      const digitos = texto.replace(/\D/g, "").slice(0, 8);
      const formatado = formatarData(digitos);
      campoData.value = formatado;
      const posicao = posicionTrasDigitos(formatado, digitosAntes);
      campoData.setSelectionRange(posicao, posicao);
    });
  }

  document.querySelectorAll("form[data-confirm]").forEach(function (formulario) {
    formulario.addEventListener("submit", function (event) {
      if (!window.confirm(formulario.dataset.confirm)) event.preventDefault();
    });
  });
})();"""


def validar_documentos(rg):
    if rg is not None and (
        not isinstance(rg, str)
        or len(rg) > 11
        or any(char < "0" or char > "9" for char in rg)
    ):
        raise ValueError("RG deve conter somente números, com até 11 dígitos.")


def validar_tipo_atendimento(tipo):
    if not isinstance(tipo, str) or tipo.strip() not in TIPOS_ATENDIMENTO:
        raise ValueError("Selecione um tipo de atendimento válido.")
    return tipo.strip()


def validar_data_nascimento(data):
    if (
        not isinstance(data, str)
        or len(data) != 10
        or data[2] != "/"
        or data[5] != "/"
        or any(
            not ("0" <= data[indice] <= "9")
            for indice in (0, 1, 3, 4, 6, 7, 8, 9)
        )
    ):
        raise ValueError("Informe a data no formato DD/MM/AAAA.")
    try:
        datetime.strptime(data, "%d/%m/%Y")
    except ValueError as erro:
        raise ValueError("Informe uma data de nascimento válida.") from erro
    return data


def formatar_data_nascimento(texto):
    digitos = "".join(char for char in texto if "0" <= char <= "9")[:8]
    if len(digitos) <= 2:
        return digitos + "/" if len(digitos) == 2 else digitos
    if len(digitos) <= 4:
        parcial = f"{digitos[:2]}/{digitos[2:]}"
        return parcial + "/" if len(digitos) == 4 else parcial
    return f"{digitos[:2]}/{digitos[2:4]}/{digitos[4:]}"


def formatar_cpf(cpf):
    digitos = "".join(char for char in cpf if "0" <= char <= "9")[:11]
    if len(digitos) <= 3:
        return digitos + "." if len(digitos) == 3 else digitos
    if len(digitos) <= 6:
        resultado = f"{digitos[:3]}.{digitos[3:]}"
        return resultado + "." if len(digitos) == 6 else resultado
    if len(digitos) <= 9:
        resultado = f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:]}"
        return resultado + "-" if len(digitos) == 9 else resultado
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def normalizar_cpf(cpf):
    if cpf is None or cpf == "":
        return None
    if not isinstance(cpf, str):
        raise ValueError("CPF deve conter exatamente 11 dígitos.")
    digitos = "".join(char for char in cpf if "0" <= char <= "9")
    if len(digitos) != 11 or cpf not in (digitos, formatar_cpf(digitos)):
        raise ValueError("CPF deve conter exatamente 11 dígitos.")
    return digitos


def validar_cartao_sus(cartao_sus):
    if not isinstance(cartao_sus, str):
        raise ValueError("Cartão SUS deve conter de 7 a 15 algarismos.")
    cartao_sus = cartao_sus.strip()
    if (
        not 7 <= len(cartao_sus) <= 15
        or not all("0" <= char <= "9" for char in cartao_sus)
    ):
        raise ValueError("Cartão SUS deve conter de 7 a 15 algarismos.")
    return cartao_sus


def validar_nome(nome):
    if not isinstance(nome, str):
        raise ValueError("Nome completo deve conter somente letras.")
    nome = nome.strip()
    if not nome or not all(char == " " or char.isalpha() for char in nome):
        raise ValueError("Nome completo deve conter somente letras.")
    return nome.upper()


def exibir_cpf(cpf):
    if not cpf:
        return "-"
    try:
        return formatar_cpf(normalizar_cpf(cpf))
    except ValueError:
        return cpf


def aplicar_mascara_cpf_entrada(event):
    campo = event.widget
    texto = campo.get()
    digitos_antes = sum("0" <= char <= "9" for char in texto[:campo.index(tk.INSERT)])
    formatado = formatar_cpf(texto)
    if texto == formatado:
        return
    campo.delete(0, tk.END)
    campo.insert(0, formatado)
    posicao = 0
    encontrados = 0
    while posicao < len(formatado) and encontrados < digitos_antes:
        if "0" <= formatado[posicao] <= "9":
            encontrados += 1
        posicao += 1
    if digitos_antes in (3, 6, 9) and formatado[posicao:posicao + 1] in (".", "-"):
        posicao += 1
    campo.icursor(posicao)


def aplicar_nome_maiusculo_entrada(event):
    campo = event.widget
    texto = campo.get()
    formatado = texto.upper()
    if texto == formatado:
        return
    posicao = campo.index(tk.INSERT)
    campo.delete(0, tk.END)
    campo.insert(0, formatado)
    campo.icursor(min(posicao, len(formatado)))


def aplicar_mascara_data_entrada(event):
    campo = event.widget
    texto = campo.get()
    cursor = campo.index(tk.INSERT)
    digitos_antes = sum("0" <= char <= "9" for char in texto[:cursor])
    digitos = "".join(char for char in texto if "0" <= char <= "9")[:8]
    formatado = formatar_data_nascimento(digitos)
    if texto != formatado:
        campo.delete(0, tk.END)
        campo.insert(0, formatado)

    posicao = 0
    encontrados = 0
    while posicao < len(formatado) and encontrados < digitos_antes:
        if "0" <= formatado[posicao] <= "9":
            encontrados += 1
        posicao += 1
    if digitos_antes in (2, 4) and formatado[posicao:posicao + 1] == "/":
        posicao += 1
    campo.icursor(posicao)


def apagar_barra_data_entrada(event):
    campo = event.widget
    texto = campo.get()
    cursor = campo.index(tk.INSERT)
    if campo.selection_present() or cursor == 0 or texto[cursor - 1] != "/":
        return

    digitos = "".join(char for char in texto if "0" <= char <= "9")
    digitos_antes = sum("0" <= char <= "9" for char in texto[:cursor])
    if digitos_antes == 0:
        return
    digitos = digitos[:digitos_antes - 1] + digitos[digitos_antes:]
    formatado = formatar_data_nascimento(digitos)
    campo.delete(0, tk.END)
    campo.insert(0, formatado)

    posicao = 0
    encontrados = 0
    while posicao < len(formatado) and encontrados < digitos_antes - 1:
        if "0" <= formatado[posicao] <= "9":
            encontrados += 1
        posicao += 1
    campo.icursor(posicao)
    return "break"


def criar_hash_senha(senha):
    sal = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac(
        "sha256", senha.encode("utf-8"), sal, ITERACOES_HASH_SENHA
    )
    return f"pbkdf2_sha256${ITERACOES_HASH_SENHA}${sal.hex()}${derivada.hex()}"


def validar_hash_senha(senha, hash_armazenado):
    if not hash_armazenado.startswith("pbkdf2_sha256$"):
        hash_legado = hashlib.sha256(senha.encode("utf-8")).hexdigest()
        return hmac.compare_digest(hash_legado, hash_armazenado), True
    try:
        _, iteracoes, sal_hex, derivada_hex = hash_armazenado.split("$")
        derivada = hashlib.pbkdf2_hmac(
            "sha256",
            senha.encode("utf-8"),
            bytes.fromhex(sal_hex),
            int(iteracoes),
        )
    except (ValueError, TypeError):
        return False, False
    return hmac.compare_digest(derivada.hex(), derivada_hex), False


# ------------------- BANCO DE DADOS LOCAL -------------------
class BancoLocal:
    def __init__(self):
        self.conn = sqlite3.connect(ARQUIVO_BD_LOCAL, check_same_thread=False)
        self.lock = threading.RLock()
        self.criar_tabelas()

    def criar_tabelas(self):
        c = self.conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                nome_completo TEXT NOT NULL,
                funcao TEXT NOT NULL,
                ultimo_acesso TEXT,
                ativo INTEGER NOT NULL DEFAULT 1
            )
        ''')

        c.execute("PRAGMA table_info(usuarios)")
        colunas_usuarios = {coluna[1] for coluna in c.fetchall()}
        if "ativo" not in colunas_usuarios:
            c.execute(
                "ALTER TABLE usuarios ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1"
            )

        c.execute('''
            CREATE TABLE IF NOT EXISTS historico_alteracoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                acao TEXT NOT NULL,
                data_hora TEXT NOT NULL,
                detalhes TEXT
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS pacientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rg_cnh TEXT,
                rg TEXT,
                cnh TEXT,
                cpf TEXT UNIQUE,
                cartao_sus TEXT NOT NULL,
                nome TEXT NOT NULL,
                data_nascimento TEXT NOT NULL,
                sexo TEXT NOT NULL,
                acompanhante TEXT,
                comprovante_residencia TEXT,
                endereco TEXT,
                data_cadastro TEXT NOT NULL,
                usuario_cadastro TEXT NOT NULL
            )
        ''')

        c.execute("PRAGMA table_info(pacientes)")
        colunas_pacientes = {coluna[1] for coluna in c.fetchall()}
        if "endereco" not in colunas_pacientes:
            c.execute("ALTER TABLE pacientes ADD COLUMN endereco TEXT")

        c.execute("PRAGMA table_info(pacientes)")
        colunas_pacientes = {coluna[1] for coluna in c.fetchall()}
        for coluna in ("rg", "cnh"):
            if coluna not in colunas_pacientes:
                c.execute(f"ALTER TABLE pacientes ADD COLUMN {coluna} TEXT")

        c.execute('''
            CREATE TABLE IF NOT EXISTS atendimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL,
                tipo_atendimento TEXT NOT NULL,
                data_atendimento TEXT NOT NULL,
                usuario_registro TEXT NOT NULL,
                status_envio TEXT DEFAULT 'PENDENTE',
                data_envio TEXT,
                FOREIGN KEY(paciente_id) REFERENCES pacientes(id)
            )
        ''')

        c.execute("SELECT id FROM usuarios WHERE usuario = '1'")
        usuario_padrao = c.fetchone()
        c.execute("SELECT id FROM usuarios WHERE usuario = 'admin'")
        usuario_admin = c.fetchone()
        if not usuario_padrao and usuario_admin:
            c.execute(
                "UPDATE usuarios SET usuario = ?, senha = ? WHERE id = ?",
                ("1", criar_hash_senha("1"), usuario_admin[0]),
            )
        elif not usuario_padrao:
            c.execute("SELECT COUNT(*) FROM usuarios")
            if c.fetchone()[0] == 0:
                senha_padrao = criar_hash_senha("1")
                c.execute('''
                    INSERT INTO usuarios (usuario, senha, nome_completo, funcao, ultimo_acesso)
                    VALUES (?, ?, ?, ?, ?)
                ''', ("1", senha_padrao, "Administrador", "Gestor", datetime.now().isoformat()))

        self.conn.commit()

    def executar(self, sql, params=()):
        with self.lock:
            c = self.conn.cursor()
            c.execute(sql, params)
            self.conn.commit()
            return c.lastrowid

    def consultar(self, sql, params=()):
        with self.lock:
            c = self.conn.cursor()
            c.execute(sql, params)
            return c.fetchall()

    def autenticar(self, usuario, senha):
        resultado = self.consultar(
            "SELECT id, senha, ativo FROM usuarios WHERE usuario = ?",
            (usuario,),
        )
        if not resultado:
            return False
        usuario_id, hash_armazenado, ativo = resultado[0]
        if not ativo:
            return False
        valida, legado = validar_hash_senha(senha, hash_armazenado)
        if valida and legado:
            self.executar(
                "UPDATE usuarios SET senha = ? WHERE id = ?",
                (criar_hash_senha(senha), usuario_id),
            )
        return valida

    def usuario_ativo(self, usuario):
        resultado = self.consultar(
            "SELECT ativo FROM usuarios WHERE usuario = ?",
            (usuario,),
        )
        return bool(resultado and resultado[0][0])

    def obter_funcao(self, usuario):
        resultado = self.consultar(
            "SELECT funcao FROM usuarios WHERE usuario = ?",
            (usuario,),
        )
        if not resultado:
            raise ValueError(f"O usuário {usuario} não foi encontrado.")
        return resultado[0][0]

    def alterar_status_usuario(self, usuario, ativo):
        if not isinstance(usuario, str) or not usuario.strip():
            raise ValueError("Informe um nome de usuário válido.")
        with self.lock, self.conn:
            c = self.conn.cursor()
            resultado = c.execute(
                "SELECT ativo FROM usuarios WHERE usuario = ?",
                (usuario,),
            ).fetchone()
            if not resultado:
                raise ValueError(f"O usuário {usuario} não foi encontrado.")
            if bool(resultado[0]) == ativo:
                estado = "ativo" if ativo else "desativado"
                raise ValueError(f"O usuário {usuario} já está {estado}.")
            if not ativo:
                quantidade_ativos = c.execute(
                    "SELECT COUNT(*) FROM usuarios WHERE ativo = 1"
                ).fetchone()[0]
                if quantidade_ativos <= 1:
                    raise ValueError(
                        "Não é possível desativar a única conta ativa."
                    )
            c.execute(
                "UPDATE usuarios SET ativo = ? WHERE usuario = ?",
                (int(ativo), usuario),
            )

    def atualizar_acesso(self, usuario):
        self.executar(
            "UPDATE usuarios SET ultimo_acesso = ? WHERE usuario = ?",
            (datetime.now().isoformat(), usuario),
        )

    def registrar_acao(self, usuario, acao, detalhes=""):
        self.executar(
            """INSERT INTO historico_alteracoes (usuario, acao, data_hora, detalhes)
               VALUES (?, ?, ?, ?)""",
            (usuario, acao, datetime.now().isoformat(), detalhes),
        )

    def listar_pacientes_atendimento(self):
        return self.consultar("SELECT id, nome, cartao_sus FROM pacientes ORDER BY nome")

    def registrar_atendimento(self, paciente_id, tipo, usuario):
        tipo = validar_tipo_atendimento(tipo)
        self.executar(
            """INSERT INTO atendimentos
               (paciente_id, tipo_atendimento, data_atendimento, usuario_registro)
               VALUES (?, ?, ?, ?)""",
            (paciente_id, tipo, datetime.now().isoformat(), usuario),
        )

    def listar_pacientes(self):
        return self.consultar(
            """SELECT nome, cpf, cartao_sus, data_cadastro
               FROM pacientes ORDER BY nome"""
        )

    def listar_pacientes_para_exclusao(self):
        return self.consultar(
            """SELECT id, nome, cpf, cartao_sus, data_cadastro
               FROM pacientes ORDER BY nome"""
        )

    def excluir_pacientes(self, paciente_ids, usuario):
        if not isinstance(paciente_ids, (list, tuple)) or not paciente_ids:
            raise ValueError("Selecione ao menos um paciente para excluir.")
        if any(
            type(paciente_id) is not int
            or not 1 <= paciente_id <= 9223372036854775807
            for paciente_id in paciente_ids
        ):
            raise ValueError("A seleção de pacientes é inválida.")
        paciente_ids = list(dict.fromkeys(paciente_ids))
        lotes = [
            paciente_ids[inicio:inicio + 500]
            for inicio in range(0, len(paciente_ids), 500)
        ]

        with self.lock, self.conn:
            c = self.conn.cursor()
            encontrados = []
            for lote in lotes:
                placeholders = ",".join("?" for _ in lote)
                encontrados.extend(
                    c.execute(
                        f"SELECT id FROM pacientes WHERE id IN ({placeholders})",
                        lote,
                    ).fetchall()
                )
            if len(encontrados) != len(paciente_ids):
                raise ValueError("Um ou mais pacientes selecionados não foram encontrados.")
            quantidade = 0
            for lote in lotes:
                placeholders = ",".join("?" for _ in lote)
                c.execute(
                    f"DELETE FROM atendimentos WHERE paciente_id IN ({placeholders})",
                    lote,
                )
                c.execute(
                    f"DELETE FROM pacientes WHERE id IN ({placeholders})",
                    lote,
                )
                quantidade += c.rowcount
            c.execute(
                """INSERT INTO historico_alteracoes
                   (usuario, acao, data_hora, detalhes)
                   VALUES (?, ?, ?, ?)""",
                (
                    usuario,
                    "EXCLUSAO",
                    datetime.now().isoformat(),
                    f"{quantidade} paciente(s) selecionado(s) e atendimentos vinculados.",
                ),
            )
            return quantidade

    def excluir_todos_pacientes(self, usuario):
        with self.lock, self.conn:
            c = self.conn.cursor()
            quantidade = c.execute("SELECT COUNT(*) FROM pacientes").fetchone()[0]
            c.execute("DELETE FROM atendimentos")
            c.execute("DELETE FROM pacientes")
            c.execute(
                """INSERT INTO historico_alteracoes
                   (usuario, acao, data_hora, detalhes)
                   VALUES (?, ?, ?, ?)""",
                (
                    usuario,
                    "EXCLUSAO",
                    datetime.now().isoformat(),
                    f"{quantidade} paciente(s) e atendimentos vinculados excluídos.",
                ),
            )
            return quantidade

    def excluir_todos_atendimentos(self, usuario):
        with self.lock, self.conn:
            c = self.conn.cursor()
            quantidade = c.execute("SELECT COUNT(*) FROM atendimentos").fetchone()[0]
            c.execute("DELETE FROM atendimentos")
            c.execute(
                """INSERT INTO historico_alteracoes
                   (usuario, acao, data_hora, detalhes)
                   VALUES (?, ?, ?, ?)""",
                (
                    usuario,
                    "EXCLUSAO",
                    datetime.now().isoformat(),
                    f"{quantidade} atendimento(s) excluído(s); pacientes preservados.",
                ),
            )
            return quantidade

    def listar_historico(self):
        return self.consultar(
            """SELECT usuario, acao, data_hora, detalhes
               FROM historico_alteracoes
               WHERE acao != 'ATENDIMENTO'
               ORDER BY id DESC LIMIT 100"""
        )

    def limpar_historico(self):
        with self.lock:
            c = self.conn.cursor()
            quantidade = c.execute("SELECT COUNT(*) FROM historico_alteracoes").fetchone()[0]
            c.execute("DELETE FROM historico_alteracoes")
            self.conn.commit()
            return quantidade

    def cadastrar_paciente(self, dados, usuario, tipo_atendimento=None):
        if len(dados) not in (8, 9):
            raise ValueError("Dados do paciente inválidos.")
        dados = list(dados)
        if len(dados) == 9:
            dados = dados[:8]
        validar_documentos(dados[0])
        dados[2] = normalizar_cpf(dados[2])
        dados[3] = validar_cartao_sus(dados[3])
        dados[4] = validar_nome(dados[4])
        if dados[7]:
            dados[7] = validar_nome(dados[7])
        dados[5] = validar_data_nascimento(dados[5])
        if tipo_atendimento is not None:
            tipo_atendimento = validar_tipo_atendimento(tipo_atendimento)

        with self.lock, self.conn:
            c = self.conn.cursor()
            if dados[2] and c.execute(
                """SELECT 1 FROM pacientes
                   WHERE REPLACE(REPLACE(cpf, '.', ''), '-', '') = ? LIMIT 1""",
                (dados[2],),
            ).fetchone():
                raise ValueError("Este CPF já está cadastrado.")
            c.execute(
                """INSERT INTO pacientes
                   (rg, cnh, cpf, cartao_sus, nome, data_nascimento, sexo,
                    acompanhante, endereco, data_cadastro, usuario_cadastro)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*dados, None, datetime.now().isoformat(), usuario),
            )
            paciente_id = c.lastrowid
            if tipo_atendimento is not None:
                c.execute(
                    """INSERT INTO atendimentos
                       (paciente_id, tipo_atendimento, data_atendimento, usuario_registro)
                       VALUES (?, ?, ?, ?)""",
                    (paciente_id, tipo_atendimento, datetime.now().isoformat(), usuario),
                )
            return paciente_id

    def verificar_conexao(self):
        return True

    def senha_admin_padrao_em_uso(self):
        resultado = self.consultar(
            "SELECT senha FROM usuarios WHERE usuario = '1'"
        )
        return bool(
            resultado
            and validar_hash_senha("1", resultado[0][0])[0]
        )

    def alterar_senha_admin(self, nova_senha):
        senha_hash = criar_hash_senha(nova_senha)
        self.executar(
            "UPDATE usuarios SET senha = ? WHERE usuario = '1'",
            (senha_hash,),
        )

    def criar_usuario(self, usuario, senha, nome_completo, funcao):
        self.executar(
            """INSERT INTO usuarios
               (usuario, senha, nome_completo, funcao, ultimo_acesso)
               VALUES (?, ?, ?, ?, ?)""",
            (
                usuario,
                criar_hash_senha(senha),
                nome_completo,
                funcao,
                datetime.now().isoformat(),
            ),
        )


class BancoCentral:
    def __init__(self, url, token, certificado_ca=None):
        self.url = url.rstrip("/")
        self.token = token
        self.sessao = None
        endereco = urlsplit(self.url)
        self.contexto_ssl = None
        if endereco.scheme == "https":
            if not certificado_ca:
                raise ValueError("Informe o certificado confiável do servidor HTTPS.")
            self.contexto_ssl = ssl.create_default_context(cafile=certificado_ca)
        elif not (
            endereco.scheme == "http"
            and endereco.hostname in ("localhost", "127.0.0.1")
            and endereco.port == PORTA_SERVIDOR
        ):
            raise ValueError(
                "Conexões HTTP só são permitidas no servidor local deste computador."
            )

    def _solicitar(self, operacao, **dados):
        payload = json.dumps({"operacao": operacao, **dados}).encode("utf-8")
        cabecalhos = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        if self.sessao:
            cabecalhos["X-Session-Token"] = self.sessao
        requisicao = urllib.request.Request(
            f"{self.url}/api",
            data=payload,
            headers=cabecalhos,
            method="POST",
        )
        try:
            if self.contexto_ssl is None:
                resposta_aberta = urllib.request.urlopen(requisicao, timeout=10)
            else:
                resposta_aberta = urllib.request.urlopen(
                    requisicao, context=self.contexto_ssl, timeout=10
                )
            with resposta_aberta as resposta:
                resultado = json.loads(resposta.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ssl.SSLError) as erro:
            raise ConnectionError(
                f"Não foi possível acessar o servidor central ({self.url}): {erro}"
            ) from erro
        if not resultado.get("ok"):
            raise RuntimeError(resultado.get("erro", "Erro retornado pelo servidor."))
        if operacao == "autenticar":
            self.sessao = resultado.get("sessao")
        return resultado.get("dados")

    def autenticar(self, usuario, senha):
        return self._solicitar("autenticar", usuario=usuario, senha=senha)

    def obter_funcao(self):
        return self._solicitar("obter_funcao")

    def atualizar_acesso(self, usuario):
        self._solicitar("atualizar_acesso", usuario=usuario)

    def registrar_acao(self, usuario, acao, detalhes=""):
        self._solicitar(
            "registrar_acao", usuario=usuario, acao=acao, detalhes=detalhes
        )

    def listar_pacientes_atendimento(self):
        return self._solicitar("listar_pacientes_atendimento")

    def registrar_atendimento(self, paciente_id, tipo, usuario):
        self._solicitar(
            "registrar_atendimento",
            paciente_id=paciente_id,
            tipo=tipo,
            usuario=usuario,
        )

    def listar_pacientes(self):
        return self._solicitar("listar_pacientes")

    def listar_pacientes_para_exclusao(self):
        return self._solicitar("listar_pacientes_para_exclusao")

    def excluir_pacientes(self, paciente_ids):
        return self._solicitar("excluir_pacientes", paciente_ids=paciente_ids)

    def excluir_todos_pacientes(self):
        return self._solicitar("excluir_todos_pacientes")

    def excluir_todos_atendimentos(self):
        return self._solicitar("excluir_todos_atendimentos")

    def listar_historico(self):
        return self._solicitar("listar_historico")

    def limpar_historico(self):
        return self._solicitar("limpar_historico")

    def cadastrar_paciente(self, dados, usuario, tipo_atendimento=None):
        return self._solicitar(
            "cadastrar_paciente",
            dados=dados,
            usuario=usuario,
            tipo_atendimento=tipo_atendimento,
        )

    def encerrar_sessao(self):
        try:
            if self.sessao:
                self._solicitar("encerrar_sessao")
        finally:
            self.sessao = None

    def verificar_conexao(self):
        try:
            self._solicitar("verificar_conexao")
            return True
        except (ConnectionError, RuntimeError):
            return False


db: BancoCentral


class ManipuladorAPI(http.server.BaseHTTPRequestHandler):
    banco: BancoLocal
    token: str
    sessoes: dict[str, tuple[str, float, str]] = {}
    sessoes_lock = threading.Lock()
    tentativas_login: dict[str, tuple[int, float]] = {}
    tentativas_login_lock = threading.Lock()

    def log_message(self, formato, *args):
        print(f"{self.address_string()} - {formato % args}")

    def _responder(self, status, corpo, sessao=None):
        if sessao:
            corpo["sessao"] = sessao
        conteudo = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(conteudo)))
        self.end_headers()
        self.wfile.write(conteudo)

    def _obter_usuario_sessao(self, identificador):
        if not identificador:
            return None
        with self.sessoes_lock:
            sessao = self.sessoes.get(identificador)
            if not sessao:
                return None
            usuario, ultima_atividade, token_csrf = sessao
            if time.monotonic() - ultima_atividade > 8 * 60 * 60:
                del self.sessoes[identificador]
                return None
            if not self.banco.usuario_ativo(usuario):
                del self.sessoes[identificador]
                return None
            self.sessoes[identificador] = (
                usuario,
                time.monotonic(),
                token_csrf,
            )
            return usuario

    def _criar_sessao(self, usuario):
        identificador = secrets.token_urlsafe(32)
        token_csrf = secrets.token_urlsafe(32)
        with self.sessoes_lock:
            self.sessoes[identificador] = (
                usuario,
                time.monotonic(),
                token_csrf,
            )
        return identificador, token_csrf

    def _token_csrf(self, identificador):
        with self.sessoes_lock:
            sessao = self.sessoes.get(identificador)
            if not sessao:
                return None
            return sessao[2]

    def _cookie_padrao_sessao(self, max_age=28800):
        return f"Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}"

    def _responder_html(self, status, conteudo, cookie=None):
        dados = conteudo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; "
            "script-src 'self'; "
            "form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(dados)

    def _responder_javascript(self, codigo):
        dados = codigo.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(dados)

    def _redirecionar_web(self, mensagem):
        self.send_response(303)
        self.send_header("Location", f"/?mensagem={mensagem}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _cookie_sessao(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except CookieError:
            return ""
        morsel = cookies.get("sistema_sessao")
        return morsel.value if morsel else ""

    def _pagina(self, titulo, conteudo):
        return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#2c5f97">
<title>{html.escape(titulo)} — Centro de Reabilitação</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  color: #243447; background: #f1f7f2; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; }}
header {{ background: #075b3b; color: white; padding: 1rem; }}
.faixa-brasil {{ height: 6px; background: linear-gradient(90deg, #159447 0 33.33%, #ffcb2f 33.33% 66.66%, #1766a8 66.66%); }}
header .barra {{ max-width: 900px; margin: auto; display: flex; gap: .75rem;
  justify-content: space-between; align-items: center; flex-wrap: wrap; }}
main {{ width: min(100% - 1.25rem, 900px); margin: 1rem auto 3rem; }}
.cartao {{ background: white; border-radius: 12px; padding: 1rem;
  margin: 1rem 0; box-shadow: 0 2px 8px #18324a12; }}
.login {{ max-width: 440px; margin: 8vh auto; }}
h1 {{ font-size: 1.25rem; margin: .25rem 0; }}
h2 {{ font-size: 1.12rem; margin-top: 0; color: #075b3b; }}
p {{ line-height: 1.5; }}
nav {{ display: flex; flex-wrap: wrap; gap: .5rem; }}
a, .botao {{ color: #1766a8; }}
nav a {{ background: white; border: 1px solid #cfe0d3; border-radius: 999px;
  padding: .55rem .8rem; text-decoration: none; }}
label {{ display: block; font-weight: 600; margin: .8rem 0 .3rem; }}
input, select, button {{ font: inherit; }}
input, select {{ width: 100%; padding: .7rem; border: 1px solid #bdc9d6;
  border-radius: 8px; background: white; }}
button, .botao {{ border: 0; border-radius: 8px; background: #159447;
  color: white; padding: .75rem 1rem; cursor: pointer; text-decoration: none;
  display: inline-block; }}
.sair {{ background: #9c2f35; }}
.botao-secundario {{ background: #1766a8; }}
.botao-destaque {{ background: #ffcb2f; color: #263746; }}
.aviso {{ border-left: 4px solid #d49a22; }}
.registro {{ border-top: 1px solid #e6ebf0; padding: .7rem 0; overflow-wrap: anywhere; }}
.registro:first-of-type {{ border-top: 0; }}
.selecao-paciente {{ display: flex; align-items: flex-start; gap: .6rem; margin: 0; }}
.selecao-paciente input {{ width: auto; margin-top: .2rem; }}
.entrada-acompanhante {{ display: flex; align-items: center; gap: .6rem; }}
.entrada-acompanhante > input {{ flex: 1; min-width: 0; }}
.opcao-checkbox {{ display: flex; align-items: center; gap: .4rem; margin: 0;
  font-weight: 500; white-space: nowrap; }}
.opcao-checkbox input {{ width: auto; margin: 0; }}
.dados-paciente {{ display: block; }}
.muted {{ color: #667788; font-size: .92rem; }}
.mensagem {{ background: #e7f2ff; border-radius: 8px; padding: .75rem; }}
@media (min-width: 680px) {{
  .duas-colunas {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
  .cartao {{ padding: 1.25rem; }}
}}
</style>
</head>
<body><div class="faixa-brasil"></div>{conteudo}</body>
</html>"""

    def _pagina_login(self, mensagem=""):
        aviso = (
            f'<p class="mensagem" role="status">{html.escape(mensagem)}</p>'
            if mensagem
            else ""
        )
        corpo = f"""<main class="cartao login">
<h1>Centro de Reabilitação</h1>
<p class="muted">Açailândia — Sistema de Atendimento</p>
{aviso}
<form method="post" action="/web/login" autocomplete="on">
  <label for="usuario">Usuário</label>
  <input id="usuario" name="usuario" required autocomplete="username" maxlength="80" autofocus>
  <label for="senha">Senha</label>
  <input id="senha" name="senha" type="password" required autocomplete="current-password" maxlength="256">
  <p><button type="submit">Entrar</button></p>
</form>
</main>"""
        corpo += '<script src="/web/formulario.js" defer></script>'
        self._responder_html(200, self._pagina("Entrar", corpo))

    def _pagina_principal(self, usuario, identificador, token_csrf, mensagem=""):
        mensagem_html = (
            f'<p class="mensagem" role="status">{html.escape(mensagem)}</p>'
            if mensagem
            else ""
        )
        somente_cadastro = funcao_somente_cadastro(
            self.banco.obter_funcao(usuario), usuario
        )
        registros_pacientes = self.banco.listar_pacientes_para_exclusao()
        historico = self.banco.listar_historico()
        opcoes_tipo_atendimento = "".join(
            f'<option value="{html.escape(tipo, quote=True)}">'
            f'{html.escape(tipo)}</option>'
            for tipo in TIPOS_ATENDIMENTO
        )
        if registros_pacientes and somente_cadastro:
            lista_pacientes = "".join(
                '<div class="registro"><strong>'
                f'{html.escape(nome)}</strong><span class="muted">'
                f'CPF: {html.escape(exibir_cpf(cpf))} · Cartão SUS: '
                f'{html.escape(cartao_sus)}<br>Cadastro: '
                f'{html.escape(data_cadastro)}</span></div>'
                for _, nome, cpf, cartao_sus, data_cadastro
                in registros_pacientes
            )
            controles_exclusao = lista_pacientes
        elif registros_pacientes:
            lista_pacientes = "".join(
                '<div class="registro"><label class="selecao-paciente">'
                f'<input type="checkbox" name="paciente_id" value="{int(paciente_id)}">'
                '<span class="dados-paciente"><strong>'
                f'{html.escape(nome)}</strong><span class="muted">'
                f'CPF: {html.escape(exibir_cpf(cpf))} · Cartão SUS: '
                f'{html.escape(cartao_sus)}<br>Cadastro: '
                f'{html.escape(data_cadastro)}</span></span></label></div>'
                for paciente_id, nome, cpf, cartao_sus, data_cadastro
                in registros_pacientes
            )
            controles_exclusao = f"""<form method="post" action="/web/excluir-pacientes"
data-confirm="Excluir os pacientes selecionados e seus atendimentos? Esta ação não pode ser desfeita.">
<input type="hidden" name="csrf" value="{html.escape(token_csrf, quote=True)}">
{lista_pacientes}
<p><button type="submit">Apagar pacientes selecionados</button></p>
</form>
<form method="post" action="/web/excluir-todos-pacientes"
data-confirm="Tem certeza que deseja apagar todos os pacientes e atendimentos? Esta ação não pode ser desfeita.">
<input type="hidden" name="csrf" value="{html.escape(token_csrf, quote=True)}">
<p><button class="sair" type="submit">Apagar todos</button></p>
</form>"""
        else:
            controles_exclusao = "<p class=\"muted\">Nenhum paciente cadastrado.</p>"
        lista_historico = "".join(
            '<div class="registro"><strong>'
            f'{html.escape(acao)}</strong> — {html.escape(usuario_registro)}'
            f'<div class="muted">{html.escape(data_hora)} · '
            f'{html.escape(detalhes or "-")}</div></div>'
            for usuario_registro, acao, data_hora, detalhes in historico
        ) or '<p class="muted">Nenhuma atividade registrada.</p>'
        if somente_cadastro:
            controles_historico = ""
        else:
            controles_historico = f"""<form method="post" action="/web/limpar-historico"
data-confirm="Apagar todo o histórico de alterações? Esta ação não pode ser desfeita.">
<input type="hidden" name="csrf" value="{html.escape(token_csrf, quote=True)}">
<p><button class="sair" type="submit">Apagar histórico</button></p>
</form>"""
        links_restritos = '<a href="#pacientes">Pacientes</a><a href="#historico">Histórico</a>'
        secoes_restritas = f"""<section id="pacientes" class="cartao"><h2>Pacientes cadastrados</h2>
{controles_exclusao}</section>
<section id="historico" class="cartao"><h2>Histórico recente</h2>
{lista_historico}
{controles_historico}</section>"""
        corpo = f"""<header><div class="barra">
<div><h1>Centro de Reabilitação</h1><div>Conectado como {html.escape(usuario)}</div></div>
<form method="post" action="/web/sair">
  <input type="hidden" name="csrf" value="{html.escape(token_csrf, quote=True)}">
  <button class="sair" type="submit">Sair</button>
</form></div></header>
<main>
{mensagem_html}
<nav aria-label="Seções">
<a href="#cadastro">Cadastrar</a>{links_restritos}
</nav>
<section id="cadastro" class="cartao"><h2>Cadastrar paciente</h2>
<form method="post" action="/web/cadastrar">
<input type="hidden" name="csrf" value="{html.escape(token_csrf, quote=True)}">
<div class="duas-colunas">
<div><label for="nome">Nome completo *</label><input id="nome" name="nome" required maxlength="200" autocomplete="name" style="text-transform: uppercase"></div>
<div><label for="data_nascimento">Data de nascimento *</label><input id="data_nascimento" name="data_nascimento" required maxlength="10" inputmode="numeric" pattern="[0-9]{{2}}/[0-9]{{2}}/[0-9]{{4}}" placeholder="DD/MM/AAAA"></div>
<div><label for="cartao_sus">Cartão SUS *</label><input id="cartao_sus" name="cartao_sus" required minlength="7" maxlength="15" inputmode="numeric" pattern="[0-9]{7,15}" title="Informe de 7 a 15 algarismos"></div>
<div><label for="cpf">CPF</label><input id="cpf" name="cpf" maxlength="14" inputmode="numeric" placeholder="000.000.000-00" autocomplete="off"></div>
<div><label for="rg">RG</label><input id="rg" name="rg" maxlength="11" inputmode="numeric" pattern="[0-9]{0,11}"></div>
<div><label for="sexo">Sexo *</label><select id="sexo" name="sexo" required>
<option value="">Selecione</option><option>Masculino</option><option>Feminino</option><option>Não Informado</option></select></div>
<div><label for="acompanhante">Nome do acompanhante/responsável</label>
<div class="entrada-acompanhante">
<input id="acompanhante" name="acompanhante" maxlength="200" autocomplete="off" style="text-transform: uppercase">
<label class="opcao-checkbox" for="sem_acompanhante"><input id="sem_acompanhante" name="sem_acompanhante" type="checkbox" value="sim"><span>Não veio acompanhado</span></label>
</div></div>
</div>
<label for="tipo_atendimento">Tipo de atendimento *</label>
<select id="tipo_atendimento" name="tipo_atendimento" required>
<option value="">Selecione</option>{opcoes_tipo_atendimento}
</select>
<p><button type="submit">Adicionar Paciente</button></p>
</form></section>
{secoes_restritas}
<script src="/web/formulario.js" defer></script>
</main>"""
        self._responder_html(
            200,
            self._pagina("Sistema de Atendimento", corpo),
            cookie=(
                f"sistema_sessao={identificador}; {self._cookie_padrao_sessao()}"
            ),
        )

    def _responder_erro_web(self, mensagem, status=400):
        corpo = (
            '<main class="cartao login"><h1>Não foi possível concluir</h1>'
            f'<p>{html.escape(mensagem)}</p><p><a href="/">Voltar ao sistema</a></p></main>'
        )
        self._responder_html(status, self._pagina("Erro", corpo))

    def do_GET(self):
        caminho = urlsplit(self.path)
        if caminho.path == "/web/formulario.js":
            self._responder_javascript(SCRIPT_MASCARA_FORMULARIO)
            return
        if caminho.path not in ("/", "/web/"):
            self._responder_html(
                404,
                self._pagina("Página não encontrada", "<main><h1>Página não encontrada</h1></main>"),
            )
            return
        identificador = self._cookie_sessao()
        usuario = self._obter_usuario_sessao(identificador)
        if not usuario:
            mensagem = "Sessão encerrada ou expirada." if identificador else ""
            self._pagina_login(mensagem)
            return
        token_csrf = self._token_csrf(identificador)
        if not token_csrf:
            self._pagina_login("Sessão expirada. Entre novamente.")
            return
        try:
            mensagem = parse_qs(
                caminho.query, keep_blank_values=True
            ).get("mensagem", [""])[0]
            self._pagina_principal(usuario, identificador, token_csrf, mensagem)
        except sqlite3.Error:
            self._responder_erro_web(
                "Erro ao consultar os dados. Tente novamente.", 500
            )

    def _ler_formulario_web(self):
        tipo_conteudo = self.headers.get("Content-Type", "").split(";", 1)[0]
        if tipo_conteudo != "application/x-www-form-urlencoded":
            raise ValueError("Tipo de formulário inválido.")
        tamanho = int(self.headers.get("Content-Length", "0"))
        if tamanho <= 0 or tamanho > 16384:
            raise ValueError("Formulário inválido.")
        bruto = self.rfile.read(tamanho).decode("utf-8")
        return parse_qs(bruto, keep_blank_values=True, max_num_fields=1024)

    @staticmethod
    def _valor_formulario(formulario, campo):
        return formulario.get(campo, [""])[0].strip()

    def _csrf_web_valido(self, formulario, identificador):
        token_enviado = self._valor_formulario(formulario, "csrf")
        token_esperado = self._token_csrf(identificador)
        return bool(
            token_esperado
            and hmac.compare_digest(token_enviado, token_esperado)
        )

    def _web_login_bloqueado(self):
        agora = time.monotonic()
        with self.tentativas_login_lock:
            tentativas, bloqueado_ate = self.tentativas_login.get(
                self.client_address[0], (0, 0)
            )
            if bloqueado_ate and agora >= bloqueado_ate:
                self.tentativas_login.pop(self.client_address[0], None)
                return False
            return bloqueado_ate > agora or tentativas >= 5

    def _registrar_falha_login(self):
        ip = self.client_address[0]
        with self.tentativas_login_lock:
            tentativas, bloqueado_ate = self.tentativas_login.get(ip, (0, 0))
            tentativas += 1
            if tentativas >= 5:
                bloqueado_ate = time.monotonic() + 60
            self.tentativas_login[ip] = (tentativas, bloqueado_ate)

    def _processar_web(self):
        try:
            formulario = self._ler_formulario_web()
        except (ValueError, UnicodeDecodeError):
            self._responder_erro_web("Formulário inválido.")
            return
        identificador = self._cookie_sessao()
        usuario = self._obter_usuario_sessao(identificador)

        if self.path == "/web/login":
            origem = self.headers.get("Origin")
            site = self.headers.get("Sec-Fetch-Site", "")
            host = self.headers.get("Host", "")
            origens_permitidas = {f"http://{host}", f"https://{host}"}
            if origem and origem not in origens_permitidas:
                self._responder_erro_web("Origem da solicitação não permitida.", 403)
                return
            if not origem and site == "cross-site":
                self._responder_erro_web("Origem da solicitação não permitida.", 403)
                return
            if self._web_login_bloqueado():
                self._responder_erro_web(
                    "Muitas tentativas de login. Aguarde um minuto.", 429
                )
                return
            nome = self._valor_formulario(formulario, "usuario")
            senha = formulario.get("senha", [""])[0]
            if not nome or not senha or len(nome) > 80 or len(senha) > 256:
                self._registrar_falha_login()
                self._pagina_login("Usuário ou senha incorretos.")
                return
            try:
                autenticado = self.banco.autenticar(nome, senha)
            except sqlite3.Error:
                self._responder_erro_web(
                    "Erro ao consultar o banco de dados. Tente novamente.", 500
                )
                return
            if not autenticado:
                self._registrar_falha_login()
                self._pagina_login("Usuário ou senha incorretos.")
                return
            with self.tentativas_login_lock:
                self.tentativas_login.pop(self.client_address[0], None)
            self.banco.atualizar_acesso(nome)
            self.banco.registrar_acao(nome, "LOGIN", "Acesso pela interface web")
            sessao, _ = self._criar_sessao(nome)
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header(
                "Set-Cookie",
                f"sistema_sessao={sessao}; {self._cookie_padrao_sessao()}",
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        if not usuario:
            self._pagina_login("Sessão expirada. Entre novamente.")
            return
        if not self._csrf_web_valido(formulario, identificador):
            self._responder_erro_web("Sessão inválida. Atualize a página.", 403)
            return

        try:
            if (
                funcao_somente_cadastro(
                    self.banco.obter_funcao(usuario), usuario
                )
                and self.path not in ROTAS_WEB_RECEPCAO
            ):
                self._responder_erro_web(
                    "Seu perfil permite apenas cadastrar pacientes.", 403
                )
                return
            if self.path == "/web/sair":
                self._encerrar_sessao(identificador)
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header(
                    "Set-Cookie",
                    f"sistema_sessao=; {self._cookie_padrao_sessao(0)}",
                )
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            if self.path == "/web/excluir-pacientes":
                valores_ids = formulario.get("paciente_id", [])
                if not valores_ids or any(
                    not valor.isdecimal() or len(valor) > 19
                    for valor in valores_ids
                ):
                    raise ValueError("Nenhum paciente válido foi selecionado.")
                quantidade = self.banco.excluir_pacientes(
                    [int(valor) for valor in valores_ids], usuario
                )
                self._redirecionar_web(
                    f"{quantidade}+paciente(s)+selecionado(s)+excluído(s)."
                )
                return
            if self.path == "/web/excluir-todos-pacientes":
                quantidade = self.banco.excluir_todos_pacientes(usuario)
                self._redirecionar_web(
                    f"{quantidade}+paciente(s)+e+atendimentos+excluídos."
                )
                return
            if self.path == "/web/excluir-todos-atendimentos":
                quantidade = self.banco.excluir_todos_atendimentos(usuario)
                self._redirecionar_web(
                    f"{quantidade}+atendimento(s)+excluído(s)."
                )
                return
            if self.path == "/web/limpar-historico":
                quantidade = self.banco.limpar_historico()
                self._redirecionar_web(
                    f"{quantidade}+registro(s)+do+histórico+apagado(s)."
                )
                return
            if self.path == "/web/cadastrar":
                rg = self._valor_formulario(formulario, "rg") or None
                validar_documentos(rg)
                sem_acompanhante = formulario.get("sem_acompanhante", [])
                if sem_acompanhante not in ([], ["sim"]):
                    raise ValueError("A opção de acompanhante é inválida.")
                acompanhante = (
                    None
                    if sem_acompanhante
                    else self._valor_formulario(formulario, "acompanhante") or None
                )
                dados = [
                    rg,
                    None,
                    self._valor_formulario(formulario, "cpf") or None,
                    self._valor_formulario(formulario, "cartao_sus"),
                    self._valor_formulario(formulario, "nome"),
                    self._valor_formulario(formulario, "data_nascimento"),
                    self._valor_formulario(formulario, "sexo"),
                    acompanhante,
                ]
                if not all(dados[indice] for indice in (3, 4, 5, 6)):
                    raise ValueError("Preencha todos os campos obrigatórios.")
                dados[5] = validar_data_nascimento(dados[5])
                if dados[6] not in ("Masculino", "Feminino", "Não Informado"):
                    raise ValueError("Selecione uma opção válida para sexo.")
                dados[3] = validar_cartao_sus(dados[3])
                dados[4] = validar_nome(dados[4])
                if dados[7]:
                    dados[7] = validar_nome(dados[7])
                tipo_atendimento = validar_tipo_atendimento(
                    self._valor_formulario(formulario, "tipo_atendimento")
                )
                limites = (11, 11, 14, 15, 200, 10, 20, 200)
                if any(
                    valor is not None and len(valor) > limite
                    for valor, limite in zip(dados, limites)
                ):
                    raise ValueError("Um ou mais campos excedem o tamanho permitido.")
                self.banco.cadastrar_paciente(
                    dados, usuario, tipo_atendimento
                )
                self.banco.registrar_acao(
                    usuario, "CADASTRO", f"Paciente {dados[4]} cadastrado"
                )
                self._redirecionar_web(
                    "Paciente+e+atendimento+adicionados+com+sucesso."
                )
                return
            if self.path == "/web/atendimento":
                paciente_id = self._valor_formulario(formulario, "paciente_id")
                tipo = validar_tipo_atendimento(
                    self._valor_formulario(formulario, "tipo")
                )
                if not paciente_id.isdecimal():
                    raise ValueError("Selecione um paciente e informe o atendimento.")
                pacientes = self.banco.listar_pacientes_atendimento()
                selecionado = next(
                    (p for p in pacientes if p[0] == int(paciente_id)), None
                )
                if not selecionado:
                    raise ValueError("O paciente selecionado não foi encontrado.")
                self.banco.registrar_atendimento(
                    int(paciente_id), tipo, usuario
                )
                self._redirecionar_web("Atendimento+salvo+com+sucesso.")
                return
            self._responder_erro_web("Ação não encontrada.", 404)
        except ValueError as erro:
            self._responder_erro_web(str(erro))
        except (ConnectionError, RuntimeError) as erro:
            self._responder_erro_web(
                f"Não foi possível concluir a operação no servidor: {erro}", 502
            )
        except sqlite3.IntegrityError:
            self._responder_erro_web(
                "Não foi possível salvar. Verifique se o CPF já está cadastrado."
            )
        except sqlite3.Error:
            self._responder_erro_web(
                "Erro ao acessar o banco de dados. Tente novamente.", 500
            )

    def do_POST(self):
        if self.path.startswith("/web/"):
            self._processar_web()
            return
        if self.path != "/api":
            self._responder(404, {"ok": False, "erro": "Rota não encontrada."})
            return
        autorizacao = self.headers.get("Authorization", "")
        token_recebido = autorizacao.removeprefix("Bearer ").strip()
        if not hmac.compare_digest(token_recebido, self.token):
            self._responder(401, {"ok": False, "erro": "Acesso não autorizado."})
            return
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
            if tamanho <= 0 or tamanho > 16384:
                raise ValueError("Tamanho de requisição inválido.")
            payload = json.loads(self.rfile.read(tamanho).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("O corpo da requisição deve ser um objeto JSON.")
            operacao = payload.get("operacao")
            dados = payload.get("dados", [])
            if operacao == "autenticar":
                usuario_login = payload.get("usuario", "")
                senha = payload.get("senha", "")
                if not isinstance(usuario_login, str) or not isinstance(senha, str):
                    raise ValueError("Usuário e senha devem ser texto.")
                autenticado = self.banco.autenticar(
                    usuario_login, senha
                )
                if not autenticado:
                    self._responder(200, {"ok": True, "dados": False})
                    return
                if funcao_somente_cadastro(
                    self.banco.obter_funcao(usuario_login), usuario_login
                ):
                    self.banco.registrar_acao(
                        usuario_login, "LOGIN", "Acesso pela aplicação desktop"
                    )
                identificador, _ = self._criar_sessao(usuario_login)
                self._responder(200, {"ok": True, "dados": True}, identificador)
                return

            identificador = self.headers.get("X-Session-Token", "")
            usuario = self._obter_usuario_sessao(identificador)
            if not usuario:
                self._responder(401, {"ok": False, "erro": "Sessão inválida ou expirada."})
                return
            operacoes = {
                "verificar_conexao": lambda: True,
                "obter_funcao": lambda: self.banco.obter_funcao(usuario),
                "atualizar_acesso": lambda: self.banco.atualizar_acesso(usuario),
                "registrar_acao": lambda: self.banco.registrar_acao(
                    usuario, payload.get("acao", ""), payload.get("detalhes", "")
                ),
                "listar_pacientes_atendimento": self.banco.listar_pacientes_atendimento,
                "registrar_atendimento": lambda: self.banco.registrar_atendimento(
                    payload.get("paciente_id"), payload.get("tipo", ""), usuario
                ),
                "listar_pacientes": self.banco.listar_pacientes,
                "listar_pacientes_para_exclusao": self.banco.listar_pacientes_para_exclusao,
                "excluir_pacientes": lambda: self.banco.excluir_pacientes(
                    payload.get("paciente_ids"), usuario
                ),
                "excluir_todos_pacientes": lambda: self.banco.excluir_todos_pacientes(
                    usuario
                ),
                "excluir_todos_atendimentos": lambda: self.banco.excluir_todos_atendimentos(
                    usuario
                ),
                "listar_historico": self.banco.listar_historico,
                "limpar_historico": self.banco.limpar_historico,
                "cadastrar_paciente": lambda: self._cadastrar_paciente_api(
                    dados, usuario, payload.get("tipo_atendimento")
                ),
                "encerrar_sessao": lambda: self._encerrar_sessao(identificador),
            }
            if operacao not in operacoes:
                self._responder(400, {"ok": False, "erro": "Operação inválida."})
                return
            if not operacao_permitida(
                self.banco.obter_funcao(usuario), operacao, usuario
            ):
                self._responder(
                    403,
                    {
                        "ok": False,
                        "erro": "Seu perfil permite apenas cadastrar pacientes.",
                    },
                )
                return
            resultado = operacoes[operacao]()
            self._responder(200, {"ok": True, "dados": resultado})
        except (ValueError, TypeError, json.JSONDecodeError, sqlite3.Error) as erro:
            self._responder(400, {"ok": False, "erro": str(erro)})

    def _encerrar_sessao(self, identificador):
        with self.sessoes_lock:
            self.sessoes.pop(identificador, None)

    def _cadastrar_paciente_api(self, dados, usuario, tipo_atendimento):
        paciente_id = self.banco.cadastrar_paciente(
            dados, usuario, tipo_atendimento
        )
        if funcao_somente_cadastro(
            self.banco.obter_funcao(usuario), usuario
        ):
            self.banco.registrar_acao(
                usuario, "CADASTRO", f"Paciente {dados[4]} cadastrado"
            )
        return paciente_id


# ------------------- INTERFACE GRÁFICA ESTILIZADA -------------------
class SistemaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Atendimento — Centro de Reabilitação de Açailândia")
        self.root.geometry("950x680")
        self.root.configure(bg=COR_FUNDO_PAINEL)
        self.modo_escuro = False
        self._fila_estado_conectividade = queue.Queue()
        self._parar_monitoramento_conectividade = threading.Event()
        self._ultimo_estado_conectividade = None
        self.label_status_rede = None
        self.label_status_internet = None
        self.root.protocol("WM_DELETE_WINDOW", self.fechar_aplicativo)
        threading.Thread(
            target=self._monitorar_conectividade,
            daemon=True,
        ).start()
        self.root.after(500, self._atualizar_status_conectividade)
        
        # Centralizar janela
        self.centralizar_janela(950, 680)
        
        # Configurar estilo dos componentes
        self.configurar_estilos()
        
        self.usuario_logado = None
        self.funcao_usuario = None
        self.tela_login()

    def _monitorar_conectividade(self):
        while not self._parar_monitoramento_conectividade.is_set():
            estado = verificar_conectividade_dispositivo()
            self._fila_estado_conectividade.put(estado)
            if self._parar_monitoramento_conectividade.wait(5):
                break

    def _atualizar_status_conectividade(self):
        try:
            while True:
                self._ultimo_estado_conectividade = (
                    self._fila_estado_conectividade.get_nowait()
                )
        except queue.Empty:
            pass

        if (
            self._ultimo_estado_conectividade is not None
            and self.label_status_rede is not None
            and self.label_status_internet is not None
        ):
            conectado_a_rede, tem_internet = self._ultimo_estado_conectividade
            cor_rede = "#24734d" if conectado_a_rede else "#9a6500"
            fundo_rede = "#e9f6ee" if conectado_a_rede else "#fff4df"
            self.label_status_rede.configure(
                text="Rede: conectada" if conectado_a_rede else "Rede: desconectada",
                fg=self._cor_tema(cor_rede, "foreground"),
                bg=self._cor_tema(fundo_rede, "background"),
            )

            if not conectado_a_rede:
                texto_internet = "Internet: sem rede"
            else:
                texto_internet = (
                    "Internet: disponível"
                    if tem_internet
                    else "Internet: não detectada"
                )
            cor_internet = "#24734d" if tem_internet else "#9a6500"
            fundo_internet = "#e9f6ee" if tem_internet else "#fff4df"
            self.label_status_internet.configure(
                text=texto_internet,
                fg=self._cor_tema(cor_internet, "foreground"),
                bg=self._cor_tema(fundo_internet, "background"),
            )

        if not self._parar_monitoramento_conectividade.is_set():
            self.root.after(500, self._atualizar_status_conectividade)

    def fechar_aplicativo(self):
        self._parar_monitoramento_conectividade.set()
        self.root.destroy()

    def centralizar_janela(self, largura, altura):
        tela_largura = self.root.winfo_screenwidth()
        tela_altura = self.root.winfo_screenheight()
        x = (tela_largura / 2) - (largura / 2)
        y = (tela_altura / 2) - (altura / 2)
        self.root.geometry(f"{largura}x{altura}+{int(x)}+{int(y)}")

    def configurar_estilos(self):
        estilo = ttk.Style(self.root)
        estilo.theme_use('clam')
        fundo = self._cor_tema(COR_FUNDO, "background")
        cartao = self._cor_tema(COR_CARTA, "background")
        texto = self._cor_tema(COR_TEXTO, "foreground")
        campo_atendimento = self._cor_tema("#dceeff", "selectcolor")
        cor_primaria = self._cor_tema(COR_PRIMARIA, "foreground")
        verde_escuro = self._cor_tema(COR_BRASIL_VERDE_ESCURO, "background")
        verde = self._cor_tema(COR_BRASIL_VERDE, "background")
        azul = self._cor_tema(COR_BRASIL_AZUL, "background")
        branco = self._cor_tema("white", "foreground")
        
        # Estilo dos Botões
        estilo.configure("Botao.TButton", 
                        font=FONTE_NORMAL,
                        padding=10)
        estilo.configure("BotaoPrincipal.TButton",
                        font=FONTE_SUBTITULO,
                        padding=12)
        estilo.configure("BotaoSair.TButton",
                        font=FONTE_NORMAL,
                        padding=8)
        
        # Estilo dos Labels
        estilo.configure("Titulo.TLabel", 
                        font=FONTE_TITULO,
                        foreground=cor_primaria,
                        background=fundo)
        estilo.configure("Subtitulo.TLabel", 
                        font=FONTE_SUBTITULO, 
                        foreground=texto,
                        background=fundo)
        estilo.configure("Normal.TLabel", 
                        font=FONTE_NORMAL, 
                        foreground=texto,
                        background=fundo)
        estilo.configure("Status.TLabel",
                        font=FONTE_PEQUENA,
                        background=cartao)
        estilo.configure(
            "TCombobox",
            fieldbackground=cartao,
            background=cartao,
            foreground=texto,
            arrowcolor=texto,
        )
        estilo.map(
            "TCombobox",
            fieldbackground=[("readonly", cartao)],
            foreground=[("readonly", texto)],
        )
        estilo.configure(
            "CadastroAtendimento.TCombobox",
            fieldbackground=campo_atendimento,
            background=campo_atendimento,
            foreground=texto,
            arrowcolor=texto,
        )
        estilo.map(
            "CadastroAtendimento.TCombobox",
            fieldbackground=[("readonly", campo_atendimento)],
            foreground=[("readonly", texto)],
        )
        estilo.configure(
            "Treeview",
            background=cartao,
            fieldbackground=cartao,
            foreground=texto,
            rowheight=28,
            font=FONTE_NORMAL,
        )
        estilo.configure(
            "Treeview.Heading",
            background=verde_escuro,
            foreground=branco,
            font=FONTE_NORMAL + ("bold",),
            padding=(8, 7),
        )
        estilo.map(
            "Treeview",
            background=[("selected", azul)],
            foreground=[("selected", branco)],
        )
        estilo.map(
            "Treeview.Heading",
            background=[("active", verde)],
        )

    def _cor_tema(self, cor, propriedade):
        mapa_escuro = (
            CORES_FUNDO_ESCURO
            if propriedade in (
                "bg",
                "background",
                "activebackground",
                "highlightbackground",
                "selectbackground",
                "fieldbackground",
                "selectcolor",
            )
            else CORES_TEXTO_ESCURO
        )
        mapa = (
            mapa_escuro
            if self.modo_escuro
            else {escuro: claro for claro, escuro in mapa_escuro.items()}
        )
        return mapa.get(cor.lower(), cor) if isinstance(cor, str) else cor

    def aplicar_tema(self, janela=None):
        alvo = janela or self.root
        opcoes_fundo = (
            "bg",
            "background",
            "activebackground",
            "highlightbackground",
            "selectbackground",
            "fieldbackground",
            "selectcolor",
        )
        opcoes_texto = (
            "fg",
            "foreground",
            "activeforeground",
            "highlightcolor",
            "insertbackground",
            "selectforeground",
        )
        fila = [alvo]
        while fila:
            widget = fila.pop()
            fila.extend(widget.winfo_children())
            opcoes = set(widget.keys())
            atualizacoes = {}
            for opcao in opcoes_fundo:
                if opcao in opcoes:
                    valor = widget.cget(opcao)
                    novo_valor = self._cor_tema(valor, opcao)
                    if novo_valor != valor:
                        atualizacoes[opcao] = novo_valor
            for opcao in opcoes_texto:
                if opcao in opcoes:
                    valor = widget.cget(opcao)
                    novo_valor = self._cor_tema(valor, opcao)
                    if novo_valor != valor:
                        atualizacoes[opcao] = novo_valor
            if atualizacoes:
                widget.configure(**atualizacoes)
            if (
                isinstance(widget, ttk.Combobox)
                and widget.cget("style") == "CadastroAtendimento.TCombobox"
            ):
                self._aplicar_cores_lista_atendimento(widget)
        self.configurar_estilos()

    def _aplicar_cores_lista_atendimento(self, combobox):
        fundo = (
            "#145b90"
            if self.modo_escuro
            else "#dceeff"
        )
        texto = (
            "#e2e8ee"
            if self.modo_escuro
            else COR_TEXTO
        )
        selecao = (
            "#2f86bf"
            if self.modo_escuro
            else COR_BRASIL_AZUL
        )
        janela_lista = combobox.tk.call(
            "ttk::combobox::PopdownWindow", combobox
        )
        lista = f"{janela_lista}.f.l"
        combobox.tk.call(
            lista,
            "configure",
            "-background",
            fundo,
            "-foreground",
            texto,
            "-selectbackground",
            selecao,
            "-selectforeground",
            "white",
        )

    def alternar_modo_escuro(self):
        self.modo_escuro = not self.modo_escuro
        self.tela_principal()

    def adicionar_faixa_cores(self, parent):
        faixa = tk.Frame(parent, height=6)
        faixa.pack(fill=tk.X, side=tk.TOP)
        faixa.pack_propagate(False)
        for cor in (COR_BRASIL_VERDE, COR_BRASIL_AMARELO, COR_BRASIL_AZUL):
            tk.Frame(faixa, bg=cor).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def criar_cartao(self, parent):
        frame = tk.Frame(parent, bg=COR_CARTA, padx=25, pady=25, 
                         relief=tk.FLAT, bd=0)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        return frame

    def registrar_acao(self, acao, detalhes=""):
        db.registrar_acao(self.usuario_logado, acao, detalhes)

    def limpar_tela(self):
        self.label_status_rede = None
        self.label_status_internet = None
        for widget in self.root.winfo_children():
            widget.destroy()

    def tela_login(self):
        self.limpar_tela()
        
        # Fundo
        self.root.configure(bg=COR_BRASIL_VERDE_ESCURO)
        self.adicionar_faixa_cores(self.root)
        
        # Container central
        container = tk.Frame(self.root, bg=COR_BRASIL_VERDE_ESCURO)
        container.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Cartão de login
        cartao = tk.Frame(container, bg=COR_CARTA, padx=50, pady=40, 
                          relief=tk.RAISED, bd=1)
        cartao.pack()
        
        # Logo/Título
        tk.Label(cartao, text="🏥", font=("Arial", 40), bg=COR_CARTA).pack()
        tk.Label(cartao, text="Centro de Reabilitação", 
                 font=("Segoe UI", 16, "bold"), fg=COR_PRIMARIA, bg=COR_CARTA).pack(pady=5)
        tk.Label(cartao, text="Açailândia — Sistema de Atendimento", 
                 font=FONTE_NORMAL, fg=COR_TEXTO_CLARO, bg=COR_CARTA).pack(pady=5)
        tk.Frame(cartao, bg=COR_BRASIL_AMARELO, height=4, width=300).pack(pady=15)
        
        # Campos
        tk.Label(cartao, text="Usuário", font=FONTE_NORMAL, fg=COR_TEXTO, bg=COR_CARTA).pack(anchor=tk.W)
        self.entry_usuario = tk.Entry(cartao, font=FONTE_NORMAL, width=35,
                                     bd=1, relief=tk.SOLID)
        self.entry_usuario.pack(padx=10, pady=(5, 15))
        self.entry_usuario.bind("<Return>", self._focar_senha)
        
        tk.Label(cartao, text="Senha", font=FONTE_NORMAL, fg=COR_TEXTO, bg=COR_CARTA).pack(anchor=tk.W)
        self.entry_senha = tk.Entry(cartao, font=FONTE_NORMAL, width=35,
                                    bd=1, relief=tk.SOLID, show="*")
        self.entry_senha.pack(padx=10, pady=(5, 20))
        self.entry_senha.bind("<Return>", self._entrar_com_teclado)
        
        # Botão
        btn_entrar = tk.Button(cartao, text="🔑 Entrar no Sistema", 
                              command=self.verificar_login,
                              bg=COR_BRASIL_VERDE, fg="white", font=FONTE_SUBTITULO,
                              padx=20, pady=10, relief=tk.FLAT, cursor="hand2")
        btn_entrar.pack(fill=tk.X, pady=5)
        tk.Button(
            cartao,
            text="Sair do programa",
            command=self.fechar_aplicativo,
            bg=COR_BRASIL_AZUL,
            fg="white",
            activebackground=COR_PRIMARIA,
            activeforeground="white",
            font=FONTE_NORMAL,
            padx=14,
            pady=8,
            relief=tk.FLAT,
            cursor="hand2",
        ).pack(fill=tk.X, pady=(8, 0))
        self.root.after_idle(self.entry_usuario.focus_set)
        self.root.after_idle(self.aplicar_tema, self.root)

    def _focar_senha(self, event=None):
        self.entry_senha.focus_set()
        return "break"

    def _entrar_com_teclado(self, event=None):
        self.verificar_login()
        return "break"
        
    def verificar_login(self):
        usuario = self.entry_usuario.get().strip()
        senha = self.entry_senha.get()
        try:
            if db.autenticar(usuario, senha):
                self.usuario_logado = usuario
                self.funcao_usuario = db.obter_funcao()
                db.atualizar_acesso(usuario)
                if not funcao_somente_cadastro(
                    self.funcao_usuario, self.usuario_logado
                ):
                    self.registrar_acao(
                        "LOGIN", f"Usuário {usuario} entrou no sistema"
                    )
                self.tela_principal()
            else:
                messagebox.showerror("❌ Erro de Acesso", "Usuário ou senha incorretos!")
        except (ConnectionError, RuntimeError, sqlite3.Error) as erro:
            messagebox.showerror("Erro de conexão", str(erro))

    def sair(self):
        try:
            db.encerrar_sessao()
        except (ConnectionError, RuntimeError, sqlite3.Error) as erro:
            messagebox.showerror("Erro ao encerrar sessão", str(erro))
        finally:
            self.usuario_logado = None
            self.funcao_usuario = None
            self.tela_login()

    def tela_principal(self):
        self.limpar_tela()
        cor_fundo_painel = COR_FUNDO_PAINEL
        self.root.configure(bg=cor_fundo_painel)

        try:
            servidor_disponivel = db.verificar_conexao()
        except (ConnectionError, RuntimeError):
            servidor_disponivel = False
        status_servidor_texto = (
            "✅ Conectado ao servidor central"
            if servidor_disponivel
            else "⚠️ Servidor central indisponível"
        )
        status_servidor_cor = "#24734d" if servidor_disponivel else "#9a6500"
        status_servidor_fundo = "#e9f6ee" if servidor_disponivel else "#fff4df"

                # Barra Superior
        barra_superior = tk.Frame(self.root, bg=COR_BRASIL_VERDE_ESCURO, padx=20, pady=12, height=60)
        barra_superior.pack(fill=tk.X, side=tk.TOP)
        barra_superior.pack_propagate(False)

        tk.Label(barra_superior, text=f"👤  {self.usuario_logado}",
                 font=FONTE_SUBTITULO, fg="white", bg=COR_BRASIL_VERDE_ESCURO).pack(side=tk.LEFT)

        self.label_status_rede = tk.Label(
            barra_superior,
            text="Rede: verificando...",
            font=("Segoe UI", 8, "bold"),
            fg=COR_TEXTO_CLARO,
            bg=self._cor_tema("#fff4df", "background"),
            padx=7,
            pady=6,
        )
        self.label_status_rede.pack(side=tk.LEFT, padx=(12, 4))

        self.label_status_internet = tk.Label(
            barra_superior,
            text="Internet: verificando...",
            font=("Segoe UI", 8, "bold"),
            fg=COR_TEXTO_CLARO,
            bg=self._cor_tema("#fff4df", "background"),
            padx=7,
            pady=6,
        )
        self.label_status_internet.pack(side=tk.LEFT, padx=(4, 4))

        self.label_status = tk.Label(barra_superior, text=status_servidor_texto,
                                      font=("Segoe UI", 9, "bold"), fg=status_servidor_cor,
                                      bg=status_servidor_fundo, padx=12, pady=6)
        self.label_status.pack(side=tk.LEFT, padx=8)
        
        tk.Button(barra_superior, text="🚪 Sair", command=self.sair,
                 bg="#fff0ef", fg="#a33b36", activebackground="#ffe3e0",
                 activeforeground="#8f302b", font=FONTE_NORMAL, padx=16, pady=7,
                 relief=tk.FLAT, bd=0, cursor="hand2").pack(side=tk.RIGHT)
        tk.Button(
            barra_superior,
            text="Ativar modo claro" if self.modo_escuro else "Ativar modo escuro",
            command=self.alternar_modo_escuro,
            bg=COR_BRASIL_AZUL,
            fg="white",
            activebackground=COR_PRIMARIA,
            activeforeground="white",
            font=FONTE_NORMAL + ("bold",),
            padx=14,
            pady=7,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(0, 8))

        self.adicionar_faixa_cores(self.root)

        # Conteúdo Principal
        conteudo = tk.Frame(self.root, bg=cor_fundo_painel, padx=30, pady=30)
        conteudo.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            conteudo,
            text="CENTRAL DE CONTROLE  ·  CENTRO DE REABILITAÇÃO  ·  AÇAILÂNDIA",
            font=("Segoe UI", 9, "bold"),
            fg=COR_BRASIL_AZUL,
            bg=cor_fundo_painel,
        ).pack(pady=(12, 8))
        tk.Frame(conteudo, bg=cor_fundo_painel, height=26).pack()

        botoes_frame = tk.Frame(
            conteudo,
            bg=COR_CARTA,
            padx=16,
            pady=12,
            highlightbackground="#d8e6db",
            highlightthickness=1,
        )
        botoes_frame.pack(fill=tk.X, padx=145)

        botoes = [
            ("📝  Cadastrar paciente", self.tela_cadastro, COR_BRASIL_VERDE, "white", "#11783a"),
            ("📋  Ver pacientes", self.ver_dados_locais, COR_BRASIL_AZUL, "white", "#12558e"),
            ("📜  Histórico de alterações", self.ver_historico, COR_BRASIL_AMARELO, "white", "#f0b91e"),
        ]

        for i, (texto, comando, cor, cor_texto, cor_hover) in enumerate(botoes):
            btn = tk.Button(
                botoes_frame,
                text=f"{texto}    ›",
                command=comando,
                bg=cor,
                fg=cor_texto,
                activebackground=cor_hover,
                activeforeground=cor_texto,
                font=FONTE_SUBTITULO,
                anchor=tk.W,
                padx=20,
                pady=15,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
            )
            btn.pack(fill=tk.X, pady=5)
            btn.bind(
                "<Enter>",
                lambda event, botao=btn, fundo=cor_hover: botao.configure(
                    bg=self._cor_tema(fundo, "background")
                ),
            )
            btn.bind(
                "<Leave>",
                lambda event, botao=btn, fundo=cor: botao.configure(
                    bg=self._cor_tema(fundo, "background")
                ),
            )
        self.root.after_idle(self.aplicar_tema, self.root)

    def tela_atendimento(self):
        janela = tk.Toplevel(self.root)
        janela.after_idle(self.aplicar_tema, janela)
        janela.title("🏥 Registrar Atendimento")
        janela.geometry("620x420")
        janela.configure(bg=COR_FUNDO_PAINEL)
        self.adicionar_faixa_cores(janela)
        x = self.root.winfo_x() + 140
        y = self.root.winfo_y() + 60
        janela.geometry(f"+{x}+{y}")

        frame = tk.Frame(janela, bg=COR_CARTA, padx=25, pady=25,
                         highlightbackground="#d8e6db", highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        tk.Label(frame, text="🏥 Registro de Atendimento", font=FONTE_SUBTITULO,
                 fg=COR_BRASIL_VERDE_ESCURO, bg=COR_CARTA).pack(anchor=tk.W, pady=(0, 20))

        try:
            pacientes = db.listar_pacientes_atendimento()
        except (ConnectionError, RuntimeError, sqlite3.Error) as erro:
            janela.destroy()
            messagebox.showerror("Erro ao acessar o servidor", str(erro))
            return
        if not pacientes:
            tk.Label(frame, text="Nenhum paciente cadastrado. Cadastre um paciente antes de registrar atendimento.",
                     font=FONTE_NORMAL, fg=COR_TEXTO_CLARO, bg=COR_CARTA, justify=tk.LEFT, wraplength=500).pack(anchor=tk.W)
            tk.Button(frame, text="Fechar", command=janela.destroy, bg=COR_BRASIL_AZUL, fg="white",
                      font=FONTE_NORMAL, padx=10, pady=6, relief=tk.FLAT).pack(pady=(20, 0))
            return

        opcoes = [f"{nome} ({cartao_sus})" for _, nome, cartao_sus in pacientes]
        var_paciente = tk.StringVar()
        ttk.Combobox(frame, textvariable=var_paciente, values=opcoes, state="readonly", width=50).pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Tipo de atendimento:", font=FONTE_NORMAL, fg=COR_TEXTO, bg=COR_CARTA).pack(anchor=tk.W)
        var_tipo = tk.StringVar()
        entrada_tipo = ttk.Combobox(
            frame,
            textvariable=var_tipo,
            values=TIPOS_ATENDIMENTO,
            state="readonly",
        )
        entrada_tipo.pack(fill=tk.X, pady=(5, 20))

        def salvar_atendimento():
            valor_paciente = var_paciente.get()
            tipo = var_tipo.get().strip()
            if not valor_paciente or not tipo:
                messagebox.showwarning("⚠️ Dados incompletos", "Selecione o paciente e informe o tipo de atendimento.")
                return
            try:
                tipo = validar_tipo_atendimento(tipo)
            except ValueError as erro:
                messagebox.showwarning("Tipo de atendimento inválido", str(erro))
                return

            paciente_nome = valor_paciente.rsplit(" (", 1)[0]
            paciente_id = None
            for paciente in pacientes:
                if paciente[1] == paciente_nome:
                    paciente_id = paciente[0]
                    break

            if paciente_id is None:
                messagebox.showerror("❌ Paciente não encontrado", "Não foi possível localizar o paciente selecionado.")
                return

            try:
                db.registrar_atendimento(paciente_id, tipo, self.usuario_logado)
            except (ConnectionError, RuntimeError, sqlite3.Error) as erro:
                messagebox.showerror("Erro ao salvar atendimento", str(erro))
                return
            messagebox.showinfo(
                "✅ Atendimento registrado",
                "Atendimento salvo com sucesso no servidor central.",
            )
            janela.destroy()

        tk.Button(frame, text="Salvar Atendimento", command=salvar_atendimento,
                  bg=COR_BRASIL_VERDE, fg="white", font=FONTE_SUBTITULO,
                  padx=20, pady=10, relief=tk.FLAT, cursor="hand2").pack(fill=tk.X)

    def ver_dados_locais(self):
        somente_cadastro = funcao_somente_cadastro(
            self.funcao_usuario, self.usuario_logado or ""
        )
        janela = tk.Toplevel(self.root)
        janela.after_idle(self.aplicar_tema, janela)
        janela.title("📋 Pacientes cadastrados")
        janela.geometry("820x500")
        janela.configure(bg=COR_FUNDO_PAINEL)
        self.adicionar_faixa_cores(janela)

        frame = tk.Frame(janela, bg=COR_CARTA, padx=15, pady=15,
                         highlightbackground="#d8e6db", highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        tk.Label(frame, text="📋 Pacientes cadastrados", font=FONTE_SUBTITULO,
                 fg=COR_BRASIL_VERDE_ESCURO, bg=COR_CARTA).pack(anchor=tk.W)
        try:
            registros = db.listar_pacientes_para_exclusao()
        except (ConnectionError, RuntimeError, sqlite3.Error) as erro:
            janela.destroy()
            messagebox.showerror("Erro ao acessar o servidor", str(erro))
            return

        colunas = ("Nome", "CPF", "Cartão SUS", "Data do Cadastro")
        arvore = ttk.Treeview(
            frame,
            columns=colunas,
            show="headings",
            height=10,
            selectmode="none" if somente_cadastro else "extended",
        )
        for coluna in colunas:
            arvore.heading(coluna, text=coluna)
            arvore.column(coluna, width=180, anchor=tk.CENTER)

        aviso_vazio = tk.Label(
            frame,
            text="Nenhum paciente cadastrado até o momento.",
            font=FONTE_NORMAL,
            fg=COR_TEXTO_CLARO,
            bg=COR_CARTA,
        )
        if not registros:
            aviso_vazio.pack(anchor=tk.W, pady=15)
        arvore.pack(fill=tk.BOTH, expand=True)

        if not somente_cadastro:
            rotulo_selecao = tk.Label(
                frame,
                text="0 pacientes selecionados",
                font=FONTE_PEQUENA,
                fg=COR_TEXTO_CLARO,
                bg=COR_CARTA,
            )
            rotulo_selecao.pack(anchor=tk.W, pady=(4, 0))

        def atualizar_contagem_selecao(event=None):
            quantidade = len(arvore.selection())
            rotulo_selecao.config(
                text=f"{quantidade} paciente(s) selecionado(s)"
            )

        def selecionar_todos():
            arvore.selection_set(arvore.get_children())
            atualizar_contagem_selecao()

        def limpar_selecao():
            arvore.selection_remove(arvore.selection())
            atualizar_contagem_selecao()

        def alternar_selecao_clique(event):
            paciente_id = arvore.identify_row(event.y)
            if not paciente_id:
                return
            if paciente_id in arvore.selection():
                arvore.selection_remove(paciente_id)
            else:
                arvore.selection_add(paciente_id)
            arvore.focus(paciente_id)
            arvore.focus_set()
            atualizar_contagem_selecao()
            return "break"

        if not somente_cadastro:
            arvore.bind("<Button-1>", alternar_selecao_clique)
            arvore.bind("<<TreeviewSelect>>", atualizar_contagem_selecao)

        def atualizar_lista():
            try:
                registros_atualizados = db.listar_pacientes_para_exclusao()
            except (ConnectionError, RuntimeError, sqlite3.Error) as erro:
                messagebox.showerror(
                    "Erro ao atualizar pacientes", str(erro), parent=janela
                )
                return

            arvore.delete(*arvore.get_children())
            for paciente_id, nome, cpf, cartao_sus, data_cadastro in registros_atualizados:
                arvore.insert(
                    "",
                    tk.END,
                    iid=str(paciente_id),
                    values=(nome, exibir_cpf(cpf), cartao_sus, data_cadastro),
                )
            if registros_atualizados:
                aviso_vazio.pack_forget()
            else:
                aviso_vazio.pack(anchor=tk.W, pady=15)

        for paciente_id, nome, cpf, cartao_sus, data_cadastro in registros:
            arvore.insert(
                "",
                tk.END,
                iid=str(paciente_id),
                values=(nome, exibir_cpf(cpf), cartao_sus, data_cadastro),
            )

        def apagar_selecionados():
            selecionados = arvore.selection()
            if not selecionados:
                messagebox.showwarning(
                    "Nenhum paciente selecionado",
                    "Nenhum paciente foi selecionado.",
                    parent=janela,
                )
                return
            if not messagebox.askyesno(
                "Confirmar exclusão",
                f"Apagar {len(selecionados)} paciente(s) selecionado(s) "
                "e seus atendimentos? Esta ação não pode ser desfeita.",
                parent=janela,
            ):
                return
            try:
                quantidade = db.excluir_pacientes(
                    [int(paciente_id) for paciente_id in selecionados]
                )
            except (ConnectionError, RuntimeError, ValueError, sqlite3.Error) as erro:
                messagebox.showerror("Erro ao apagar pacientes", str(erro), parent=janela)
                return
            messagebox.showinfo(
                "Exclusão concluída",
                f"{quantidade} paciente(s) e seus atendimentos foram apagados.",
                parent=janela,
            )
            atualizar_lista()

        def apagar_todos():
            if not messagebox.askyesno(
                "Confirmar exclusão total",
                "Apagar todos os pacientes e atendimentos? "
                "Esta ação não pode ser desfeita.",
                parent=janela,
            ):
                return
            try:
                quantidade = db.excluir_todos_pacientes()
            except (ConnectionError, RuntimeError, sqlite3.Error) as erro:
                messagebox.showerror("Erro ao apagar pacientes", str(erro), parent=janela)
                return
            messagebox.showinfo(
                "Exclusão concluída",
                f"{quantidade} paciente(s) e seus atendimentos foram apagados.",
                parent=janela,
            )
            atualizar_lista()

        if not somente_cadastro:
            botoes = tk.Frame(frame, bg=COR_CARTA)
            botoes.pack(fill=tk.X, pady=(10, 0))
            tk.Button(
                botoes,
                text="Selecionar todos",
                command=selecionar_todos,
                bg=COR_BRASIL_AZUL,
                fg="white",
                font=FONTE_NORMAL,
                padx=12,
                pady=6,
                relief=tk.FLAT,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=(0, 8))
            tk.Button(
                botoes,
                text="Limpar seleção",
                command=limpar_selecao,
                bg=COR_BRASIL_VERDE,
                fg="white",
                font=FONTE_NORMAL,
                padx=12,
                pady=6,
                relief=tk.FLAT,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=(0, 8))
            tk.Button(
                botoes,
                text="Apagar pacientes selecionados",
                command=apagar_selecionados,
                bg=COR_BRASIL_AMARELO,
                fg=COR_TEXTO,
                font=FONTE_NORMAL,
                padx=12,
                pady=6,
                relief=tk.FLAT,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=(0, 8))
            tk.Button(
                botoes,
                text="Apagar todos",
                command=apagar_todos,
                bg=COR_ERRO,
                fg="white",
                font=FONTE_NORMAL,
                padx=12,
                pady=6,
                relief=tk.FLAT,
                cursor="hand2",
            ).pack(side=tk.LEFT)

    def ver_historico(self):
        janela = tk.Toplevel(self.root)
        janela.after_idle(self.aplicar_tema, janela)
        janela.title("📜 Histórico de Alterações")
        janela.geometry("900x520")
        janela.configure(bg=COR_FUNDO_PAINEL)
        self.adicionar_faixa_cores(janela)

        frame = tk.Frame(janela, bg=COR_CARTA, padx=15, pady=15,
                         highlightbackground="#d8e6db", highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        tk.Label(frame, text="📜 Histórico de atividades", font=FONTE_SUBTITULO,
                 fg=COR_BRASIL_VERDE_ESCURO, bg=COR_CARTA).pack(anchor=tk.W)

        def limpar_historico():
            if not messagebox.askyesno(
                "Apagar histórico",
                "Apagar todo o histórico de alterações?\nEsta ação não pode ser desfeita.",
                parent=janela,
            ):
                return
            try:
                quantidade = db.limpar_historico()
            except (ConnectionError, RuntimeError, sqlite3.Error) as erro:
                messagebox.showerror(
                    "Erro ao apagar histórico",
                    str(erro),
                    parent=janela,
                )
                return
            messagebox.showinfo(
                "Histórico apagado",
                f"{quantidade} registro(s) apagado(s).",
                parent=janela,
            )
            janela.destroy()
            self.ver_historico()

        if not funcao_somente_cadastro(
            self.funcao_usuario, self.usuario_logado or ""
        ):
            tk.Button(
                frame,
                text="🗑 Apagar histórico",
                command=limpar_historico,
                bg=COR_ERRO,
                fg="white",
                font=FONTE_NORMAL,
                padx=12,
                pady=6,
                relief=tk.FLAT,
                cursor="hand2",
            ).pack(anchor=tk.E, pady=(8, 8))

        try:
            registros = db.listar_historico()
        except (ConnectionError, RuntimeError, sqlite3.Error) as erro:
            janela.destroy()
            messagebox.showerror("Erro ao acessar o servidor", str(erro))
            return

        if not registros:
            tk.Label(frame, text="Nenhuma atividade registrada até o momento.",
                     font=FONTE_NORMAL, fg=COR_TEXTO_CLARO, bg=COR_CARTA).pack(anchor=tk.W, pady=15)
            return

        colunas = ("Usuário", "Ação", "Data/Hora", "Detalhes")
        arvore = ttk.Treeview(frame, columns=colunas, show="headings", height=18)
        for coluna in colunas:
            arvore.heading(coluna, text=coluna)
            arvore.column(coluna, width=200, anchor=tk.W)

        for usuario, acao, data_hora, detalhes in registros:
            arvore.insert("", tk.END, values=(usuario, acao, data_hora, detalhes or "-"))

        arvore.pack(fill=tk.BOTH, expand=True)

    def tela_cadastro(self):
        janela = tk.Toplevel(self.root)
        janela.after_idle(self.aplicar_tema, janela)
        janela.title("📝 Cadastro de Paciente")
        janela.geometry("650x600")
        janela.configure(bg=COR_FUNDO_PAINEL)
        self.adicionar_faixa_cores(janela)
        x = self.root.winfo_x() + 150
        y = self.root.winfo_y() + 50
        janela.geometry(f"+{x}+{y}")

        frame = tk.Frame(janela, bg=COR_CARTA, padx=30, pady=25,
                         highlightbackground="#d8e6db", highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="📝 Dados do Paciente", font=FONTE_SUBTITULO, 
                fg=COR_BRASIL_VERDE_ESCURO, bg=COR_CARTA).pack(anchor=tk.W, pady=(0, 20))

        campos = {}
        sem_acompanhante_var = tk.BooleanVar(value=False)
        labels = [
            ("RG:", "rg"),
            ("CPF:", "cpf"),
            ("Cartão SUS:", "cartao_sus"),
            ("Nome Completo:", "nome"),
            ("Data de Nascimento:", "data_nascimento"),
            ("Sexo:", "sexo"),
            ("Nome do Acompanhante/Responsável:", "acompanhante")
        ]

        for texto, chave in labels:
            linha = tk.Frame(frame, bg=COR_CARTA)
            linha.pack(fill=tk.X, pady=8)
            
            largura_rotulo = 34 if chave == "acompanhante" else 25
            tk.Label(linha, text=texto, font=FONTE_NORMAL, fg=COR_TEXTO, 
                    bg=COR_CARTA, width=largura_rotulo, anchor=tk.W).pack(side=tk.LEFT)
            
            if chave == "sexo":
                var_sexo = tk.StringVar()
                cbx = ttk.Combobox(linha, textvariable=var_sexo, 
                                   values=["Masculino", "Feminino", "Não Informado"], 
                                   state="readonly", width=35)
                cbx.pack(side=tk.LEFT, padx=5)
                campos[chave] = var_sexo
            else:
                opcoes_entrada = {}
                if chave == "rg":
                    validar_entrada = janela.register(
                        lambda valor: len(valor) <= 11
                        and all("0" <= char <= "9" for char in valor)
                    )
                    opcoes_entrada = {
                        "validate": "key",
                        "validatecommand": (validar_entrada, "%P"),
                    }
                elif chave == "cartao_sus":
                    validar_entrada = janela.register(
                        lambda valor: len(valor) <= 15
                        and all("0" <= char <= "9" for char in valor)
                    )
                    opcoes_entrada = {
                        "validate": "key",
                        "validatecommand": (validar_entrada, "%P"),
                    }
                elif chave in ("nome", "acompanhante"):
                    validar_entrada = janela.register(
                        lambda valor: len(valor) <= 200
                        and all(char == " " or char.isalpha() for char in valor)
                    )
                    opcoes_entrada = {
                        "validate": "key",
                        "validatecommand": (validar_entrada, "%P"),
                    }
                ent = tk.Entry(
                    linha,
                    font=FONTE_NORMAL,
                    bd=1,
                    relief=tk.SOLID,
                    **opcoes_entrada,
                )
                ent.pack(
                    side=tk.LEFT,
                    padx=5,
                    fill=tk.X,
                    expand=chave == "acompanhante",
                )
                if chave == "acompanhante":
                    def alternar_acompanhante(campo=ent):
                        if sem_acompanhante_var.get():
                            campo.delete(0, tk.END)
                            campo.configure(state=tk.DISABLED)
                        else:
                            campo.configure(state=tk.NORMAL)

                    tk.Checkbutton(
                        linha,
                        text="Não veio acompanhado",
                        variable=sem_acompanhante_var,
                        command=alternar_acompanhante,
                        font=FONTE_PEQUENA,
                        fg=COR_TEXTO,
                        bg=COR_CARTA,
                        activebackground=COR_CARTA,
                        activeforeground=COR_TEXTO,
                        selectcolor="#dceeff",
                    ).pack(side=tk.RIGHT, padx=5)
                if chave in ("nome", "acompanhante"):
                    ent.bind("<KeyRelease>", aplicar_nome_maiusculo_entrada)
                elif chave == "cpf":
                    ent.bind("<KeyRelease>", aplicar_mascara_cpf_entrada)
                elif chave == "data_nascimento":
                    ent.bind("<KeyPress-BackSpace>", apagar_barra_data_entrada)
                    ent.bind("<KeyRelease>", aplicar_mascara_data_entrada)
                campos[chave] = ent

        tk.Label(
            frame,
            text="Tipo de atendimento:",
            font=FONTE_NORMAL,
            fg=COR_TEXTO,
            bg=COR_CARTA,
        ).pack(anchor=tk.W, pady=(12, 4))
        var_tipo_atendimento = tk.StringVar()
        entrada_tipo_atendimento = ttk.Combobox(
            frame,
            textvariable=var_tipo_atendimento,
            values=TIPOS_ATENDIMENTO,
            state="readonly",
            style="CadastroAtendimento.TCombobox",
        )
        entrada_tipo_atendimento.pack(fill=tk.X)

        def salvar_paciente():
            rg = campos["rg"].get().strip() or None
            try:
                validar_documentos(rg)
            except ValueError as erro:
                messagebox.showwarning("Documento inválido", str(erro))
                return
            try:
                data_nascimento = validar_data_nascimento(
                    campos["data_nascimento"].get().strip()
                )
            except ValueError as erro:
                messagebox.showwarning("Data inválida", str(erro))
                return
            dados = [
                rg,
                None,
                campos["cpf"].get().strip() or None,
                campos["cartao_sus"].get().strip(),
                campos["nome"].get().strip(),
                data_nascimento,
                campos["sexo"].get().strip(),
                (
                    None
                    if sem_acompanhante_var.get()
                    else campos["acompanhante"].get().strip() or None
                ),
            ]
            if not all(dados[index] for index in (3, 4, 5, 6)):
                messagebox.showwarning(
                    "Dados incompletos",
                    "Preencha Cartão SUS, nome, data de nascimento e sexo.",
                )
                return
            try:
                dados[3] = validar_cartao_sus(dados[3])
            except ValueError as erro:
                messagebox.showwarning("Cartão SUS inválido", str(erro))
                return
            try:
                dados[4] = validar_nome(dados[4])
            except ValueError as erro:
                messagebox.showwarning("Nome inválido", str(erro))
                return
            if dados[7]:
                try:
                    dados[7] = validar_nome(dados[7])
                except ValueError as erro:
                    messagebox.showwarning(
                        "Acompanhante inválido",
                        "Nome do acompanhante/responsável deve conter somente letras.",
                    )
                    return
            tipo_atendimento = var_tipo_atendimento.get().strip()
            if not tipo_atendimento:
                messagebox.showwarning(
                    "Dados incompletos",
                    "Informe o tipo de atendimento.",
                )
                return
            tipo_atendimento = validar_tipo_atendimento(tipo_atendimento)
            try:
                db.cadastrar_paciente(
                    dados, self.usuario_logado, tipo_atendimento
                )
                if not funcao_somente_cadastro(
                    self.funcao_usuario, self.usuario_logado or ""
                ):
                    self.registrar_acao(
                        "CADASTRO", f"Paciente {dados[4]} cadastrado no sistema"
                    )
            except (ConnectionError, RuntimeError, sqlite3.Error) as erro:
                messagebox.showerror("Erro ao salvar paciente", str(erro))
                return
            messagebox.showinfo(
                "Cadastro concluído",
                "Paciente e atendimento adicionados ao sistema.",
            )
            janela.destroy()

        tk.Button(
            frame,
            text="Adicionar Paciente",
            command=salvar_paciente,
            bg=COR_BRASIL_VERDE,
            fg="white",
            font=FONTE_SUBTITULO,
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2",
        ).pack(fill=tk.X, pady=(12, 0))


def iniciar_servidor(certificado, chave):
    token = os.environ.get("SISTEMA_API_TOKEN", "")
    if len(token) < 32:
        raise SystemExit(
            "Defina SISTEMA_API_TOKEN com pelo menos 32 caracteres antes de iniciar o servidor."
        )
    ManipuladorAPI.banco = BancoLocal()
    if ManipuladorAPI.banco.senha_admin_padrao_em_uso():
        ManipuladorAPI.banco.conn.close()
        raise SystemExit(
            "O acesso inicial 1/1 ainda está ativo. "
            "Altere a senha com --alterar-senha-admin antes de iniciar o servidor na rede."
        )
    ManipuladorAPI.token = token
    servidor = http.server.ThreadingHTTPServer(("0.0.0.0", PORTA_SERVIDOR), ManipuladorAPI)
    servidor.daemon_threads = True
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.load_cert_chain(certfile=certificado, keyfile=chave)
    servidor.socket = contexto.wrap_socket(servidor.socket, server_side=True)
    print(f"Servidor central HTTPS ativo na porta {PORTA_SERVIDOR}.")
    print(f"Banco de dados: {ARQUIVO_BD_LOCAL}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        servidor.server_close()
        ManipuladorAPI.banco.conn.close()


def iniciar_aplicativo():
    url = os.environ.get("SISTEMA_SERVIDOR", "").strip()
    token = os.environ.get("SISTEMA_API_TOKEN", "")
    certificado_ca = os.environ.get("SISTEMA_CERTIFICADO_CA", "").strip()
    if not url.startswith("https://"):
        raise SystemExit("Defina SISTEMA_SERVIDOR com a URL HTTPS do PC da recepção.")
    if len(token) < 32:
        raise SystemExit("Defina SISTEMA_API_TOKEN com o token configurado no servidor.")
    if not certificado_ca or not os.path.isfile(certificado_ca):
        raise SystemExit(
            "Defina SISTEMA_CERTIFICADO_CA com o caminho do certificado confiável do servidor."
        )
    global db
    db = BancoCentral(url, token, certificado_ca)
    root = tk.Tk()
    SistemaApp(root)
    root.mainloop()


def preparar_arquivo_banco_local():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("Não foi possível localizar a pasta local de dados do Windows.")
    pasta_dados = os.path.join(local_app_data, "DolaCentroReabilitacao")
    os.makedirs(pasta_dados, exist_ok=True)
    caminho_local = os.path.join(pasta_dados, "servidor_local.db")
    if not os.path.exists(caminho_local) and os.path.isfile(ARQUIVO_BD_LOCAL):
        with sqlite3.connect(ARQUIVO_BD_LOCAL) as origem:
            with sqlite3.connect(caminho_local) as destino:
                origem.backup(destino)
    return caminho_local


def iniciar_aplicativo_local():
    global ARQUIVO_BD_LOCAL
    ARQUIVO_BD_LOCAL = preparar_arquivo_banco_local()
    root = tk.Tk()
    root.withdraw()
    banco_local = BancoLocal()
    servidor = None
    servidor_iniciado = False
    try:
        token = secrets.token_urlsafe(32)
        ManipuladorAPI.banco = banco_local
        ManipuladorAPI.token = token
        try:
            servidor = http.server.ThreadingHTTPServer(
                ("127.0.0.1", PORTA_SERVIDOR), ManipuladorAPI
            )
        except OSError as erro:
            messagebox.showerror(
                "Não foi possível iniciar",
                f"Não foi possível abrir a porta local {PORTA_SERVIDOR}: {erro}",
                parent=root,
            )
            root.destroy()
            return
        servidor.daemon_threads = True
        thread_servidor = threading.Thread(
            target=servidor.serve_forever,
            daemon=True,
        )
        thread_servidor.start()
        servidor_iniciado = True

        global db
        db = BancoCentral(f"http://127.0.0.1:{PORTA_SERVIDOR}", token)
        root.deiconify()
        SistemaApp(root)
        root.mainloop()
    finally:
        if servidor is not None:
            if servidor_iniciado:
                servidor.shutdown()
            servidor.server_close()
        banco_local.conn.close()


def alterar_senha_admin():
    banco = BancoLocal()
    if not banco.consultar("SELECT 1 FROM usuarios WHERE usuario = '1'"):
        banco.conn.close()
        raise SystemExit("O usuário 1 não existe neste banco de dados.")
    nova_senha = getpass.getpass("Nova senha do usuário 1 (mínimo 12 caracteres): ")
    confirmacao = getpass.getpass("Confirme a nova senha: ")
    if len(nova_senha) < 12:
        banco.conn.close()
        raise SystemExit("A senha precisa ter pelo menos 12 caracteres.")
    if nova_senha != confirmacao:
        banco.conn.close()
        raise SystemExit("As senhas não coincidem.")
    banco.alterar_senha_admin(nova_senha)
    banco.conn.close()
    print("Senha do usuário 1 alterada.")


def criar_usuario():
    banco = BancoLocal()
    usuario = input("Nome de usuário: ").strip()
    nome_completo = input("Nome completo: ").strip()
    funcao = input("Função: ").strip()
    senha = getpass.getpass("Senha (mínimo 12 caracteres): ")
    confirmacao = getpass.getpass("Confirme a senha: ")
    if not usuario or not nome_completo or not funcao:
        banco.conn.close()
        raise SystemExit("Usuário, nome completo e função são obrigatórios.")
    if len(senha) < 12:
        banco.conn.close()
        raise SystemExit("A senha precisa ter pelo menos 12 caracteres.")
    if senha != confirmacao:
        banco.conn.close()
        raise SystemExit("As senhas não coincidem.")
    try:
        banco.criar_usuario(usuario, senha, nome_completo, funcao)
    except sqlite3.IntegrityError as erro:
        banco.conn.close()
        raise SystemExit(f"Não foi possível criar o usuário: {erro}") from erro
    banco.conn.close()
    print(f"Usuário {usuario} criado.")


def alterar_status_usuario(usuario, ativo):
    banco = BancoLocal()
    try:
        banco.alterar_status_usuario(usuario, ativo)
    except ValueError as erro:
        raise SystemExit(str(erro)) from erro
    finally:
        banco.conn.close()
    estado = "ativado" if ativo else "desativado"
    print(f"Usuário {usuario} {estado}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--criar-usuario",
        action="store_true",
        help="Cria um usuário no banco central.",
    )
    parser.add_argument(
        "--alterar-senha-admin",
        action="store_true",
        help="Altera a senha do usuário admin no banco do PC central.",
    )
    parser.add_argument(
        "--desativar-usuario",
        metavar="USUARIO",
        help="Desativa a conta e bloqueia novos acessos.",
    )
    parser.add_argument(
        "--ativar-usuario",
        metavar="USUARIO",
        help="Reativa uma conta desativada.",
    )
    parser.add_argument(
        "--servidor",
        action="store_true",
        help="Inicia o servidor central HTTPS no PC da recepção.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Usa o banco local; sem outra opção, inicia o aplicativo neste computador.",
    )
    parser.add_argument("--certificado", help="Certificado TLS do servidor.")
    parser.add_argument("--chave", help="Chave privada TLS do servidor.")
    argumentos = parser.parse_args()

    if argumentos.criar_usuario:
        if argumentos.local:
            ARQUIVO_BD_LOCAL = preparar_arquivo_banco_local()
        criar_usuario()
    elif argumentos.alterar_senha_admin:
        if argumentos.local:
            ARQUIVO_BD_LOCAL = preparar_arquivo_banco_local()
        alterar_senha_admin()
    elif argumentos.desativar_usuario:
        if argumentos.local:
            ARQUIVO_BD_LOCAL = preparar_arquivo_banco_local()
        alterar_status_usuario(argumentos.desativar_usuario, False)
    elif argumentos.ativar_usuario:
        if argumentos.local:
            ARQUIVO_BD_LOCAL = preparar_arquivo_banco_local()
        alterar_status_usuario(argumentos.ativar_usuario, True)
    elif argumentos.servidor:
        if not argumentos.certificado or not argumentos.chave:
            parser.error("--servidor exige --certificado e --chave.")
        iniciar_servidor(argumentos.certificado, argumentos.chave)
    elif argumentos.local or not any(
        os.environ.get(nome)
        for nome in (
            "SISTEMA_SERVIDOR",
            "SISTEMA_API_TOKEN",
            "SISTEMA_CERTIFICADO_CA",
        )
    ):
        iniciar_aplicativo_local()
    else:
        iniciar_aplicativo()        