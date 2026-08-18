(function () {
  "use strict";

  var form = document.getElementById("demo-form");
  if (!form) return;

  var input = document.getElementById("demo-input");
  var answerBox = document.getElementById("demo-answer");
  var busy = false;

  function esc(text) {
    var holder = document.createElement("div");
    holder.textContent = text;
    return holder.innerHTML;
  }

  function poll(id, token) {
    var deadline = Date.now() + 120000;
    function attempt() {
      return fetch(
        "/api/questions/" + id + "/demo/?token=" + encodeURIComponent(token)
      )
        .then(function (response) {
          if (!response.ok) throw new Error("خطا در دریافت پاسخ");
          return response.json();
        })
        .then(function (question) {
          if (question.status === "done" || question.status === "failed") {
            return question;
          }
          if (Date.now() > deadline) {
            throw new Error("زمان پاسخ‌دهی به پایان رسید");
          }
          return new Promise(function (resolve) {
            setTimeout(function () {
              resolve(attempt());
            }, 2000);
          });
        });
    }
    return attempt();
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (busy) return;
    var text = input.value.trim();
    if (!text) return;

    busy = true;
    input.disabled = true;
    answerBox.hidden = false;
    answerBox.innerHTML = '<p class="demo-pending">در حال آماده‌سازی پاسخ…</p>';

    fetch("/api/questions/demo_ask/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text }),
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) throw new Error(result.data.detail || "خطا در ثبت پرسش");
        return poll(result.data.id, result.data.demo_token);
      })
      .then(function (question) {
        if (question.status === "failed") {
          answerBox.innerHTML =
            '<p class="demo-error">' +
            esc(question.error_message || "خطا در تولید پاسخ") +
            "</p>";
          return;
        }
        var sources = (question.sources || [])
          .map(function (source) {
            return '<span class="demo-source">' + esc(source.title) + "</span>";
          })
          .join("");
        answerBox.innerHTML =
          "<p>" + esc(question.answer) + "</p>" +
          (sources
            ? '<div class="demo-sources"><span class="demo-sources-label">منابع:</span>' +
              sources +
              "</div>"
            : "");
      })
      .catch(function (error) {
        answerBox.innerHTML =
          '<p class="demo-error">' +
          esc(error && error.message ? error.message : String(error)) +
          "</p>";
      })
      .then(function () {
        busy = false;
        input.disabled = false;
      });
  });
})();