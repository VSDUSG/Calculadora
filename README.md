# 🩻 Daikon — Ultrassom, Agenda e Laudos

Sistema completo para clínica de ultrassonografia:

| O que faz | Como |
|---|---|
| 📅 **Agendamento de pacientes** na web, com preço do exame | Tela "Agenda" |
| 📡 **Worklist DICOM (MWL)** — os agendamentos aparecem na tela do seu ultrassom | Automático |
| 🖼️ **Recebe as imagens do ultrassom em tempo real** (DICOM C-STORE) | Automático |
| 📝 **Editor de laudos** com modelos prontos por tipo de exame | Tela "Exames" |
| 📄 **PDF do laudo** com cabeçalho da clínica, assinatura e imagens | Botão "Gerar PDF" |
| 📋 Cadastro de **médicos, procedimentos (com preço) e pacientes** | Tela "Cadastros" |
| 💰 Controle de **faturamento do dia** e pagamentos | Tela "Início" |
| 📱 **Funciona no celular e no computador** — pode ser instalado como aplicativo (PWA) | Qualquer navegador |

---

## 1. Como instalar (uma vez só)

Você precisa de um computador (Windows, Mac ou Linux) **na mesma rede do
aparelho de ultrassom**. Pode ser o mesmo computador da recepção.

1. Instale o **Python 3.10 ou mais novo**: https://www.python.org/downloads/
   (no Windows, marque a caixinha **"Add Python to PATH"** na instalação)
2. Baixe esta pasta do projeto para o computador
3. Abra o terminal (no Windows: Prompt de Comando) dentro da pasta e digite:

```bash
pip install -r requirements.txt
```

## 2. Como ligar o sistema

```bash
python run.py
```

Vai aparecer algo assim:

```
  Daikon iniciado!
  Site/aplicativo : http://localhost:8000
  Servidor DICOM  : AE Title 'DAIKON'  porta 11112
  Senha inicial   : daikon
```

- No **computador**: abra http://localhost:8000 no navegador
- No **celular** (na mesma rede Wi-Fi): abra `http://IP-DO-COMPUTADOR:8000`
  (ex.: `http://192.168.0.10:8000`) e use o menu do navegador →
  **"Adicionar à tela inicial"** para virar um aplicativo
- Senha inicial: **daikon** (troque na tela "Ajustes")

> 💡 Para descobrir o IP do computador: no Windows digite `ipconfig` no
> Prompt de Comando e procure "Endereço IPv4".

## 3. Como configurar o seu aparelho de ultrassom

No menu de configuração DICOM do aparelho (geralmente em
*Setup / Connectivity / DICOM*), crie **dois serviços** apontando para o
computador do Daikon:

### a) Armazenamento de imagens (Storage / Image Store)
| Campo | Valor |
|---|---|
| IP / Host | IP do computador do Daikon (ex.: 192.168.0.10) |
| AE Title remoto | `DAIKON` |
| Porta | `11112` |

### b) Worklist (MWL / Modality Worklist)
| Campo | Valor |
|---|---|
| IP / Host | o mesmo IP |
| AE Title remoto | `DAIKON` |
| Porta | `11112` |

Use o botão **"Verify" / "Ping DICOM" / "Echo"** do aparelho para testar —
deve dar sucesso (o Daikon responde C-ECHO).

## 4. Fluxo de trabalho do dia a dia

1. **Agende** o paciente na tela *Agenda* (na web ou no celular) —
   escolha o procedimento e o preço já vem preenchido
2. No **ultrassom**, aperte o botão de *Worklist* → o paciente agendado
   aparece na lista → selecione e faça o exame
3. As **imagens chegam sozinhas** na tela *Exames*, em tempo real
4. Toque no exame, **escolha as imagens** que entram no laudo, **digite o
   laudo** (ou use um modelo pronto) e clique em **Gerar PDF**
5. O agendamento muda sozinho para "realizado" e entra no faturamento do dia

## 5. Modelos de laudo

Em *Cadastros → Procedimentos*, cada exame pode ter um **modelo de laudo**
(texto pré-pronto). Ao laudar, é só escolher o modelo e ajustar o que for
diferente — igual aos sistemas de telemedicina.

## 6. Onde ficam os dados

Tudo fica na pasta `storage/` ao lado do programa:

- `storage/daikon.db` — banco de dados (agenda, pacientes, laudos…)
- `storage/dicom/` — imagens DICOM originais recebidas do aparelho
- `storage/png/` — imagens convertidas para visualização
- `storage/laudos/` — PDFs gerados

> ⚠️ **Faça backup da pasta `storage/` regularmente** — são os dados dos
> seus pacientes.

## 7. Perguntas frequentes

**O ultrassom não acha a Worklist.** Confira se o computador e o aparelho
estão na mesma rede, se o firewall do Windows liberou a porta 11112
("Permitir acesso" na primeira execução) e se o IP digitado no aparelho é
o IP atual do computador.

**As imagens não aparecem.** Verifique a configuração de *Storage* do
aparelho (item 3a) e se há um destino de envio automático configurado
(em muitos aparelhos: *Auto-transfer / Send after exam*).

**Quero mudar a porta ou o AE Title.** Tela *Ajustes* no sistema, depois
reinicie o Daikon (feche e rode `python run.py` de novo).

**Esqueci a senha.** Abra o arquivo `config.json` no Bloco de Notas e veja
o campo `"senha"`.
