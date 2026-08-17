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

    function initReveal() {
        var els = document.querySelectorAll("[data-reveal]");
        if (!els.length) return;
        document.documentElement.classList.add("js-anim");
        if (prefersReducedMotion() || !("IntersectionObserver" in window)) {
            for (var i = 0; i < els.length; i++) {
                els[i].classList.add("in-view");
            }
            return;
        }
        var groups = {};
        for (var j = 0; j < els.length; j++) {
            var parent = els[j].parentNode;
            var list = groups[parent] || (groups[parent] = []);
            list.push(els[j]);
        }
        Object.keys(groups).forEach(function (key) {
            var list = groups[key];
            for (var k = 0; k < list.length; k++) {
                list[k].style.setProperty("--i", k);
            }
        });
        function show(el) {
            el.classList.add("in-view");
        }
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    show(entry.target);
                    io.unobserve(entry.target);
                }
            });
        }, { threshold: 0, rootMargin: "0px 0px 15% 0px" });
        for (var m = 0; m < els.length; m++) {
            io.observe(els[m]);
        }
        var timer = null;
        window.addEventListener("scroll", function () {
            if (timer) return;
            timer = setTimeout(function () {
                timer = null;
                var vh = window.innerHeight;
                for (var n = 0; n < els.length; n++) {
                    var el = els[n];
                    if (el.classList.contains("in-view")) continue;
                    if (el.getBoundingClientRect().top <= vh + 80) {
                        show(el);
                        io.unobserve(el);
                    }
                }
            }, 90);
        }, { passive: true });
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
        initReveal();
    });
})();