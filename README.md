# 🩻 Daikon — Ultrassom, Agenda e Laudos (na internet)

Sistema completo para clínica de ultrassonografia, acessível **de qualquer
lugar, a qualquer hora**, pelo computador ou pelo celular:

| O que faz | Onde |
|---|---|
| 📅 **Agendamento de pacientes** com preço do exame | Tela "Agenda" |
| 📡 **Worklist** — os agendamentos aparecem na tela do seu ultrassom | Automático |
| 🖼️ **Imagens do ultrassom chegam em tempo real** no site | Tela "Exames" |
| 📝 **Editor de laudos** com modelos prontos por tipo de exame | Tela "Exames" |
| 📄 **PDF do laudo** com cabeçalho da clínica, assinatura e imagens | Botão "Gerar PDF" |
| 📋 Cadastro de **médicos, procedimentos (com preço) e pacientes** | Tela "Cadastros" |
| 💰 **Faturamento do dia** e controle de pagamentos | Tela "Início" |
| 📱 Instala como **aplicativo no celular** (PWA) | Qualquer navegador |

## Como funciona (visão geral)

O aparelho de ultrassom fala um protocolo antigo (DICOM) que só funciona em
rede local — ele não consegue falar direto com um site. Por isso o Daikon
tem duas partes:

```
┌─────────────── NA CLÍNICA ───────────────┐      ┌───── NA INTERNET ─────┐
│                                          │      │                       │
│  Ultrassom ──DICOM──► Conector (1 PC)  ──┼HTTPS─┼──►  Site Daikon       │
│              (worklist e imagens)        │      │   (agenda, exames,    │
│                                          │      │    laudos, PDF)       │
└──────────────────────────────────────────┘      └───────────────────────┘
                                                     ▲
                                you, de qualquer lugar ┘ (celular ou computador)
```

- **Site Daikon** (`run.py`): fica hospedado na nuvem. É onde você agenda,
  vê os exames e digita os laudos — de onde estiver.
- **Conector** (`conector_clinica.py`): um programinha que fica ligado em
  um computador da clínica. Ele entrega a worklist ao ultrassom e manda as
  imagens para o site. Se a internet da clínica cair durante um exame, ele
  guarda as imagens e reenvia sozinho quando a conexão voltar.

---

## Parte 1 — Colocar o site na internet (Render.com)

O projeto já vem pronto para o [Render](https://render.com) (hospedagem
com HTTPS automático). Custo aproximado: plano *Starter* + disco
(~US$ 7–10/mês). Passos:

1. Crie uma conta em https://render.com (pode entrar com a conta do GitHub)
2. No painel do Render: **New +** → **Blueprint**
3. Conecte a sua conta do GitHub e escolha **este repositório**
4. O Render lê o arquivo `render.yaml` e já monta tudo (programa + disco
   para guardar as imagens). Confirme com **Apply**
5. Em alguns minutos o site fica no ar num endereço tipo
   `https://daikon.onrender.com`
6. Entre no site com a senha inicial **daikon** e **troque a senha** na
   tela *Ajustes*

> Outras opções que também funcionam: Railway, Fly.io ou qualquer servidor
> VPS com Docker (o projeto inclui um `Dockerfile`). Em um VPS:
> `docker build -t daikon . && docker run -p 80:8000 -v /dados:/dados daikon`

> ⚠️ **Importante:** as imagens dos exames ficam no disco do servidor
> (pasta `/dados`). Configure backup no painel da hospedagem.

## Parte 2 — Instalar o Conector no PC da clínica

Em **um** computador da clínica (pode ser o da recepção), na mesma rede do
ultrassom:

1. Instale o **Python 3.10+**: https://www.python.org/downloads/
   (no Windows, marque **"Add Python to PATH"**)
2. Copie para o computador os arquivos `conector_clinica.py` e abra o
   Prompt de Comando na pasta:

```bash
pip install pydicom pynetdicom requests
python conector_clinica.py
```

3. Na primeira execução ele pergunta:
   - **Endereço do site**: o endereço do Render (ex.: `https://daikon.onrender.com`)
   - **Token do conector**: aparece na tela *Ajustes* do site (toque para copiar)
4. Deixe a janela aberta (ou configure para iniciar com o Windows —
   coloque um atalho na pasta *Inicializar*)

## Parte 3 — Configurar o aparelho de ultrassom

No menu DICOM do aparelho (*Setup / Connectivity / DICOM*), crie **dois
serviços** apontando para o computador onde o Conector roda:

| Campo | Storage (imagens) | Worklist (MWL) |
|---|---|---|
| IP / Host | IP do PC do Conector (ex.: 192.168.0.10) | o mesmo IP |
| AE Title remoto | `DAIKON` | `DAIKON` |
| Porta | `11112` | `11112` |

Use o botão **"Verify" / "Echo"** do aparelho para testar — deve dar
sucesso. Se não der, libere a porta 11112 no firewall do Windows.

## O dia a dia

1. **Agende** o paciente no site (de onde você estiver) — o preço vem do
   procedimento cadastrado
2. No **ultrassom**, aperte *Worklist* → o paciente aparece → faça o exame
3. As **imagens chegam sozinhas** na tela *Exames* do site, em tempo real
4. No site ou no celular: escolha as imagens, **digite o laudo** (ou use um
   modelo pronto) e clique em **Gerar PDF**
5. O agendamento vira "realizado" e entra no faturamento do dia

## Aplicativo no celular

Abra o endereço do site no celular → menu do navegador →
**"Adicionar à tela inicial"**. Pronto: vira um aplicativo com ícone,
tela cheia e tudo.

## Modelos de laudo

Em *Cadastros → Procedimentos*, cada exame pode ter um **modelo de laudo**
(texto pré-pronto). Ao laudar, escolha o modelo e ajuste só o que for
diferente.

## Uso em rede local (sem internet)

O Daikon também funciona 100% dentro da clínica, sem nuvem: instale as
dependências (`pip install -r requirements.txt`) e rode `python run.py`
num PC da rede — nesse modo o próprio site recebe o DICOM do aparelho,
sem precisar do Conector.

## Perguntas frequentes

**O ultrassom não acha a Worklist.** Confira se o Conector está rodando
(janela aberta), se o IP digitado no aparelho é o IP atual do PC do
Conector e se o firewall liberou a porta 11112.

**As imagens não aparecem no site.** Olhe a janela do Conector: ela mostra
cada imagem recebida e enviada. "Sem internet agora — imagem guardada na
fila" significa que ele reenvia sozinho quando a internet voltar.

**Esqueci a senha do site.** No painel da hospedagem, abra o arquivo
`/dados/config.json` (Shell do Render) e veja o campo `"senha"`.

**Quero trocar o token do conector.** Apague o campo `"token_conector"` do
`/dados/config.json`, reinicie o site (um novo token é gerado) e atualize o
`conector.json` na clínica.
