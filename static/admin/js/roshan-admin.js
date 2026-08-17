(function () {
  "use strict";

  var reduceMotion = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
  var isTouch = window.matchMedia
    ? window.matchMedia("(hover: none)").matches
    : false;

  function setupTilt() {
    var cards = document.querySelectorAll("[data-tilt]");
    Array.prototype.forEach.call(cards, function (card) {
      card.addEventListener(
        "mouseenter",
        function () {
          card.style.transition = "transform 120ms ease-out";
        },
        { passive: true }
      );
      card.addEventListener(
        "mousemove",
        function (event) {
          var rect = card.getBoundingClientRect();
          var px = (event.clientX - rect.left) / rect.width;
          var py = (event.clientY - rect.top) / rect.height;
          card.style.setProperty("--rx", ((py - 0.5) * -7).toFixed(2) + "deg");
          card.style.setProperty("--ry", ((px - 0.5) * 9).toFixed(2) + "deg");
        },
        { passive: true }
      );
      card.addEventListener(
        "mouseleave",
        function () {
          card.style.transition = "transform 500ms cubic-bezier(0.22, 1, 0.36, 1)";
          card.style.setProperty("--rx", "0deg");
          card.style.setProperty("--ry", "0deg");
        },
        { passive: true }
      );
    });
  }

  function animateCount(el, target) {
    var duration = 650;
    var start = null;
    function step(timestamp) {
      if (!start) start = timestamp;
      var progress = Math.min((timestamp - start) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.round(target * eased).toLocaleString("en-US");
      if (progress < 1) {
        window.requestAnimationFrame(step);
      } else {
        el.textContent = target.toLocaleString("en-US");
      }
    }
    window.requestAnimationFrame(step);
  }

  function setupCounters() {
    var counters = document.querySelectorAll("[data-count]");
    Array.prototype.forEach.call(counters, function (el) {
      var target = parseInt(el.getAttribute("data-count"), 10);
      if (isNaN(target)) return;
      el.textContent = "0";
      animateCount(el, target);
    });
  }

  function ready(fn) {
    if (document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  ready(function () {
    if (reduceMotion) {
      return;
    }
    if (!isTouch) {
      setupTilt();
    }
    setupCounters();
  });
})();