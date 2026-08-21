(function () {
    "use strict";

    var root = document.documentElement;
    var STORAGE_KEY = "roshan-theme";
    var PERSIAN_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

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
        var digit = el.querySelector("em") || el;
        function setValue(value) {
            digit.textContent = toPersianDigits(value);
        }
        if (prefersReducedMotion()) {
            setValue(target);
            return;
        }
        function frame(ts) {
            if (!start) start = ts;
            var progress = Math.min((ts - start) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3);
            setValue(Math.round(target * eased));
            if (progress < 1) {
                window.requestAnimationFrame(frame);
            }
        }
        window.requestAnimationFrame(frame);
    }

    function toPersianDigits(value) {
        return String(value).replace(/\d/g, function (d) {
            return PERSIAN_DIGITS[d];
        });
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
            toggle.classList.toggle("open", open);
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        });
        var items = links.querySelectorAll("a");
        for (var i = 0; i < items.length; i++) {
            items[i].addEventListener("click", function () {
                links.classList.remove("open");
                toggle.classList.remove("open");
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
            el.style.willChange = "opacity, translate";
            el.classList.add("in-view");
            el.addEventListener("transitionend", function handler(e) {
                if (e.target !== el) return;
                el.style.willChange = "";
                el.removeEventListener("transitionend", handler);
            });
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
    }

    function canHover() {
        return window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    }

    function setupTilt(el) {
        if (prefersReducedMotion() || !canHover()) return;
        var ticking = false;
        var latest = null;
        var rect = null;
        function update() {
            ticking = false;
            if (!latest || !rect) return;
            var x = (latest.clientX - rect.left) / rect.width - 0.5;
            var y = (latest.clientY - rect.top) / rect.height - 0.5;
            el.style.setProperty("--rx", (-y * 7).toFixed(2) + "deg");
            el.style.setProperty("--ry", (x * 7).toFixed(2) + "deg");
            el.style.setProperty("--mx", (((latest.clientX - rect.left) / rect.width) * 100).toFixed(2) + "%");
            el.style.setProperty("--my", (((latest.clientY - rect.top) / rect.height) * 100).toFixed(2) + "%");
        }
        el.addEventListener("pointerenter", function () {
            el.classList.add("is-tilting");
            rect = el.getBoundingClientRect();
        });
        el.addEventListener("pointermove", function (e) {
            latest = e;
            if (!ticking) {
                ticking = true;
                window.requestAnimationFrame(update);
            }
        });
        el.addEventListener("pointerleave", function () {
            latest = null;
            ticking = false;
            el.classList.remove("is-tilting");
            el.style.setProperty("--rx", "0deg");
            el.style.setProperty("--ry", "0deg");
        });
        if ("ResizeObserver" in window) {
            var ro = new ResizeObserver(function () {
                rect = el.getBoundingClientRect();
            });
            ro.observe(el);
        }
    }

    function initTilt() {
        var cards = document.querySelectorAll("[data-tilt]");
        for (var i = 0; i < cards.length; i++) {
            setupTilt(cards[i]);
        }
    }

    function setupMagnetic(el) {
        if (prefersReducedMotion() || !canHover()) return;
        var ticking = false;
        var latest = null;
        var rect = null;
        function update() {
            ticking = false;
            if (!latest || !rect) return;
            var x = latest.clientX - rect.left - rect.width / 2;
            var y = latest.clientY - rect.top - rect.height / 2;
            var dx = Math.max(-9, Math.min(9, x * 0.3));
            var dy = Math.max(-9, Math.min(9, y * 0.3));
            el.style.translate = dx.toFixed(1) + "px " + dy.toFixed(1) + "px";
        }
        el.addEventListener("pointerenter", function () {
            rect = el.getBoundingClientRect();
        });
        el.addEventListener("pointermove", function (e) {
            latest = e;
            if (!ticking) {
                ticking = true;
                window.requestAnimationFrame(update);
            }
        });
        el.addEventListener("pointerleave", function () {
            latest = null;
            ticking = false;
            el.style.translate = "0px 0px";
        });
        if ("ResizeObserver" in window) {
            var ro = new ResizeObserver(function () {
                rect = el.getBoundingClientRect();
            });
            ro.observe(el);
        }
    }

    function initMagnetic() {
        var els = document.querySelectorAll(".magnetic");
        for (var i = 0; i < els.length; i++) {
            setupMagnetic(els[i]);
        }
    }

    function initPauseOffscreen() {
        var els = document.querySelectorAll(".marquee, .elegant-dark-bg");
        if (!els.length || !("IntersectionObserver" in window)) return;
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                entry.target.classList.toggle("paused", !entry.isIntersecting);
            });
        }, { threshold: 0 });
        for (var i = 0; i < els.length; i++) {
            io.observe(els[i]);
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
        initReveal();
        initTilt();
        initMagnetic();
        initPauseOffscreen();
    });
})();