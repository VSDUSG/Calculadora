/* ===== Daikon — interface web/celular ===== */
"use strict";

const $ = (s) => document.querySelector(s);
const conteudo = () => $("#conteudo");
let cacheMedicos = [], cacheProcedimentos = [];
let timerExames = null, ultimoTotalEstudos = -1;

/* ---------------- utilidades ---------------- */
async function api(caminho, metodo = "GET", corpo = null) {
  const opcoes = { method: metodo, headers: {} };
  if (corpo) {
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo);
  }
  const r = await fetch(caminho, opcoes);
  if (r.status === 401) { mostrarLogin(); throw new Error("login"); }
  if (!r.ok) {
    let msg = "Erro no servidor";
    try { msg = (await r.json()).detail || msg; } catch (e) {}
    avisar(msg);
    throw new Error(msg);
  }
  return r.json();
}

function avisar(texto) {
  const el = $("#aviso");
  el.textContent = texto;
  el.classList.remove("oculto");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("oculto"), 2800);
}

function esc(t) {
  return String(t ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function dataBR(iso) {
  if (!iso) return "";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

function dinheiro(v) {
  return (v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function hoje() { return new Date().toISOString().slice(0, 10); }

function abrirModal(html) {
  $("#modal").innerHTML = html;
  $("#modal-fundo").classList.remove("oculto");
}
function fecharModal() { $("#modal-fundo").classList.add("oculto"); }

/* ---------------- login ---------------- */
function mostrarLogin() {
  $("#tela-login").classList.remove("oculto");
  $("#app").classList.add("oculto");
}

async function fazerLogin() {
  const senha = $("#login-senha").value;
  try {
    const r = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ senha }),
    });
    if (!r.ok) { $("#login-erro").textContent = "Senha incorreta"; return; }
    $("#tela-login").classList.add("oculto");
    $("#app").classList.remove("oculto");
    iniciarApp();
  } catch (e) {
    $("#login-erro").textContent = "Não foi possível conectar";
  }
}

/* ---------------- navegação ---------------- */
const telas = { inicio: telaInicio, agenda: telaAgenda, exames: telaExames,
                cadastros: telaCadastros, config: telaConfig };

function navegar() {
  clearInterval(timerExames);
  const hash = location.hash.replace("#", "") || "inicio";
  const [nome, parametro] = hash.split("/");
  document.querySelectorAll("[data-tela]").forEach((a) =>
    a.classList.toggle("ativa", a.dataset.tela === nome));
  if (nome === "exame" && parametro) { telaLaudo(parseInt(parametro)); return; }
  (telas[nome] || telaInicio)();
}

async function iniciarApp() {
  try {
    const cfg = await api("/api/config");
    $("#nome-clinica-topo").textContent = cfg.nome_clinica || "Daikon";
  } catch (e) { return; }
  [cacheMedicos, cacheProcedimentos] = await Promise.all([
    api("/api/medicos"), api("/api/procedimentos")]);
  navegar();
}

/* ================= TELA: INÍCIO ================= */
async function telaInicio() {
  const r = await api("/api/resumo");
  conteudo().innerHTML = `
    <h2 class="titulo">Hoje, ${dataBR(r.data)}</h2>
    <div class="grade-numeros">
      <div class="numero-cartao"><b>${r.agendados}</b><span>Agendados</span></div>
      <div class="numero-cartao"><b>${r.realizados}</b><span>Realizados</span></div>
      <div class="numero-cartao"><b>${r.exames_recebidos}</b><span>Exames recebidos</span></div>
      <div class="numero-cartao"><b>${r.laudos_pendentes}</b><span>Laudos pendentes</span></div>
      <div class="numero-cartao"><b>${dinheiro(r.faturamento)}</b><span>Faturamento do dia</span></div>
      <div class="numero-cartao"><b>${dinheiro(r.recebido)}</b><span>Já recebido</span></div>
    </div>
    <div class="cartao" style="margin-top:14px">
      <b>Atalhos</b><br><br>
      <button class="btn primario" onclick="location.hash='agenda'">📅 Ver agenda</button>
      <button class="btn" onclick="modalAgendamento()">➕ Novo agendamento</button>
      <button class="btn" onclick="location.hash='exames'">🖼️ Exames recebidos</button>
    </div>`;
}

/* ================= TELA: AGENDA ================= */
async function telaAgenda(data) {
  data = data || sessionStorage.getItem("agenda_data") || hoje();
  sessionStorage.setItem("agenda_data", data);
  const ags = await api(`/api/agendamentos?data=${data}`);
  const itens = ags.map((a) => `
    <div class="item-agenda" onclick="modalAgendamento(${a.id})">
      <div class="hora">${esc(a.hora)}</div>
      <div class="meio">
        <b>${esc(a.paciente_nome)}</b>
        <small>${esc(a.procedimento_nome || "Sem procedimento")} · ${esc(a.medico_nome || "")}</small>
      </div>
      <div class="fim">
        <span class="preco">${dinheiro(a.preco)}</span>
        <span class="etiqueta ${a.status}">${esc(a.status)}</span>
        ${a.pago ? '<span class="etiqueta pago">pago</span>' : ""}
      </div>
    </div>`).join("");
  conteudo().innerHTML = `
    <h2 class="titulo">Agenda
      <button class="btn primario pequeno" onclick="modalAgendamento()">➕ Agendar</button>
    </h2>
    <div class="cartao" style="display:flex;gap:8px;align-items:center">
      <button class="btn pequeno" onclick="mudarDia(-1)">◀</button>
      <input type="date" id="agenda-data" value="${data}"
             onchange="telaAgenda(this.value)" style="flex:1">
      <button class="btn pequeno" onclick="mudarDia(1)">▶</button>
    </div>
    ${itens || `<div class="vazio"><span class="icone">📅</span>Nenhum agendamento para ${dataBR(data)}</div>`}`;

  window._agendamentosDia = ags;
}

function mudarDia(passo) {
  const d = new Date($("#agenda-data").value + "T12:00:00");
  d.setDate(d.getDate() + passo);
  telaAgenda(d.toISOString().slice(0, 10));
}

async function modalAgendamento(id) {
  const ag = id ? (window._agendamentosDia || []).find((a) => a.id === id) : null;
  const opMedicos = cacheMedicos.map((m) =>
    `<option value="${m.id}" ${ag && ag.medico_id === m.id ? "selected" : ""}>${esc(m.nome)}</option>`).join("");
  const opProc = cacheProcedimentos.map((p) =>
    `<option value="${p.id}" data-preco="${p.preco}" ${ag && ag.procedimento_id === p.id ? "selected" : ""}>${esc(p.nome)} — ${dinheiro(p.preco)}</option>`).join("");

  abrirModal(`
    <h3>${ag ? "Editar agendamento" : "Novo agendamento"}</h3>
    ${ag ? "" : `
      <label>Paciente</label>
      <input id="ag-busca" placeholder="Digite o nome para buscar…"
             oninput="buscarPaciente(this.value)" autocomplete="off">
      <div id="ag-resultados"></div>
      <input type="hidden" id="ag-paciente-id">
      <div id="ag-novo-paciente" class="oculto">
        <label>Nascimento</label><input type="date" id="ag-nasc">
        <div class="linha-form">
          <div><label>Sexo</label>
            <select id="ag-sexo"><option value="F">Feminino</option>
              <option value="M">Masculino</option><option value="O">Outro</option></select></div>
          <div><label>Telefone</label><input id="ag-tel" placeholder="(00) 00000-0000"></div>
        </div>
      </div>`}
    ${ag ? `<p><b>${esc(ag.paciente_nome)}</b></p>` : ""}
    <div class="linha-form">
      <div><label>Data</label><input type="date" id="ag-data"
        value="${ag ? ag.data : sessionStorage.getItem("agenda_data") || hoje()}"></div>
      <div><label>Hora</label><input type="time" id="ag-hora" value="${ag ? ag.hora : "08:00"}"></div>
    </div>
    <label>Procedimento</label>
    <select id="ag-proc" onchange="precoDoProcedimento()">
      <option value="">— escolher —</option>${opProc}</select>
    <label>Médico</label>
    <select id="ag-medico"><option value="">— escolher —</option>${opMedicos}</select>
    <div class="linha-form">
      <div><label>Preço (R$)</label>
        <input type="number" step="0.01" id="ag-preco" value="${ag ? ag.preco : ""}"></div>
      <div><label>Pago?</label>
        <select id="ag-pago"><option value="0">Não</option>
          <option value="1" ${ag && ag.pago ? "selected" : ""}>Sim</option></select></div>
    </div>
    <label>Observações</label>
    <input id="ag-obs" value="${ag ? esc(ag.observacoes) : ""}">
    <div class="acoes">
      ${ag ? `<button class="btn perigo" onclick="cancelarAgendamento(${ag.id})">Cancelar exame</button>` : ""}
      <button class="btn" onclick="fecharModal()">Fechar</button>
      <button class="btn primario" onclick="salvarAgendamento(${ag ? ag.id : "null"})">Salvar</button>
    </div>`);
}

function precoDoProcedimento() {
  const op = $("#ag-proc").selectedOptions[0];
  if (op && op.dataset.preco !== undefined) $("#ag-preco").value = op.dataset.preco;
}

let timerBusca = null;
function buscarPaciente(texto) {
  clearTimeout(timerBusca);
  $("#ag-paciente-id").value = "";
  timerBusca = setTimeout(async () => {
    if (!texto.trim()) { $("#ag-resultados").innerHTML = ""; return; }
    const lista = await api(`/api/pacientes?busca=${encodeURIComponent(texto)}`);
    $("#ag-resultados").innerHTML = lista.map((p) => `
      <div class="linha-lista" style="cursor:pointer"
           onclick="escolherPaciente(${p.id}, '${esc(p.nome).replace(/'/g, "\\'")}')">
        <div>${esc(p.nome)}<small>${dataBR(p.nascimento)}</small></div><div>✔️</div>
      </div>`).join("") +
      `<div class="linha-lista" style="cursor:pointer" onclick="novoPacienteNoModal()">
        <div><b>➕ Cadastrar “${esc(texto)}” como novo paciente</b></div></div>`;
  }, 250);
}

function escolherPaciente(id, nome) {
  $("#ag-paciente-id").value = id;
  $("#ag-busca").value = nome;
  $("#ag-resultados").innerHTML = "";
  $("#ag-novo-paciente").classList.add("oculto");
}

function novoPacienteNoModal() {
  $("#ag-paciente-id").value = "";
  $("#ag-resultados").innerHTML = "";
  $("#ag-novo-paciente").classList.remove("oculto");
}

async function salvarAgendamento(id) {
  const corpo = {
    data: $("#ag-data").value, hora: $("#ag-hora").value,
    procedimento_id: $("#ag-proc").value || null,
    medico_id: $("#ag-medico").value || null,
    preco: $("#ag-preco").value, pago: $("#ag-pago").value,
    observacoes: $("#ag-obs").value,
  };
  if (id) {
    const ag = (window._agendamentosDia || []).find((a) => a.id === id);
    corpo.status = ag ? ag.status : "agendado";
    await api(`/api/agendamentos/${id}`, "PUT", corpo);
  } else {
    let pacienteId = $("#ag-paciente-id").value;
    if (!pacienteId) {
      const nome = $("#ag-busca").value.trim();
      if (!nome) { avisar("Informe o paciente"); return; }
      const novo = await api("/api/pacientes", "POST", {
        nome, nascimento: $("#ag-nasc") ? $("#ag-nasc").value : "",
        sexo: $("#ag-sexo") ? $("#ag-sexo").value : "O",
        telefone: $("#ag-tel") ? $("#ag-tel").value : "",
      });
      pacienteId = novo.id;
    }
    corpo.paciente_id = pacienteId;
    await api("/api/agendamentos", "POST", corpo);
  }
  fecharModal();
  avisar("Agendamento salvo! Ele já aparece na Worklist do ultrassom.");
  telaAgenda($("#ag-data") ? $("#ag-data").value : undefined);
}

async function cancelarAgendamento(id) {
  if (!confirm("Cancelar este agendamento?")) return;
  await api(`/api/agendamentos/${id}`, "DELETE");
  fecharModal();
  telaAgenda();
}

/* ================= TELA: EXAMES ================= */
async function telaExames() {
  await desenharExames();
  // tempo real: atualiza a lista a cada 5 segundos
  timerExames = setInterval(async () => {
    if (location.hash.replace("#", "").split("/")[0] === "exames") {
      await desenharExames(true);
    } else clearInterval(timerExames);
  }, 5000);
}

async function desenharExames(silencioso) {
  const estudos = await api("/api/estudos");
  if (silencioso && estudos.length === ultimoTotalEstudos) return;
  if (silencioso && ultimoTotalEstudos >= 0 && estudos.length > ultimoTotalEstudos)
    avisar("📡 Novo exame recebido do ultrassom!");
  ultimoTotalEstudos = estudos.length;

  const cartoes = estudos.map((e) => {
    const nome = e.paciente_cadastro || e.paciente_nome || "Paciente sem nome";
    const capa = e.capa_id
      ? `<img class="capa" src="/arquivos/imagem/${e.capa_id}" loading="lazy">`
      : `<div class="sem-capa">🩻</div>`;
    const laudo = e.laudo_status === 1
      ? '<span class="etiqueta realizado">laudo pronto</span>'
      : e.laudo_status === 0
        ? '<span class="etiqueta pendente">laudo em edição</span>'
        : '<span class="etiqueta pendente">sem laudo</span>';
    return `
      <div class="cartao-exame" onclick="location.hash='exame/${e.id}'">
        ${capa}
        <div class="info">
          <b>${esc(nome)}</b>
          <small>${esc(e.procedimento_nome || e.descricao || "Ultrassom")} ·
                 ${e.total_imagens} imagem(ns)</small><br>
          ${laudo}
        </div>
      </div>`;
  }).join("");

  const corpo = cartoes
    ? `<div class="grade-exames">${cartoes}</div>`
    : `<div class="vazio"><span class="icone">📡</span>
        Nenhum exame ainda.<br>Quando você fizer um exame no ultrassom,
        ele aparece aqui em tempo real.</div>`;
  conteudo().innerHTML = `
    <h2 class="titulo">Exames recebidos
      <small style="font-weight:400;color:var(--texto-fraco)">atualiza sozinho 🔄</small>
    </h2>
    ${corpo}`;
}

/* ================= TELA: LAUDO ================= */
async function telaLaudo(estudoId) {
  const e = await api(`/api/estudos/${estudoId}`);
  const laudo = e.laudo || {};
  const selecionadas = new Set((laudo.imagens_ids || "").split(",").filter(Boolean).map(Number));
  window._selecionadas = selecionadas;
  window._estudoAtual = estudoId;

  const nome = (e.paciente && e.paciente.nome) || e.paciente_nome || "Paciente";
  const medicoSel = laudo.medico_id || e.agendamento_medico_id || "";
  const opMedicos = cacheMedicos.map((m) =>
    `<option value="${m.id}" ${m.id === medicoSel ? "selected" : ""}>${esc(m.nome)}</option>`).join("");

  const miniaturas = e.imagens.map((img) => {
    const marcada = selecionadas.has(img.id) ? "escolhida" : "";
    const corpo = img.tem_png
      ? `<img src="/arquivos/imagem/${img.id}" loading="lazy">`
      : `<div style="height:110px;display:flex;align-items:center;justify-content:center;color:#fff">DICOM</div>`;
    return `
      <div class="miniatura ${marcada}" id="mini-${img.id}">
        ${corpo}
        ${selecionadas.has(img.id) ? '<div class="marca">✓</div>' : ""}
        ${img.frames > 1 ? `<div class="cine">🎞 ${img.frames} quadros</div>` : ""}
      </div>`;
  }).join("");

  const modelos = cacheProcedimentos.filter((p) => p.modelo_laudo).map((p) =>
    `<option value="${p.id}">${esc(p.nome)}</option>`).join("");

  conteudo().innerHTML = `
    <h2 class="titulo">
      <span><a href="#exames" style="text-decoration:none">←</a> Laudo — ${esc(nome)}</span>
    </h2>
    <div class="cartao">
      <b>Imagens do exame</b>
      <small style="color:var(--texto-fraco)"> — toque para escolher as que entram no PDF,
        toque duas vezes para ampliar</small><br><br>
      <div class="galeria">${miniaturas ||
        '<div class="vazio">Sem imagens ainda — elas chegam sozinhas durante o exame</div>'}</div>
    </div>
    <div class="cartao">
      <label>Título do laudo</label>
      <input id="laudo-titulo"
             value="${esc(laudo.titulo || e.procedimento_nome || e.descricao || "")}">
      ${modelos ? `<label>Usar modelo de laudo</label>
        <select id="laudo-modelo" onchange="aplicarModelo()">
          <option value="">— escolher modelo —</option>${modelos}</select>` : ""}
      <label>Texto do laudo</label>
      <textarea id="laudo-texto" placeholder="Digite aqui o laudo…">${esc(laudo.texto || e.modelo_laudo || "")}</textarea>
      <label>Médico responsável</label>
      <select id="laudo-medico"><option value="">— escolher —</option>${opMedicos}</select>
      <label>Situação</label>
      <select id="laudo-final">
        <option value="0">Rascunho</option>
        <option value="1" ${laudo.finalizado ? "selected" : ""}>Finalizado</option>
      </select>
      <div class="acoes" style="display:flex;gap:8px;margin-top:16px">
        <button class="btn primario" style="flex:1" onclick="salvarLaudo()">💾 Salvar</button>
        <button class="btn" style="flex:1" onclick="gerarPDF()">📄 Gerar PDF</button>
      </div>
    </div>`;

  // clique simples seleciona; duplo clique amplia
  e.imagens.forEach((img) => {
    const el = $(`#mini-${img.id}`);
    if (!el) return;
    let timer = null;
    el.addEventListener("click", () => {
      clearTimeout(timer);
      timer = setTimeout(() => alternarImagem(img.id), 220);
    });
    el.addEventListener("dblclick", () => {
      clearTimeout(timer);
      if (img.tem_png) abrirModal(
        `<img class="imagem-grande" src="/arquivos/imagem/${img.id}">
         <div class="acoes"><button class="btn" onclick="fecharModal()">Fechar</button></div>`);
    });
  });

  // se ainda chegam imagens, atualiza a galeria a cada 6 s
  timerExames = setInterval(async () => {
    const atual = await api(`/api/estudos/${estudoId}`);
    if (atual.imagens.length !== e.imagens.length) telaLaudo(estudoId);
  }, 6000);
}

function alternarImagem(id) {
  const sel = window._selecionadas;
  const el = $(`#mini-${id}`);
  if (!el) return;
  if (sel.has(id)) {
    sel.delete(id);
    el.classList.remove("escolhida");
    const marca = el.querySelector(".marca");
    if (marca) marca.remove();
  } else {
    sel.add(id);
    el.classList.add("escolhida");
    el.insertAdjacentHTML("beforeend", '<div class="marca">✓</div>');
  }
}

function aplicarModelo() {
  const id = parseInt($("#laudo-modelo").value);
  const proc = cacheProcedimentos.find((p) => p.id === id);
  if (proc && proc.modelo_laudo) {
    if (!$("#laudo-texto").value.trim() ||
        confirm("Substituir o texto atual pelo modelo?"))
      $("#laudo-texto").value = proc.modelo_laudo;
  }
}

async function salvarLaudo() {
  await api(`/api/estudos/${window._estudoAtual}/laudo`, "POST", {
    titulo: $("#laudo-titulo").value,
    texto: $("#laudo-texto").value,
    medico_id: $("#laudo-medico").value || null,
    imagens_ids: [...window._selecionadas],
    finalizado: $("#laudo-final").value,
  });
  avisar("Laudo salvo ✔");
}

async function gerarPDF() {
  await salvarLaudo();
  window.open(`/api/estudos/${window._estudoAtual}/laudo.pdf`, "_blank");
}

/* ================= TELA: CADASTROS ================= */
function telaCadastros(aba) {
  aba = aba || sessionStorage.getItem("aba_cadastro") || "procedimentos";
  sessionStorage.setItem("aba_cadastro", aba);
  conteudo().innerHTML = `
    <h2 class="titulo">Cadastros</h2>
    <div class="abas">
      <button class="btn ${aba === "procedimentos" ? "ativa" : ""}"
        onclick="telaCadastros('procedimentos')">Procedimentos</button>
      <button class="btn ${aba === "medicos" ? "ativa" : ""}"
        onclick="telaCadastros('medicos')">Médicos</button>
      <button class="btn ${aba === "pacientes" ? "ativa" : ""}"
        onclick="telaCadastros('pacientes')">Pacientes</button>
    </div>
    <div id="aba-conteudo"></div>`;
  ({ procedimentos: abaProcedimentos, medicos: abaMedicos,
     pacientes: abaPacientes }[aba])();
}

async function abaProcedimentos() {
  cacheProcedimentos = await api("/api/procedimentos");
  $("#aba-conteudo").innerHTML = `
    <div class="cartao">
      <button class="btn primario" onclick="modalProcedimento()">➕ Novo procedimento</button>
      ${cacheProcedimentos.map((p) => `
        <div class="linha-lista">
          <div><b>${esc(p.nome)}</b>
            <small>${dinheiro(p.preco)} · ${p.duracao_min} min
              ${p.modelo_laudo ? "· tem modelo de laudo" : ""}</small></div>
          <button class="btn pequeno" onclick="modalProcedimento(${p.id})">Editar</button>
        </div>`).join("") ||
        '<div class="vazio">Cadastre seus exames aqui (ex.: US Abdome Total — R$ 180)</div>'}
    </div>`;
}

function modalProcedimento(id) {
  const p = cacheProcedimentos.find((x) => x.id === id) || {};
  abrirModal(`
    <h3>${id ? "Editar" : "Novo"} procedimento</h3>
    <label>Nome do exame</label>
    <input id="pr-nome" value="${esc(p.nome || "")}" placeholder="US Abdome Total">
    <div class="linha-form">
      <div><label>Preço (R$)</label>
        <input type="number" step="0.01" id="pr-preco" value="${p.preco ?? ""}"></div>
      <div><label>Duração (min)</label>
        <input type="number" id="pr-dur" value="${p.duracao_min ?? 20}"></div>
    </div>
    <label>Modelo de laudo (texto pré-pronto, opcional)</label>
    <textarea id="pr-modelo" placeholder="Fígado de dimensões normais…">${esc(p.modelo_laudo || "")}</textarea>
    <div class="acoes">
      ${id ? `<button class="btn perigo" onclick="removerProcedimento(${id})">Excluir</button>` : ""}
      <button class="btn" onclick="fecharModal()">Fechar</button>
      <button class="btn primario" onclick="salvarProcedimento(${id || "null"})">Salvar</button>
    </div>`);
}

async function salvarProcedimento(id) {
  const corpo = {
    nome: $("#pr-nome").value.trim(), preco: $("#pr-preco").value,
    duracao_min: $("#pr-dur").value, modelo_laudo: $("#pr-modelo").value,
  };
  if (!corpo.nome) { avisar("Informe o nome"); return; }
  await api(id ? `/api/procedimentos/${id}` : "/api/procedimentos",
            id ? "PUT" : "POST", corpo);
  fecharModal(); abaProcedimentos(); avisar("Procedimento salvo ✔");
}

async function removerProcedimento(id) {
  if (!confirm("Excluir este procedimento?")) return;
  await api(`/api/procedimentos/${id}`, "DELETE");
  fecharModal(); abaProcedimentos();
}

async function abaMedicos() {
  cacheMedicos = await api("/api/medicos");
  $("#aba-conteudo").innerHTML = `
    <div class="cartao">
      <button class="btn primario" onclick="modalMedico()">➕ Novo médico</button>
      ${cacheMedicos.map((m) => `
        <div class="linha-lista">
          <div><b>${esc(m.nome)}</b>
            <small>${esc(m.crm ? "CRM " + m.crm : "")} ${esc(m.especialidade || "")}</small></div>
          <button class="btn pequeno" onclick="modalMedico(${m.id})">Editar</button>
        </div>`).join("") || '<div class="vazio">Cadastre os médicos aqui</div>'}
    </div>`;
}

function modalMedico(id) {
  const m = cacheMedicos.find((x) => x.id === id) || {};
  abrirModal(`
    <h3>${id ? "Editar" : "Novo"} médico</h3>
    <label>Nome</label><input id="md-nome" value="${esc(m.nome || "")}" placeholder="Dr(a). …">
    <div class="linha-form">
      <div><label>CRM</label><input id="md-crm" value="${esc(m.crm || "")}"></div>
      <div><label>Especialidade</label><input id="md-esp" value="${esc(m.especialidade || "")}"></div>
    </div>
    <div class="acoes">
      ${id ? `<button class="btn perigo" onclick="removerMedico(${id})">Excluir</button>` : ""}
      <button class="btn" onclick="fecharModal()">Fechar</button>
      <button class="btn primario" onclick="salvarMedico(${id || "null"})">Salvar</button>
    </div>`);
}

async function salvarMedico(id) {
  const corpo = { nome: $("#md-nome").value.trim(), crm: $("#md-crm").value,
                  especialidade: $("#md-esp").value };
  if (!corpo.nome) { avisar("Informe o nome"); return; }
  await api(id ? `/api/medicos/${id}` : "/api/medicos", id ? "PUT" : "POST", corpo);
  fecharModal(); abaMedicos(); avisar("Médico salvo ✔");
}

async function removerMedico(id) {
  if (!confirm("Excluir este médico?")) return;
  await api(`/api/medicos/${id}`, "DELETE");
  fecharModal(); abaMedicos();
}

async function abaPacientes(busca) {
  const lista = await api(`/api/pacientes${busca ? "?busca=" + encodeURIComponent(busca) : ""}`);
  $("#aba-conteudo").innerHTML = `
    <div class="cartao">
      <input placeholder="🔎 Buscar paciente…" value="${esc(busca || "")}"
             oninput="clearTimeout(window._tb); window._tb=setTimeout(()=>abaPacientes(this.value),300)">
      <br><br>
      ${lista.map((p) => `
        <div class="linha-lista">
          <div><b>${esc(p.nome)}</b>
            <small>${dataBR(p.nascimento)} ${esc(p.telefone || "")}</small></div>
          <button class="btn pequeno"
            onclick='modalPaciente(${JSON.stringify(p).replace(/'/g, "&#39;")})'>Editar</button>
        </div>`).join("") || '<div class="vazio">Nenhum paciente</div>'}
    </div>`;
}

