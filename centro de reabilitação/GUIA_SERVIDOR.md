# Configuração do servidor central

O computador da recepção mantém o arquivo `servidor_local.db` e precisa ficar
ligado enquanto os outros computadores usam o sistema. Os clientes se conectam
ao servidor pela rede local; não compartilhe o arquivo SQLite pelo OneDrive ou
por uma pasta de rede.

## Requisitos

- Python instalado em todos os computadores.
- Computadores conectados à mesma rede local.
- Um certificado TLS e a chave privada correspondentes, emitidos para o nome
  ou endereço IP fixo do computador da recepção.
- O certificado da autoridade que emitiu o certificado TLS disponível nos
  computadores clientes.

Não exponha a porta do sistema à internet. Como o banco contém dados pessoais e
de saúde, mantenha o servidor na rede privada e use apenas certificados
confiáveis. O nome/IP usado em `SISTEMA_SERVIDOR` deve constar no certificado.

## Uso em um único computador

Para usar o sistema somente neste computador, execute:

```powershell
python .\sistema_reabilitacao.py --local
```

No modo local, entre com o usuário `1` e a senha `1`. Não é necessário configurar
token ou certificados. O servidor local aceita conexões somente do próprio
computador e é encerrado ao fechar o aplicativo. Se as variáveis de configuração
de cliente não estiverem definidas, iniciar o programa sem opções também abre
esse modo local.

Nesse modo, o banco fica em `%LOCALAPPDATA%\DolaCentroReabilitacao`. Se houver
um banco ao lado do programa e ainda não existir um banco local, ele será copiado
para essa pasta; o arquivo original não é removido.

Para criar uma conta que funcione nesse modo, use:

```powershell
python .\sistema_reabilitacao.py --criar-usuario --local
```

Para desativar uma conta ou reativá-la, use o nome do usuário:

```powershell
python .\sistema_reabilitacao.py --desativar-usuario NOME_DO_USUARIO --local
python .\sistema_reabilitacao.py --ativar-usuario NOME_DO_USUARIO --local
```

O argumento `--local` também pode ser combinado com `--alterar-senha-admin`
para alterar a senha no banco local.

## Preparar o computador da recepção

Abra o PowerShell na pasta do programa. Primeiro, troque a senha inicial `1` (faça isso somente no computador que
manterá o banco):

```powershell
python .\sistema_reabilitacao.py --alterar-senha-admin
```

O sistema exige uma senha com pelo menos 12 caracteres e não inicia o servidor
enquanto a senha conhecida `1` do usuário `1` estiver ativa. A combinação `1`/`1`
é fraca e deve ser usada apenas no modo local, não no servidor da rede.

Crie uma conta individual para cada profissional no computador da recepção:

```powershell
python .\sistema_reabilitacao.py --criar-usuario
```

Para desativar ou reativar uma conta no banco central, execute no computador
que hospeda esse banco:

```powershell
python .\sistema_reabilitacao.py --desativar-usuario NOME_DO_USUARIO
python .\sistema_reabilitacao.py --ativar-usuario NOME_DO_USUARIO
```

As senhas são armazenadas com PBKDF2; senhas antigas são atualizadas ao entrar
com sucesso. Evite compartilhar a conta de administrador.

Gere um token aleatório para autenticar os computadores clientes e mantenha-o
em local seguro:

```powershell
$bytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$env:SISTEMA_API_TOKEN = [BitConverter]::ToString($bytes).Replace('-', '')
```

Configure uma regra de entrada no Firewall do Windows para TCP 8765, somente
no perfil de rede privada. Em um PowerShell executado como administrador:

```powershell
New-NetFirewallRule -DisplayName "Sistema reabilitacao" `
  -Direction Inbound -Protocol TCP -LocalPort 8765 `
  -Action Allow -Profile Private
```

Inicie o servidor com os caminhos do certificado e da chave privada:

```powershell
python .\sistema_reabilitacao.py --servidor `
  --certificado "C:\caminho\servidor.crt" `
  --chave "C:\caminho\servidor.key"
```

Deixe essa janela do PowerShell aberta. O banco ficará junto ao arquivo Python.

## Testar pelo celular

Com o servidor ativo, conecte o celular à mesma rede Wi-Fi e abra no navegador:

```text
https://IP-DO-PC-DA-RECEPCAO:8765/
```

Por exemplo, substitua `IP-DO-PC-DA-RECEPCAO` pelo IP reservado do computador
da recepção. O certificado HTTPS precisa ser confiável pelo celular e incluir
esse IP ou nome; se o navegador mostrar aviso de certificado, não prossiga até
corrigir a configuração do certificado. A porta 8765 deve estar liberada no
Firewall somente para a rede privada.

Entre com a conta individual criada no servidor. No navegador do celular não é
necessário configurar `SISTEMA_API_TOKEN`; essa chave é apenas para os clientes
da aplicação desktop. Para testar, use informações fictícias, não dados reais
de pacientes.

## Preparar cada computador cliente

Abra o PowerShell na pasta do programa e configure o endereço do servidor
(substitua o IP pelo endereço fixo/reservado do computador da recepção), o
mesmo token criado no servidor e o caminho do certificado da autoridade
confiável:

```powershell
$env:SISTEMA_SERVIDOR = "https://192.168.1.10:8765"
$env:SISTEMA_API_TOKEN = "COLE_AQUI_O_TOKEN_DO_SERVIDOR"
$env:SISTEMA_CERTIFICADO_CA = "C:\caminho\autoridade.crt"
python .\sistema_reabilitacao.py
```

Cada novo terminal precisa receber essas três variáveis novamente. Distribua o
token e os certificados por um canal seguro; não os grave no código-fonte.
Quando o servidor estiver desligado ou inacessível, os clientes não poderão
consultar nem gravar dados.

Na tela principal, os indicadores de rede e internet são separados do status do
servidor central e são atualizados aproximadamente a cada cinco segundos. A
verificação de internet consulta o teste de conectividade da Microsoft; redes
que bloqueiem esse endereço podem aparecer como sem internet.

## Cópias de segurança

Faça cópias regulares de `servidor_local.db` em um local protegido. Para reduzir
o risco de uma cópia inconsistente, feche o servidor antes de copiar o arquivo.
