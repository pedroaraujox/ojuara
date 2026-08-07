/* Ojuara - grade de digitacao em lote por codigo do produto + tamanho + cor.
 *
 * Usada na entrada/baixa/devolucao de estoque, na montagem de sacolas e na
 * tela de nova venda. O operador digita o codigo, tecla Enter; se o codigo
 * tiver mais de um tamanho cadastrado, escolhe o tamanho num select; tecla
 * Enter de novo, digita a quantidade e cai direto na proxima linha.
 */
(function (global) {
  "use strict";

  var cacheProdutos = {};

  function normalizaLeitura(valor) {
    return String(valor || "").replace(/\s+/g, "").toUpperCase();
  }

  var modalLeitor = null;
  var instanciaModalLeitor = null;
  var controleLeitor = null;
  var aoLerCodigo = null;
  var ultimaLeituraCamera = "";
  var repeticoesLeituraCamera = 0;
  var opcoesLeitor = {};
  var workerOCRPromise = null;

  function pararCamera() {
    if (controleLeitor && controleLeitor.stop) {
      controleLeitor.stop();
    }
    controleLeitor = null;
    if (modalLeitor) {
      var video = modalLeitor.querySelector("video");
      if (video && video.srcObject) {
        video.srcObject.getTracks().forEach(function (trilha) { trilha.stop(); });
        video.srcObject = null;
      }
    }
  }

  function capturarAreaNome() {
    var video = modalLeitor.querySelector("video");
    if (!video.videoWidth || !video.videoHeight) {
      return null;
    }
    var canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = Math.round(video.videoHeight * 0.5);
    canvas.getContext("2d").drawImage(
      video,
      0, 0, video.videoWidth, canvas.height,
      0, 0, canvas.width, canvas.height
    );
    return canvas;
  }

  function extrairNomeEtiqueta(texto, codigo) {
    var ignorar = /(^|\s)(R\$|RS)\s*\d|CONT[EÉ]M|PE[CÇ]AS?|PRE[CÇ]O|TAMANHO|^\d+[,.]?\d*$/i;
    var linhas = String(texto || "").split(/\r?\n/).map(function (linha) {
      return linha.replace(/[^0-9A-Za-zÀ-ÿ\s\-]/g, " ").replace(/\s+/g, " ").trim();
    }).filter(function (linha) {
      return linha && linha !== codigo && !ignorar.test(linha) && /[A-Za-zÀ-ÿ]{2}/.test(linha);
    });
    return linhas.slice(0, 2).join(" ").replace(/\s+/g, " ").trim().slice(0, 100);
  }

  function reconhecerNomeEtiqueta(canvas, codigo) {
    if (!canvas || !global.Tesseract || !global.Tesseract.createWorker) {
      return Promise.resolve("");
    }
    if (!workerOCRPromise) {
      workerOCRPromise = global.Tesseract.createWorker("por");
    }
    return workerOCRPromise.then(function (worker) {
      return worker.recognize(canvas);
    }).then(function (resultado) {
      return extrairNomeEtiqueta(resultado.data.text, codigo);
    });
  }

  function concluirLeitura(valor, veioDaCamera) {
    valor = normalizaLeitura(valor);
    if (!valor) {
      return;
    }
    var status = modalLeitor.querySelector(".status-leitor");
    var campoManual = modalLeitor.querySelector(".leitura-manual");
    if (!/^\d{5}$/.test(valor)) {
      status.textContent = "Leitura incompleta (" + valor + "). Mantenha a etiqueta centralizada.";
      if (!veioDaCamera) {
        campoManual.classList.add("is-invalid");
        campoManual.focus();
      }
      return;
    }
    campoManual.classList.remove("is-invalid");
    if (veioDaCamera) {
      if (valor === ultimaLeituraCamera) {
        repeticoesLeituraCamera += 1;
      } else {
        ultimaLeituraCamera = valor;
        repeticoesLeituraCamera = 1;
      }
      if (repeticoesLeituraCamera < 2) {
        status.textContent = "Codigo " + valor + " identificado. Mantenha a camera firme para confirmar.";
        return;
      }
    }
    var callback = aoLerCodigo;
    if (veioDaCamera && opcoesLeitor.lerNome) {
      var imagemNome = capturarAreaNome();
      status.textContent = "Codigo " + valor + " confirmado. Lendo o nome da etiqueta...";
      pararCamera();
      reconhecerNomeEtiqueta(imagemNome, valor).then(function (nome) {
        instanciaModalLeitor.hide();
        if (callback) {
          callback(valor, nome);
        }
      }).catch(function () {
        instanciaModalLeitor.hide();
        if (callback) {
          callback(valor, "");
        }
      });
      return;
    }
    pararCamera();
    instanciaModalLeitor.hide();
    if (callback) {
      callback(valor);
    }
  }

  function criarModalLeitor() {
    if (modalLeitor) {
      return;
    }
    modalLeitor = document.createElement("div");
    modalLeitor.className = "modal fade";
    modalLeitor.tabIndex = -1;
    modalLeitor.setAttribute("aria-hidden", "true");
    modalLeitor.innerHTML =
      '<div class="modal-dialog modal-dialog-centered">' +
        '<div class="modal-content">' +
          '<div class="modal-header">' +
            '<h2 class="modal-title fs-5"><i class="bi bi-upc-scan me-2"></i>Ler etiqueta</h2>' +
            '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fechar"></button>' +
          '</div>' +
          '<div class="modal-body">' +
            '<div class="ratio ratio-4x3 bg-dark rounded overflow-hidden mb-3">' +
              '<video class="w-100 h-100 object-fit-cover" muted playsinline></video>' +
              '<div class="mira-leitor" aria-hidden="true"></div>' +
            '</div>' +
            '<p class="small text-secondary status-leitor mb-2">Aponte a camera para o codigo de barras.</p>' +
            '<p class="small text-secondary mb-2">Se o celular perguntar sempre, altere a permissao ' +
              'deste site para <strong>Permitir</strong> nas configuracoes do navegador.</p>' +
            '<div class="input-group">' +
              '<input type="text" class="form-control leitura-manual" autocomplete="off" ' +
                     'inputmode="numeric" maxlength="5" pattern="[0-9]{5}" ' +
                     'placeholder="Codigo com 5 numeros">' +
              '<button type="button" class="btn btn-marca confirmar-leitura">Usar codigo</button>' +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(modalLeitor);
    instanciaModalLeitor = new bootstrap.Modal(modalLeitor);

    var campoManual = modalLeitor.querySelector(".leitura-manual");
    modalLeitor.querySelector(".confirmar-leitura").addEventListener("click", function () {
      concluirLeitura(campoManual.value, false);
    });
    campoManual.addEventListener("keydown", function (evento) {
      if (evento.key === "Enter") {
        evento.preventDefault();
        concluirLeitura(campoManual.value, false);
      }
    });
    modalLeitor.addEventListener("hidden.bs.modal", pararCamera);
  }

  function abrirLeitor(callback, opcoes) {
    criarModalLeitor();
    pararCamera();
    aoLerCodigo = callback;
    opcoesLeitor = opcoes || {};
    var status = modalLeitor.querySelector(".status-leitor");
    var campoManual = modalLeitor.querySelector(".leitura-manual");
    campoManual.value = "";
    campoManual.classList.remove("is-invalid");
    ultimaLeituraCamera = "";
    repeticoesLeituraCamera = 0;
    status.textContent = "Aponte a camera para o codigo de barras.";
    instanciaModalLeitor.show();

    modalLeitor.addEventListener("shown.bs.modal", function iniciar() {
      modalLeitor.removeEventListener("shown.bs.modal", iniciar);
      if (!global.ZXingBrowser) {
        status.textContent = "Camera indisponivel. Digite o codigo ou use um leitor fisico.";
        campoManual.focus();
        return;
      }
      var leitor = new global.ZXingBrowser.BrowserMultiFormatOneDReader();
      leitor.decodeFromConstraints(
        { video: { facingMode: { ideal: "environment" } }, audio: false },
        modalLeitor.querySelector("video"),
        function (resultado, _erro, controles) {
          if (resultado) {
            controleLeitor = controles;
            concluirLeitura(resultado.getText(), true);
          }
        }
      ).then(function (controles) {
        controleLeitor = controles;
      }).catch(function () {
        status.textContent = "Nao foi possivel abrir a camera. Digite o codigo abaixo.";
        campoManual.focus();
      });
    });
  }

  function moedaBR(valor) {
    return (valor || 0).toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL"
    });
  }

  function buscaProduto(codigo, parametros) {
    parametros = parametros || "";
    var chaveCache = codigo + "?" + parametros;
    if (cacheProdutos[chaveCache]) {
      return Promise.resolve(cacheProdutos[chaveCache]);
    }
    var url = "/api/produtos/" + encodeURIComponent(codigo);
    if (parametros) url += "?" + parametros;
    return fetch(url)
      .then(function (resposta) {
        return resposta.json().then(function (dados) {
          var resultado = resposta.ok
            ? dados
            : { encontrado: false, codigo: codigo, variantes: [] };
          cacheProdutos[chaveCache] = resultado;
          return resultado;
        });
      })
      .catch(function () {
        return { encontrado: false, codigo: codigo, variantes: [], erro: true };
      });
  }

  function GradeLote(opcoes) {
    this.corpo = document.getElementById(opcoes.corpo);
    this.modelo = document.getElementById(opcoes.modelo);
    this.comPreco = !!opcoes.comPreco;
    this.aoAtualizar = opcoes.aoAtualizar || function () {};
    this.botaoAdicionar = document.getElementById(opcoes.botaoAdicionar);
    this.parametrosBusca = opcoes.parametrosBusca || function () { return ""; };
    this.validaEstoque = true;

    var self = this;
    if (this.botaoAdicionar) {
      this.botaoAdicionar.addEventListener("click", function () {
        self.adicionar().querySelector(".codigo-lote").focus();
      });
      var botaoEscanear = document.createElement("button");
      botaoEscanear.type = "button";
      botaoEscanear.className = "btn btn-outline-secondary btn-sm";
      botaoEscanear.innerHTML = '<i class="bi bi-camera me-1"></i>Ler codigo';
      botaoEscanear.addEventListener("click", function () {
        abrirLeitor(function (codigo) {
          self.preencherProximo(codigo);
        });
      });
      this.botaoAdicionar.insertAdjacentElement("afterend", botaoEscanear);
    }
    this.corpo.addEventListener("click", function (evento) {
      var botao = evento.target.closest(".remover-linha");
      if (botao) {
        self.remover(botao.closest("tr"));
      }
    });
  }

  GradeLote.prototype.linhas = function () {
    return Array.prototype.slice.call(this.corpo.querySelectorAll("tr.linha-lote"));
  };

  GradeLote.prototype.adicionar = function (dados) {
    dados = dados || {};
    var fragmento = this.modelo.content.cloneNode(true);
    var linha = fragmento.querySelector("tr");
    var self = this;

    var campoCodigo = linha.querySelector(".codigo-lote");
    var campoTamanho = linha.querySelector(".tamanho-lote");
    var campoCor = linha.querySelector(".cor-lote");
    var campoQtd = linha.querySelector(".qtd-lote");
    var campoPreco = linha.querySelector(".preco-lote");

    campoCodigo.value = dados.codigo || "";
    campoQtd.value = dados.quantidade || 1;
    if (campoPreco && dados.preco) {
      campoPreco.value = dados.preco;
    }
    this._resetaVariante(linha);

    campoCodigo.addEventListener("change", function () {
      self.verificarCodigo(linha).then(function () {
        if (dados.tamanho) {
          self._selecionaTamanho(linha, dados.tamanho, dados.cor || "");
        }
      });
    });
    campoCodigo.addEventListener("keydown", function (evento) {
      if (evento.key === "Enter") {
        evento.preventDefault();
        self.verificarCodigo(linha).then(function () {
          if (campoTamanho.options.length > 1 && !campoTamanho.disabled) {
            campoTamanho.focus();
          } else if (campoCor.options.length > 1 && !campoCor.disabled) {
            campoCor.focus();
          } else {
            campoQtd.focus();
            campoQtd.select();
          }
        });
      }
    });
    campoTamanho.addEventListener("change", function () {
      self._atualizarCores(linha);
    });
    campoTamanho.addEventListener("keydown", function (evento) {
      if (evento.key === "Enter") {
        evento.preventDefault();
        if (campoCor.options.length > 1 && !campoCor.disabled) {
          campoCor.focus();
        } else {
          campoQtd.focus();
          campoQtd.select();
        }
      }
    });
    campoCor.addEventListener("change", function () {
      self._aplicarVariante(linha);
    });
    campoCor.addEventListener("keydown", function (evento) {
      if (evento.key === "Enter") {
        evento.preventDefault();
        campoQtd.focus();
        campoQtd.select();
      }
    });
    campoQtd.addEventListener("keydown", function (evento) {
      if (evento.key === "Enter") {
        evento.preventDefault();
        var proxima = linha.nextElementSibling;
        if (proxima) {
          proxima.querySelector(".codigo-lote").focus();
        } else {
          self.adicionar().querySelector(".codigo-lote").focus();
        }
      }
    });
    campoQtd.addEventListener("input", function () {
      self._aplicarVariante(linha);
    });
    if (campoPreco) {
      campoPreco.addEventListener("input", function () {
        self.atualizarLinha(linha);
        self.aoAtualizar(self);
      });
    }

    this.corpo.appendChild(linha);
    if (campoCodigo.value) {
      this.verificarCodigo(linha).then(function () {
        if (dados.tamanho) {
          self._selecionaTamanho(linha, dados.tamanho, dados.cor || "");
        }
      });
    }
    this.aoAtualizar(this);
    return linha;
  };

  GradeLote.prototype.remover = function (linha) {
    linha.remove();
    if (this.linhas().length === 0) {
      this.adicionar();
    }
    this.aoAtualizar(this);
  };

  GradeLote.prototype._resetaVariante = function (linha) {
    var campoTamanho = linha.querySelector(".tamanho-lote");
    var campoCor = linha.querySelector(".cor-lote");
    campoTamanho.innerHTML = '<option value="">--</option>';
    campoTamanho.disabled = true;
    campoCor.innerHTML = '<option value="">--</option>';
    campoCor.disabled = true;
    linha._variantes = [];
    linha.dataset.produtoNome = "";
  };

  GradeLote.prototype.verificarCodigo = function (linha) {
    var self = this;
    var campoCodigo = linha.querySelector(".codigo-lote");
    var codigo = (campoCodigo.value || "").replace(/\s+/g, "").toUpperCase();
    campoCodigo.value = codigo;

    var status = linha.querySelector(".status-item");
    this._resetaVariante(linha);

    if (!codigo) {
      status.innerHTML = '<span class="text-secondary">Digite o codigo</span>';
      this.atualizarLinha(linha);
      this.aoAtualizar(this);
      return Promise.resolve();
    }

    status.innerHTML = '<span class="text-secondary">Consultando...</span>';
    return buscaProduto(codigo, self.parametrosBusca()).then(function (produto) {
      var campoTamanho = linha.querySelector(".tamanho-lote");

      if (!produto.encontrado || !produto.variantes || !produto.variantes.length) {
        status.innerHTML =
          '<span class="text-danger"><i class="bi bi-x-circle me-1"></i>' +
          "Codigo nao cadastrado</span>";
        self.atualizarLinha(linha);
        self.aoAtualizar(self);
        return;
      }

      linha.dataset.produtoNome = produto.variantes[0].nome || "";
      linha._variantes = produto.variantes;
      campoTamanho.innerHTML = "";
      var tamanhos = [];
      produto.variantes.forEach(function (variante) {
        if (tamanhos.indexOf(variante.tamanho) === -1) {
          tamanhos.push(variante.tamanho);
        }
      });
      if (tamanhos.length > 1) {
        campoTamanho.appendChild(new Option("Selecione...", ""));
      }
      tamanhos.forEach(function (tamanho) {
        campoTamanho.appendChild(new Option(tamanho, tamanho));
      });
      campoTamanho.disabled = false;

      if (tamanhos.length === 1) {
        campoTamanho.selectedIndex = 0;
        self._atualizarCores(linha);
      } else {
        status.innerHTML =
          '<span class="text-warning-emphasis">' +
          '<i class="bi bi-arrow-left-short me-1"></i>Selecione o tamanho</span>';
      }
      self.atualizarLinha(linha);
      self.aoAtualizar(self);
    });
  };

  GradeLote.prototype._selecionaTamanho = function (linha, tamanho, cor) {
    var campoTamanho = linha.querySelector(".tamanho-lote");
    for (var i = 0; i < campoTamanho.options.length; i++) {
      if (campoTamanho.options[i].value === tamanho) {
        campoTamanho.selectedIndex = i;
        this._atualizarCores(linha);
        this._selecionaCor(linha, cor);
        return;
      }
    }
  };

  GradeLote.prototype._selecionaCor = function (linha, cor) {
    var campoCor = linha.querySelector(".cor-lote");
    for (var i = 0; i < campoCor.options.length; i++) {
      if (campoCor.options[i].value === cor) {
        campoCor.selectedIndex = i;
        this._aplicarVariante(linha);
        return;
      }
    }
  };

  GradeLote.prototype._atualizarCores = function (linha) {
    var campoTamanho = linha.querySelector(".tamanho-lote");
    var campoCor = linha.querySelector(".cor-lote");
    var tamanho = campoTamanho.value;
    var variantes = (linha._variantes || []).filter(function (variante) {
      return variante.tamanho === tamanho;
    });
    campoCor.innerHTML = "";
    if (variantes.length > 1) {
      campoCor.appendChild(new Option("Selecione...", ""));
    }
    variantes.forEach(function (variante) {
      campoCor.appendChild(new Option(variante.cor, variante.cor));
    });
    campoCor.disabled = !tamanho || !variantes.length;
    if (variantes.length === 1) {
      campoCor.selectedIndex = 0;
      this._aplicarVariante(linha);
    } else {
      linha.querySelector(".status-item").innerHTML =
        '<span class="text-warning-emphasis"><i class="bi bi-arrow-left-short me-1"></i>' +
        "Selecione a cor</span>";
    }
  };

  GradeLote.prototype._aplicarVariante = function (linha) {
    var self = this;
    var campoTamanho = linha.querySelector(".tamanho-lote");
    var campoCor = linha.querySelector(".cor-lote");
    var status = linha.querySelector(".status-item");
    var tamanho = campoTamanho.value;
    var cor = campoCor.value;
    var variante = (linha._variantes || []).filter(function (item) {
      return item.tamanho === tamanho && item.cor === cor;
    })[0];

    if (!variante) {
      if (!tamanho) {
        status.innerHTML =
          '<span class="text-warning-emphasis">' +
          '<i class="bi bi-arrow-left-short me-1"></i>Selecione o tamanho</span>';
      } else {
        status.innerHTML =
          '<span class="text-warning-emphasis">' +
          '<i class="bi bi-arrow-left-short me-1"></i>Selecione a cor</span>';
      }
      this.atualizarLinha(linha);
      this.aoAtualizar(this);
      return;
    }

    var preco = parseFloat(variante.preco_venda) || 0;
    var estoque = parseInt(variante.estoque, 10) || 0;

    var campoPreco = linha.querySelector(".preco-lote");
    if (campoPreco && !campoPreco.value) {
      campoPreco.value = preco.toFixed(2);
    }

    var qtd = parseInt(linha.querySelector(".qtd-lote").value, 10) || 0;
    var alerta = "";
    if (self.validaEstoque !== false && qtd > estoque) {
      alerta = ' <span class="badge bg-danger">estoque insuficiente</span>';
    }
    status.innerHTML =
      '<span class="text-success"><i class="bi bi-check-circle me-1"></i></span>' +
      "<strong>" + (linha.dataset.produtoNome || "") + "</strong>" +
      ' <span class="text-secondary">(' + tamanho + " / " + cor + ")</span>" +
      ' <span class="text-secondary">| estoque: ' + estoque + "</span>" +
      (self.comPreco ? " | " + moedaBR(preco) : "") +
      alerta;

    this.atualizarLinha(linha);
    this.aoAtualizar(this);
  };

  GradeLote.prototype.atualizarLinha = function (linha) {
    var celulaTotal = linha.querySelector(".total-linha");
    if (!celulaTotal) {
      return;
    }
    var qtd = parseInt(linha.querySelector(".qtd-lote").value, 10) || 0;
    var campoPreco = linha.querySelector(".preco-lote");
    var preco = campoPreco ? parseFloat(String(campoPreco.value).replace(",", ".")) || 0 : 0;
    celulaTotal.textContent = moedaBR(qtd * preco);
  };

  GradeLote.prototype.subtotal = function () {
    var total = 0;
    this.linhas().forEach(function (linha) {
      var campoPreco = linha.querySelector(".preco-lote");
      if (!campoPreco) {
        return;
      }
      var qtd = parseInt(linha.querySelector(".qtd-lote").value, 10) || 0;
      var preco = parseFloat(String(campoPreco.value).replace(",", ".")) || 0;
      total += qtd * preco;
    });
    return Math.round(total * 100) / 100;
  };

  // Usado pelo botao "usar" da tabela de referencia do catalogo: preenche a
  // proxima linha vazia (ou cria uma nova) com o codigo escolhido e ja
  // consulta as variantes, deixando o operador so digitar a quantidade.
  GradeLote.prototype.preencherProximo = function (codigo) {
    var alvo = this.linhas().filter(function (linha) {
      return !(linha.querySelector(".codigo-lote").value || "").trim();
    })[0];
    if (!alvo) {
      alvo = this.adicionar();
    }
    var campoCodigo = alvo.querySelector(".codigo-lote");
    campoCodigo.value = codigo;
    this.verificarCodigo(alvo).then(function () {
      var campoTamanho = alvo.querySelector(".tamanho-lote");
      var campoCor = alvo.querySelector(".cor-lote");
      var campoQtd = alvo.querySelector(".qtd-lote");
      if (campoTamanho.options.length > 1 && !campoTamanho.disabled) {
        campoTamanho.focus();
      } else if (campoCor.options.length > 1 && !campoCor.disabled) {
        campoCor.focus();
      } else {
        campoQtd.focus();
        campoQtd.select();
      }
    });
  };

  GradeLote.prototype.totalPecas = function () {
    var total = 0;
    this.linhas().forEach(function (linha) {
      if ((linha.querySelector(".codigo-lote").value || "").trim()) {
        total += parseInt(linha.querySelector(".qtd-lote").value, 10) || 0;
      }
    });
    return total;
  };

  global.GradeLote = GradeLote;
  global.moedaBR = moedaBR;
  global.abrirLeitorCodigoBarras = abrirLeitor;

  document.querySelectorAll(".leitor-campo[data-leitor-campo]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      var campo = document.getElementById(botao.dataset.leitorCampo);
      if (!campo) {
        return;
      }
      abrirLeitor(function (codigo, nome) {
        campo.value = codigo;
        campo.dispatchEvent(new Event("change", { bubbles: true }));
        campo.focus();
        var campoNomeId = botao.dataset.leitorNomeCampo;
        var campoNome = campoNomeId ? document.getElementById(campoNomeId) : null;
        if (campoNome && nome) {
          campoNome.value = nome;
          campoNome.classList.add("is-valid");
          campoNome.focus();
          campoNome.select();
        }
      }, { lerNome: !!botao.dataset.leitorNomeCampo });
    });
  });

  // Confirmacao generica para acoes destrutivas.
  document.addEventListener("submit", function (evento) {
    var formulario = evento.target;
    var pergunta = formulario.getAttribute("data-confirmar");
    if (pergunta && !global.confirm(pergunta)) {
      evento.preventDefault();
    }
  });

  // Alternar tema claro/escuro. O tema inicial ja e aplicado antes do CSS
  // carregar (ver _head_tema.html); aqui so cuidamos da troca e da persistencia.
  var botaoTema = document.getElementById("botao-tema");
  if (botaoTema) {
    botaoTema.addEventListener("click", function () {
      var raiz = document.documentElement;
      var atual = raiz.getAttribute("data-bs-theme") === "dark" ? "dark" : "light";
      var proximo = atual === "dark" ? "light" : "dark";
      raiz.setAttribute("data-bs-theme", proximo);
      try {
        localStorage.setItem("ojuara-tema", proximo);
      } catch (erro) {
        /* localStorage indisponivel (modo privado, etc.): tema so nao persiste. */
      }
    });
  }
})(window);
