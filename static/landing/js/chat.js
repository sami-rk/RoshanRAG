(function () {
  "use strict";

  var form = document.getElementById("ask-form");
  if (!form) return;

  var csrfEl = form.querySelector("input[name='csrfmiddlewaretoken']");
  var csrf = csrfEl ? csrfEl.value : "";
  var input = document.getElementById("ask-input");
  var submit = document.getElementById("ask-submit");
  var stream = document.getElementById("chat-stream");
  var historyList = document.getElementById("chat-history-list");

  function esc(value) {
    if (value == null) return "";
    var div = document.createElement("div");
    div.textContent = String(value);
    return div.innerHTML;
  }

  function statusLabel(status) {
    return {
      pending: "در انتظار",
      generating: "در حال تولید",
      done: "پاسخ داده شده",
      failed: "ناموفق",
    }[status] || status;
  }

  function addMessage(kind, html) {
    if (!stream) return;
    var el = document.createElement("div");
    el.className = "chat-msg chat-msg-" + kind;
    el.innerHTML = html;
    stream.appendChild(el);
    if (historyList) {
      historyList.closest(".chat-history").style.display = "none";
    }
  }

  function renderSources(sources) {
    if (!sources || !sources.length) return "";
    var items = sources
      .map(function (source) {
        var id = source.document_id != null ? source.document_id : "";
        var title = esc(source.title || "سند بدون نام");
        var excerpt = esc((source.excerpt || "").slice(0, 220));
        var link = id
          ? '<a href="/admin/documents/document/' + id + '/change/">' + title + "</a>"
          : title;
        return (
          '<li class="chat-source"><strong>' + link + "</strong><p>" + excerpt + "</p></li>"
        );
      })
      .join("");
    return '<div class="chat-sources-title">منابع:</div><ul class="chat-sources">' + items + "</ul>";
  }

  function renderAnswer(question) {
    if (question.status === "failed") {
      addMessage(
        "error",
        "<p>پاسخی تولید نشد: " + esc(question.error_message || "خطای ناشناخته") + "</p>"
      );
      return;
    }
    addMessage(
      "answer",
      "<p>" + esc(question.answer) + "</p>" + renderSources(question.sources)
    );
  }

  function setBusy(busy) {
    input.disabled = busy;
    submit.disabled = busy;
    submit.textContent = busy ? "در حال تولید…" : "پرسیدن";
  }

  function api(path, options) {
    options = options || {};
    options.headers = Object.assign({}, options.headers || {}, { "X-CSRFToken": csrf });
    if (options.body) {
      options.headers["Content-Type"] = "application/json";
    }
    return fetch(path, options).then(function (response) {
      if (response.status === 401 || response.status === 403) {
        window.location.href = "/admin/login/?next=" + encodeURIComponent("/chat/");
        throw new Error("unauthorized");
      }
      return response.json();
    });
  }

  function poll(questionId) {
    fetch("/api/questions/" + questionId + "/").then(function (response) {
      if (response.status === 401 || response.status === 403) {
        window.location.href = "/admin/login/?next=" + encodeURIComponent("/chat/");
        return;
      }
      return response.json();
    }).then(function (question) {
      if (!question) return;
      if (question.status === "done" || question.status === "failed") {
        setBusy(false);
        renderAnswer(question);
      } else {
        setTimeout(function () {
          poll(questionId);
        }, 1500);
      }
    });
  }

  function loadHistory() {
    if (!historyList) return;
    api("/api/questions/?page=1").then(function (data) {
      var items = (data.results || []).slice(0, 5);
      if (!items.length) {
        historyList.innerHTML = '<li class="chat-empty">هنوز پرسشی ثبت نشده است.</li>';
        return;
      }
      historyList.innerHTML = items
        .map(function (item) {
          var badge =
            '<span class="chat-badge chat-badge-' +
            item.status +
            '">' +
            statusLabel(item.status) +
            "</span>";
          return '<li><span class="chat-q">' + esc(item.question) + " " + badge + "</span></li>";
        })
        .join("");
    });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var text = (input.value || "").trim();
    if (!text) return;

    setBusy(true);
    addMessage("question", "<p>" + esc(text) + "</p>");
    input.value = "";

    api("/api/questions/", {
      method: "POST",
      body: JSON.stringify({ question: text }),
    }).then(function (question) {
      poll(question.id);
    }).catch(function () {
      setBusy(false);
      addMessage("error", "<p>ثبت پرسش ناموفق بود؛ دوباره تلاش کنید.</p>");
    });
  });

  loadHistory();
})();