function modalPaciente(p) {
  abrirModal(`
    <h3>Editar paciente</h3>
    <label>Nome</label><input id="pa-nome" value="${esc(p.nome)}">
    <div class="linha-form">
      <div><label>Nascimento</label><input type="date" id="pa-nasc" value="${esc(p.nascimento)}"></div>
      <div><label>Sexo</label>
        <select id="pa-sexo">
          <option value="F" ${p.sexo === "F" ? "selected" : ""}>Feminino</option>
          <option value="M" ${p.sexo === "M" ? "selected" : ""}>Masculino</option>
          <option value="O" ${p.sexo === "O" ? "selected" : ""}>Outro</option>
        </select></div>
    </div>
    <div class="linha-form">
      <div><label>Telefone</label><input id="pa-tel" value="${esc(p.telefone)}"></div>
      <div><label>Documento</label><input id="pa-doc" value="${esc(p.documento)}"></div>
    </div>
    <div class="acoes">
      <button class="btn" onclick="fecharModal()">Fechar</button>
      <button class="btn primario" onclick="salvarPaciente(${p.id})">Salvar</button>
    </div>`);
}

async function salvarPaciente(id) {
  await api(`/api/pacientes/${id}`, "PUT", {
    nome: $("#pa-nome").value, nascimento: $("#pa-nasc").value,
    sexo: $("#pa-sexo").value, telefone: $("#pa-tel").value,
    documento: $("#pa-doc").value,
  });
  fecharModal(); abaPacientes(); avisar("Paciente salvo ✔");
}

