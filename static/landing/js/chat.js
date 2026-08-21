(function () {
  "use strict";

  var form = document.getElementById("ask-form");
  if (!form) return;

  var csrfEl = document.querySelector("input[name='csrfmiddlewaretoken']");
  var csrf = csrfEl ? csrfEl.value : "";
  var input = document.getElementById("ask-input");
  var submit = document.getElementById("ask-submit");
  var stream = document.getElementById("chat-stream");
  var threadsList = document.getElementById("chat-threads-list");
  var newThreadBtn = document.getElementById("chat-new-thread");
  var bodyEl = document.querySelector(".chat-conversation-body");
  var scrollRoot = bodyEl || stream;
  var currentThread = null;

  function scrollToBottom() {
    if (!scrollRoot) return;
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    try {
      scrollRoot.scrollTo({ top: scrollRoot.scrollHeight, behavior: reduce ? "auto" : "smooth" });
    } catch (e) {
      scrollRoot.scrollTop = scrollRoot.scrollHeight;
    }
  }

  var T = {
    fa: {
      busy: "در حال تولید…",
      ask: "پرسیدن",
      streaming: "در حال تولید پاسخ…",
      generateFailed: "پاسخی تولید نشد: ",
      unknownError: "خطای ناشناخته",
      fetchFailed: "دریافت پاسخ ناموفق بود؛ دوباره تلاش کنید.",
      submitFailed: "ثبت پرسش ناموفق بود؛ دوباره تلاش کنید.",
      openFailed: "باز کردن گفتگو ناموفق بود.",
      noAnswer: "پاسخی دریافت نشد؛ دوباره تلاش کنید.",
      noThreads: "هنوز گفتگویی نیست.",
      count: " پرسش",
      feedbackLabel: "این پاسخ چطور بود؟",
      helpful: "پاسخ مفید بود",
      notHelpful: "پاسخ مفید نبود",
      sourcesTitle: "منابع:",
      showSource: "نمایش منبع ",
      unnamedDoc: "سند بدون نام",
      status: { pending: "در انتظار", generating: "در حال تولید", done: "پاسخ داده شده", failed: "ناموفق" },
    },
    en: {
      busy: "Generating…",
      ask: "Ask",
      streaming: "Generating answer…",
      generateFailed: "No answer was produced: ",
      unknownError: "unknown error",
      fetchFailed: "Could not fetch the answer; please try again.",
      submitFailed: "Could not submit the question; please try again.",
      openFailed: "Could not open the conversation.",
      noAnswer: "No answer was received; please try again.",
      noThreads: "No conversations yet.",
      count: " questions",
      feedbackLabel: "How was this answer?",
      helpful: "This answer was helpful",
      notHelpful: "This answer was not helpful",
      sourcesTitle: "Sources:",
      showSource: "Show source ",
      unnamedDoc: "Untitled document",
      status: { pending: "Pending", generating: "Generating", done: "Answered", failed: "Failed" },
    },
  }[document.documentElement.lang === "en" ? "en" : "fa"];

  function esc(value) {
    if (value == null) return "";
    var div = document.createElement("div");
    div.textContent = String(value);
    return div.innerHTML;
  }

  function addMessage(kind, html) {
    if (!stream) return;
    var el = document.createElement("div");
    el.className = "chat-msg chat-msg-" + kind;
    el.innerHTML = html;
    stream.appendChild(el);
    scrollToBottom();
  }

  function renderSources(sources) {
    if (!sources || !sources.length) return "";
    var items = sources
      .map(function (source) {
        var id = source.document_id != null ? source.document_id : "";
        var citation = source.citation != null ? source.citation : "";
        var title = esc(source.title || T.unnamedDoc);
        var excerpt = esc((source.excerpt || "").slice(0, 220));
        var fileUrl = source.file_url ? esc(source.file_url) : "";
        var link = fileUrl
          ? '<a href="' + fileUrl + '" target="_blank" rel="noopener">' + title + "</a>"
          : id
            ? '<a href="/admin/documents/document/' + id + '/change/">' + title + "</a>"
            : title;
        var badge = citation
          ? '<span class="chat-citation-badge">[' + citation + "]</span>"
          : "";
        return (
          '<li class="chat-source" data-source="' +
          citation +
          '">' +
          badge +
          "<strong>" +
          link +
          "</strong><p>" +
          excerpt +
          "</p></li>"
        );
      })
      .join("");
    return '<div class="chat-sources-title">' + T.sourcesTitle + '</div><ul class="chat-sources">' + items + "</ul>";
  }

  function withCitations(html, sources) {
    if (!sources || !sources.length) return html;
    var valid = {};
    sources.forEach(function (source) {
      if (source.citation != null) valid[String(source.citation)] = true;
    });
    return html.replace(/\[(\d+)\]/g, function (match, number) {
      if (!valid[number]) return match;
      return (
        '<button type="button" class="citation" data-source="' +
        number +
        '" aria-label="' +
        T.showSource +
        number +
        '">[' +
        number +
        "]</button>"
      );
    });
  }

  function renderFeedback(question) {
    var qid = question.id;
    function thumb(kind) {
      var cls = "chat-fb-" + kind + (question.feedback === kind ? " active" : "");
      var title = kind === "up" ? T.helpful : T.notHelpful;
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
      '<div class="chat-feedback"><span class="chat-feedback-label">' + T.feedbackLabel + "</span>" +
      thumb("up") +
      thumb("down") +
      "</div>"
    );
  }

  function renderAnswerHtml(question) {
    if (question.status === "failed") {
      return "<p>" + T.generateFailed + esc(question.error_message || T.unknownError) + "</p>";
    }
    return (
      "<p>" +
      withCitations(esc(question.answer), question.sources) +
      "</p>" +
      renderSources(question.sources) +
      renderFeedback(question)
    );
  }

  function renderAnswer(question) {
    addMessage(
      question.status === "failed" ? "error" : "answer",
      renderAnswerHtml(question)
    );
  }

  function setBusy(busy) {
    input.disabled = busy;
    submit.disabled = busy;
    submit.textContent = busy ? T.busy : T.ask;
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

  function openStream(questionId, container) {
    var pending = document.createElement("p");
    pending.className = "chat-streaming";
    pending.textContent = T.streaming;
    container.appendChild(pending);

    fetch("/api/questions/" + questionId + "/stream/", {
      headers: { "X-CSRFToken": csrf },
    }).then(function (response) {
      if (response.status === 401 || response.status === 403) {
        window.location.href = "/admin/login/?next=" + encodeURIComponent("/chat/");
        throw new Error("unauthorized");
      }
      if (!response.body) throw new Error("no stream");
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";

      var tokenQueue = "";
      var tokenRaf = null;
      function flushTokens() {
        tokenRaf = null;
        if (tokenQueue && pending.isConnected) {
          pending.textContent += tokenQueue;
          tokenQueue = "";
        }
      }
      function handle(frame) {
        var line = frame.trim();
        if (line.indexOf("data:") !== 0) return;
        var data;
        try {
          data = JSON.parse(line.slice(5).trim());
        } catch (e) {
          return;
        }
        if (data.type === "token") {
          if (!pending.isConnected) return;
          tokenQueue += data.text;
          if (!tokenRaf) {
            tokenRaf = window.requestAnimationFrame(function () {
              flushTokens();
              scrollToBottom();
            });
          }
        } else if (data.type === "done") {
          setBusy(false);
          container.innerHTML = renderAnswerHtml(data.question);
          scrollToBottom();
        } else if (data.type === "error" || data.type === "timeout") {
          setBusy(false);
          container.innerHTML = "<p>" + T.noAnswer + "</p>";
          scrollToBottom();
        }
      }

      function pump() {
        return reader.read().then(function (result) {
          if (result.done) {
            setBusy(false);
            return;
          }
          buffer += decoder.decode(result.value, { stream: true });
          var frames = buffer.split("\n\n");
          buffer = frames.pop();
          frames.forEach(handle);
          return pump();
        });
      }

      return pump();
    }).catch(function () {
      setBusy(false);
      if (pending.isConnected) {
        container.innerHTML = "<p>" + T.fetchFailed + "</p>";
      }
    });
  }

  function renderThread(thread) {
    api("/api/threads/" + thread.id + "/").then(function (data) {
      stream.innerHTML = "";
      currentThread = thread.id;
      (data.questions || []).forEach(function (question) {
        addMessage("question", "<p>" + esc(question.question) + "</p>");
        if (question.status === "pending" || question.status === "generating") {
          addMessage("answer", '<p class="chat-streaming">' + T.streaming + "</p>");
        } else {
          renderAnswer(question);
        }
      });
      var btn = threadsList.querySelector('[data-thread="' + thread.id + '"]');
      if (btn) btn.classList.add("active");
      input.focus();
      scrollToBottom();
    }).catch(function () {
      addMessage("error", "<p>" + T.openFailed + "</p>");
    });
  }

  function loadThreads() {
    if (!threadsList) return;
    api("/api/threads/").then(function (data) {
      var items = data.results || [];
      if (!items.length) {
        threadsList.innerHTML = '<li class="chat-empty">' + T.noThreads + "</li>";
        return;
      }
      threadsList.innerHTML = items
        .map(function (thread) {
          var active = currentThread === thread.id ? " active" : "";
          return (
            '<li><button type="button" class="chat-thread' +
            active +
            '" data-thread="' +
            thread.id +
            '"><span class="chat-thread-title">' +
            esc(thread.title) +
            '</span><span class="chat-thread-meta">' +
            thread.question_count +
            T.count +
            "</span></button></li>"
          );
        })
        .join("");
    });
  }

  if (stream) {
    stream.addEventListener("click", function (event) {
      var citation = event.target.closest("button.citation[data-source]");
      if (citation) {
        var number = citation.getAttribute("data-source");
        var sources = stream.querySelectorAll(".chat-source");
        var active = null;
        sources.forEach(function (source) {
          if (source.getAttribute("data-source") === number) {
            active = source;
          } else {
            source.classList.remove("chat-source-active");
          }
        });
        if (!active) return;
        active.classList.add("chat-source-active");
        var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        active.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
        return;
      }
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

  if (threadsList) {
    threadsList.addEventListener("click", function (event) {
      var btn = event.target.closest("button[data-thread]");
      if (!btn) return;
      threadsList.querySelectorAll("button").forEach(function (b) {
        b.classList.remove("active");
      });
      renderThread({ id: btn.getAttribute("data-thread") });
    });
  }

  if (newThreadBtn) {
    newThreadBtn.addEventListener("click", function () {
      currentThread = null;
      stream.innerHTML = "";
      threadsList.querySelectorAll("button").forEach(function (b) {
        b.classList.remove("active");
      });
      input.focus();
    });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var text = (input.value || "").trim();
    if (!text) return;

    setBusy(true);
    addMessage("question", "<p>" + esc(text) + "</p>");
    input.value = "";

    var payload = { question: text };
    if (currentThread) payload.thread = currentThread;

    api("/api/questions/", {
      method: "POST",
      body: JSON.stringify(payload),
    }).then(function (question) {
      if (question.thread) currentThread = question.thread;
      loadThreads();
      var container = document.createElement("div");
      container.className = "chat-msg chat-msg-answer";
      stream.appendChild(container);
      openStream(question.id, container);
    }).catch(function () {
      setBusy(false);
      addMessage("error", "<p>" + T.submitFailed + "</p>");
    });
  });

  loadThreads();
})();