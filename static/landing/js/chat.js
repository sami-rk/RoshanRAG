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

  function renderFeedback(question) {
    var qid = question.id;
    function thumb(kind) {
      var cls = "chat-fb-" + kind + (question.feedback === kind ? " active" : "");
      var title = kind === "up" ? "پاسخ مفید بود" : "پاسخ مفید نبود";
      var icon =
        kind === "up"
          ? '<path d="M7 10v12M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/>'
          : '<path d="M17 14V2M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/>';
      return (
        '<button type="button" class="' +
        cls +
        '" data-feedback="' +
        kind +
        '" data-id="' +
        qid +
        '" aria-label="' +
        title +
        '" title="' +
        title +
        '"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        icon +
        "</svg></button>"
      );
    }
    return (
      '<div class="chat-feedback"><span class="chat-feedback-label">این پاسخ چطور بود؟</span>' +
      thumb("up") +
      thumb("down") +
      "</div>"
    );
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
      "<p>" + esc(question.answer) + "</p>" + renderSources(question.sources) + renderFeedback(question)
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
    }).catch(function () {
      setBusy(false);
      addMessage("error", "<p>دریافت پاسخ ناموفق بود؛ دوباره تلاش کنید.</p>");
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

  if (stream) {
    stream.addEventListener("click", function (event) {
      var btn = event.target.closest("button[data-feedback]");
      if (!btn) return;
      var id = btn.getAttribute("data-id");
      var value = btn.classList.contains("active")
        ? "none"
        : btn.getAttribute("data-feedback");
      api("/api/questions/" + id + "/", {
        method: "PATCH",
        body: JSON.stringify({ feedback: value }),
      }).then(function () {
        var row = btn.closest(".chat-feedback");
        row.querySelectorAll("button[data-feedback]").forEach(function (b) {
          b.classList.remove("active");
        });
        if (value !== "none") btn.classList.add("active");
      }).catch(function () {});
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