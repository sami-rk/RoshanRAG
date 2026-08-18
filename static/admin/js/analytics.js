(function () {
  "use strict";

  var dataNode = document.getElementById("analytics-data");
  if (!dataNode || typeof Chart === "undefined") return;

  var data = JSON.parse(dataNode.textContent);

  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue("--accent").trim() || "#2563eb";
  var grid = style.getPropertyValue("--border-color").trim() || "rgba(127, 127, 127, 0.25)";
  var text = style.getPropertyValue("--body-fg").trim() || "#6b7280";

  Chart.defaults.color = text;
  Chart.defaults.borderColor = grid;

  var dateFormatter = new Intl.DateTimeFormat("fa-IR", {
    month: "short",
    day: "numeric",
  });

  function persianDate(iso) {
    return dateFormatter.format(new Date(iso + "T00:00:00"));
  }

  var questionsChart = new Chart(document.getElementById("chart-questions"), {
    type: "line",
    data: {
      labels: data.questions_per_day.map(function (d) { return persianDate(d.date); }),
      datasets: [{
        label: "پرسش",
        data: data.questions_per_day.map(function (d) { return d.count; }),
        borderColor: accent,
        backgroundColor: accent + "33",
        fill: true,
        tension: 0.3,
        pointRadius: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } },
      },
      plugins: { legend: { display: false } },
    },
  });

  new Chart(document.getElementById("chart-documents"), {
    type: "doughnut",
    data: {
      labels: ["آماده", "در انتظار", "ناموفق"],
      datasets: [{
        data: [
          data.documents_ready,
          data.documents_pending,
          data.documents_failed,
        ],
        backgroundColor: ["#22c55e", "#f59e0b", "#ef4444"],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: { legend: { position: "bottom" } },
    },
  });

  new Chart(document.getElementById("chart-feedback"), {
    type: "bar",
    data: {
      labels: ["مفید", "نامفید"],
      datasets: [{
        data: [data.feedback_counts.up, data.feedback_counts.down],
        backgroundColor: ["#22c55e", "#ef4444"],
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } },
      },
      plugins: { legend: { display: false } },
    },
  });
})();