/* ================= TELA: AJUSTES ================= */
async function telaConfig() {
  const c = await api("/api/config");
  conteudo().innerHTML = `
    <h2 class="titulo">Ajustes</h2>
    <div class="cartao">
      <b>Dados da clínica (aparecem no laudo)</b>
      <label>Nome da clínica</label><input id="cf-nome" value="${esc(c.nome_clinica)}">
      <label>Subtítulo</label><input id="cf-sub" value="${esc(c.subtitulo_clinica)}">
      <label>Endereço</label><input id="cf-end" value="${esc(c.endereco_clinica)}">
      <label>Telefone</label><input id="cf-tel" value="${esc(c.telefone_clinica)}">
    </div>
    <div class="cartao">
      <b>Conexão com o ultrassom (DICOM)</b>
      <p style="font-size:13.5px;color:var(--texto-fraco);margin-top:6px">
        Configure no seu aparelho de ultrassom estes dados, tanto para
        <b>armazenamento (Storage)</b> quanto para <b>Worklist</b>:</p>
      <label>AE Title (nome DICOM deste servidor)</label>
      <input id="cf-ae" value="${esc(c.ae_title)}">
      <label>Porta DICOM</label>
      <input id="cf-porta" type="number" value="${c.porta_dicom}">
      <p style="font-size:13.5px;color:var(--texto-fraco);margin-top:8px">
        💡 No ultrassom, use o IP do computador onde o Daikon está rodando,
        com o AE Title e a porta acima.</p>
    </div>
    <div class="cartao">
      <b>Segurança</b>
      <label>Nova senha (deixe vazio para manter)</label>
      <input type="password" id="cf-senha" placeholder="••••••">
    </div>
    <button class="btn primario" style="width:100%" onclick="salvarConfig()">💾 Salvar ajustes</button>
    <br><br>
    <button class="btn" style="width:100%" onclick="sair()">Sair (logout)</button>`;
}

async function salvarConfig() {
  const r = await api("/api/config", "PUT", {
    nome_clinica: $("#cf-nome").value, subtitulo_clinica: $("#cf-sub").value,
    endereco_clinica: $("#cf-end").value, telefone_clinica: $("#cf-tel").value,
    ae_title: $("#cf-ae").value, porta_dicom: parseInt($("#cf-porta").value),
    nova_senha: $("#cf-senha").value,
  });
  $("#nome-clinica-topo").textContent = $("#cf-nome").value || "Daikon";
  avisar(r.aviso || "Ajustes salvos ✔");
}

async function sair() {
  await api("/api/logout", "POST");
  mostrarLogin();
}

/* ---------------- início ---------------- */
window.addEventListener("hashchange", navegar);
$("#login-senha").addEventListener("keydown", (e) => {
  if (e.key === "Enter") fazerLogin();
});

(async () => {
  if ("serviceWorker" in navigator) {
    try { await navigator.serviceWorker.register("/sw.js"); } catch (e) {}
  }
  try {
    await api("/api/resumo");           // sessão ainda válida?
    $("#app").classList.remove("oculto");
    iniciarApp();
  } catch (e) { /* mostrarLogin já foi chamado */ }
})();
