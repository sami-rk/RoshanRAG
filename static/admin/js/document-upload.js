(function () {
  "use strict";

  var dropzone = document.getElementById("dropzone");
  var input = document.getElementById("file-input");
  var list = document.getElementById("file-list");
  var button = document.getElementById("upload-button");
  var status = document.getElementById("upload-status");
  var results = document.getElementById("upload-results");
  if (!dropzone || !input || !list || !button || !status || !results) return;

  var files = [];

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function escapeHtml(text) {
    var holder = document.createElement("div");
    holder.textContent = text;
    return holder.innerHTML;
  }

  function updateList() {
    list.innerHTML = "";
    files.forEach(function (file, index) {
      var item = document.createElement("li");
      item.className = "upload-file-item";
      item.textContent = file.name + " — " + formatSize(file.size);
      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "upload-file-remove";
      remove.setAttribute("aria-label", "حذف " + file.name);
      remove.textContent = "×";
      remove.addEventListener("click", function () {
        files.splice(index, 1);
        updateList();
      });
      item.appendChild(remove);
      list.appendChild(item);
    });
    button.disabled = files.length === 0;
  }

  function addFiles(selected) {
    for (var i = 0; i < selected.length; i++) {
      var file = selected[i];
      var name = file.name.toLowerCase();
      if (name.endsWith(".docx") || name.endsWith(".txt")) {
        files.push(file);
      }
    }
    updateList();
  }

  dropzone.addEventListener("click", function () {
    input.click();
  });
  dropzone.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
  input.addEventListener("change", function () {
    addFiles(input.files);
    input.value = "";
  });

  ["dragover", "dragenter"].forEach(function (eventName) {
    dropzone.addEventListener(eventName, function (event) {
      event.preventDefault();
      dropzone.classList.add("dropzone-active");
    });
  });
  ["dragleave", "drop"].forEach(function (eventName) {
    dropzone.addEventListener(eventName, function (event) {
      event.preventDefault();
      dropzone.classList.remove("dropzone-active");
    });
  });
  dropzone.addEventListener("drop", function (event) {
    addFiles(event.dataTransfer.files);
  });

  function csrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function renderResults(data) {
    var created = data.created || [];
    var errors = data.errors || [];
    var html = "";
    created.forEach(function (doc) {
      html +=
        '<div class="upload-result upload-result-ok"><strong>' +
        escapeHtml(doc.title) +
        "</strong><span class=\"pill pill-pending\">در صف پردازش</span></div>";
    });
    errors.forEach(function (entry) {
      var messages = Object.values(entry.errors || {}).flat().join("، ");
      html +=
        '<div class="upload-result upload-result-err"><strong>' +
        escapeHtml(entry.file) +
        "</strong><span>" +
        escapeHtml(messages) +
        "</span></div>";
    });
    results.innerHTML = html;
    files = [];
    updateList();
    status.textContent =
      created.length + " سند بارگذاری شد و " + errors.length + " سند رد شد";
  }

  button.addEventListener("click", function () {
    if (files.length === 0) return;
    button.disabled = true;
    status.textContent = "در حال بارگذاری…";
    var formData = new FormData();
    files.forEach(function (file) {
      formData.append("files", file);
    });
    fetch("/api/documents/batch/", {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken() },
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { ok: response.ok, data: data };
        });
      })
      .then(function (result) {
        renderResults(result.data);
      })
      .catch(function () {
        status.textContent = "خطا در برقراری ارتباط با سرور";
      })
      .then(function () {
        button.disabled = false;
      });
  });
})();