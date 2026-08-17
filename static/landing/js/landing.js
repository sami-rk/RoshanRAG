(function () {
    "use strict";

    var root = document.documentElement;
    var STORAGE_KEY = "roshan-theme";

    function resolvedTheme() {
        return root.getAttribute("data-theme") ||
            (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    }

    function applyTheme(theme) {
        if (theme === "dark") {
            root.setAttribute("data-theme", "dark");
        } else {
            root.setAttribute("data-theme", "light");
        }
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (e) {}
    }

    function initTheme() {
        var saved = null;
        try {
            saved = localStorage.getItem(STORAGE_KEY);
        } catch (e) {}
        if (saved === "light" || saved === "dark") {
            root.setAttribute("data-theme", saved);
        }
        var toggle = document.querySelector(".theme-toggle");
        if (toggle) {
            toggle.addEventListener("click", function () {
                applyTheme(resolvedTheme() === "dark" ? "light" : "dark");
            });
        }
    }

    function prefersReducedMotion() {
        return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    function countUp(el) {
        var target = parseInt(el.getAttribute("data-count"), 10) || 0;
        var duration = 700;
        var start = null;
        if (prefersReducedMotion()) {
            el.textContent = target;
            return;
        }
        function frame(ts) {
            if (!start) start = ts;
            var progress = Math.min((ts - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(target * eased);
            if (progress < 1) {
                window.requestAnimationFrame(frame);
            }
        }
        window.requestAnimationFrame(frame);
    }

    function initCountUp() {
        var chips = document.querySelectorAll("[data-count]");
        for (var i = 0; i < chips.length; i++) {
            countUp(chips[i]);
        }
    }

    function initNav() {
        var toggle = document.querySelector(".nav-toggle");
        var links = document.querySelector(".nav-links");
        if (!toggle || !links) return;
        toggle.addEventListener("click", function () {
            var open = links.classList.toggle("open");
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        });
        var items = links.querySelectorAll("a");
        for (var i = 0; i < items.length; i++) {
            items[i].addEventListener("click", function () {
                links.classList.remove("open");
                toggle.setAttribute("aria-expanded", "false");
            });
        }
    }

    function onReady(fn) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", fn);
        } else {
            fn();
        }
    }

    onReady(function () {
        initTheme();
        initCountUp();
        initNav();
    });
})();