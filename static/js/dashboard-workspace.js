document.addEventListener("DOMContentLoaded", function () {
    const shell = document.getElementById("dashboardCanvasShell");
    const canvas = document.getElementById("dashboardCanvas");
    if (!shell || !canvas) return;

    const customizeBtn = document.getElementById("dashboardCustomizeBtn");
    const resetBtn = document.getElementById("dashboardResetBtn");
    const exportBtn = document.getElementById("dashboardExportBtn");
    const modePill = document.getElementById("dashboardLayoutModePill");
    const modeText = document.getElementById("dashboardLayoutModeText");

    const saveUrl = shell.dataset.saveUrl || "";
    const defaultLayout = JSON.parse(shell.dataset.defaultLayout || "[]");
    const storageKey = "ums-dashboard-layout-v8";
    const customizeKey = "ums-dashboard-customize-v8";

    const SNAP = 8;
    const MIN_W = 240;
    const MIN_H = 100;

    let customizeMode = localStorage.getItem(customizeKey) === "true";
    let interaction = null;
    let zCounter = 20;
    let resizeTicking = false;
    let lastResponsiveMode = null;

    function snap(value) {
        return Math.round(value / SNAP) * SNAP;
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function getResponsiveMode() {
        const width = window.innerWidth;

        if (width < 768) return "mobile";
        if (width < 992) return "tablet";
        if (width < 1200) return "small-desktop";
        if (width < 1400) return "compact-canvas";
        if (width < 1600) return "desktop";
        return "wide";
    }

    function isCanvasMode() {
        const mode = getResponsiveMode();
        return mode === "compact-canvas" || mode === "desktop" || mode === "wide";
    }

    function getWidgets() {
        return Array.from(canvas.querySelectorAll(".dashboard-widget"));
    }

    function getWidgetById(widgetId) {
        return canvas.querySelector(`.dashboard-widget[data-widget-id="${widgetId}"]`);
    }

    function elevate(widget) {
        zCounter += 1;
        widget.style.zIndex = String(zCounter);
    }

    function clearWidgetFrameStyles(widget) {
        widget.style.left = "";
        widget.style.top = "";
        widget.style.width = "";
        widget.style.height = "";
    }

    function getStoredFrame(widget) {
        return {
            x: parseFloat(widget.dataset.desktopX || widget.dataset.x || "0"),
            y: parseFloat(widget.dataset.desktopY || widget.dataset.y || "0"),
            w: parseFloat(widget.dataset.desktopW || widget.dataset.w || "320"),
            h: parseFloat(widget.dataset.desktopH || widget.dataset.h || "180")
        };
    }

    function setStoredFrame(widget, frame) {
        widget.dataset.desktopX = String(frame.x);
        widget.dataset.desktopY = String(frame.y);
        widget.dataset.desktopW = String(frame.w);
        widget.dataset.desktopH = String(frame.h);

        widget.dataset.x = String(frame.x);
        widget.dataset.y = String(frame.y);
        widget.dataset.w = String(frame.w);
        widget.dataset.h = String(frame.h);
    }

    function updateAdaptiveClasses(widget) {
        const w = parseFloat(widget.dataset.desktopW || widget.dataset.w || "320");
        const h = parseFloat(widget.dataset.desktopH || widget.dataset.h || "180");
        const card = widget.querySelector(".dashboard-widget-card");
        if (!card) return;

        card.classList.toggle("widget-xs", w < 300);
        card.classList.toggle("widget-sm", w >= 300 && w < 420);
        card.classList.toggle("widget-md", w >= 420 && w < 700);
        card.classList.toggle("widget-lg", w >= 700);

        card.classList.toggle("widget-short", h < 150);
        card.classList.toggle("widget-mid", h >= 150 && h < 260);
        card.classList.toggle("widget-tall", h >= 260);
    }

    function updateCanvasHeight() {
        if (!isCanvasMode()) {
            canvas.style.height = "auto";
            return;
        }

        let maxBottom = 700;

        getWidgets().forEach((widget) => {
            const frame = getStoredFrame(widget);
            maxBottom = Math.max(maxBottom, frame.y + frame.h + 40);
        });

        canvas.style.height = `${maxBottom}px`;
    }

    function normalizeFrameForCanvas(frame) {
        const shellWidth = canvas.clientWidth;
        const maxWidth = Math.max(MIN_W, shellWidth);

        const w = clamp(snap(frame.w), MIN_W, maxWidth);
        const h = clamp(snap(frame.h), MIN_H, 1600);
        const x = clamp(snap(frame.x), 0, Math.max(0, shellWidth - w));
        const y = Math.max(0, snap(frame.y));

        return { x, y, w, h };
    }

    function applyWidgetFrame(widget, frame, persist = true) {
        const normalized = normalizeFrameForCanvas(frame);

        if (persist) {
            setStoredFrame(widget, normalized);
        }

        if (!isCanvasMode()) {
            clearWidgetFrameStyles(widget);
            updateAdaptiveClasses(widget);
            return;
        }

        widget.style.left = `${normalized.x}px`;
        widget.style.top = `${normalized.y}px`;
        widget.style.width = `${normalized.w}px`;
        widget.style.height = `${normalized.h}px`;

        updateAdaptiveClasses(widget);
    }

    function serializeLayout() {
        return getWidgets().map((widget) => ({
            id: widget.dataset.widgetId,
            x: parseFloat(widget.dataset.desktopX || widget.dataset.x || "0"),
            y: parseFloat(widget.dataset.desktopY || widget.dataset.y || "0"),
            w: parseFloat(widget.dataset.desktopW || widget.dataset.w || "320"),
            h: parseFloat(widget.dataset.desktopH || widget.dataset.h || "180")
        }));
    }

    function applyLayout(layout) {
        if (!Array.isArray(layout) || !layout.length) return;

        layout.forEach((item) => {
            const widget = getWidgetById(item.id);
            if (!widget) return;
            applyWidgetFrame(widget, item, true);
        });

        updateCanvasHeight();
    }

    function saveLocal() {
        localStorage.setItem(storageKey, JSON.stringify(serializeLayout()));
    }

    function saveServer() {
        if (!saveUrl) return;

        fetch(saveUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                layout: serializeLayout()
            })
        }).catch((error) => {
            console.warn("Dashboard save failed", error);
        });
    }

    function loadInitialLayout() {
        try {
            const localLayout = JSON.parse(localStorage.getItem(storageKey));
            if (Array.isArray(localLayout) && localLayout.length) {
                applyLayout(localLayout);
                return;
            }
        } catch (error) {
            console.warn("Local dashboard layout parse failed", error);
        }

        if (Array.isArray(window.UMS_DASHBOARD_LAYOUT) && window.UMS_DASHBOARD_LAYOUT.length) {
            applyLayout(window.UMS_DASHBOARD_LAYOUT);
            return;
        }

        applyLayout(defaultLayout);
    }

    function updateModeUI() {
        const activeEditMode = customizeMode && isCanvasMode();

        document.body.classList.toggle("dashboard-customize-mode", activeEditMode);

        if (modePill) {
            modePill.classList.toggle("editing", activeEditMode);
        }

        if (modeText) {
            modeText.textContent = isCanvasMode()
                ? (activeEditMode ? "Layout editing" : "Organized view")
                : "Responsive view";
        }

        if (customizeBtn) {
            if (!isCanvasMode()) {
                customizeBtn.disabled = true;
                customizeBtn.classList.add("is-disabled");
                customizeBtn.textContent = "Customize Layout";
            } else {
                customizeBtn.disabled = false;
                customizeBtn.classList.remove("is-disabled");
                customizeBtn.textContent = activeEditMode ? "Done" : "Customize Layout";
            }
        }
    }

    function refreshWidgetMetrics() {
        getWidgets().forEach((widget) => {
            updateAdaptiveClasses(widget);
        });
    }

    function refreshCanvasLayout() {
        if (!isCanvasMode()) {
            getWidgets().forEach((widget) => {
                clearWidgetFrameStyles(widget);
                updateAdaptiveClasses(widget);
            });
            canvas.style.height = "auto";
            return;
        }

        getWidgets().forEach((widget) => {
            const stored = getStoredFrame(widget);
            const normalized = normalizeFrameForCanvas(stored);

            setStoredFrame(widget, normalized);

            widget.style.left = `${normalized.x}px`;
            widget.style.top = `${normalized.y}px`;
            widget.style.width = `${normalized.w}px`;
            widget.style.height = `${normalized.h}px`;

            updateAdaptiveClasses(widget);
        });

        updateCanvasHeight();
    }

    function refreshDashboardUI() {
        refreshWidgetMetrics();
        refreshCanvasLayout();
        updateModeUI();
    }

    function liveResizeRefresh() {
        if (resizeTicking) return;

        resizeTicking = true;
        requestAnimationFrame(() => {
            const currentMode = getResponsiveMode();

            if (currentMode !== lastResponsiveMode) {
                lastResponsiveMode = currentMode;
            }

            refreshDashboardUI();
            resizeTicking = false;
        });
    }

    function setCustomizeMode(enabled) {
        customizeMode = enabled;
        localStorage.setItem(customizeKey, String(enabled));

        refreshDashboardUI();

        if (typeof gsap !== "undefined" && isCanvasMode()) {
            gsap.fromTo(
                ".dashboard-widget-card",
                { scale: 0.995 },
                {
                    scale: 1,
                    duration: 0.2,
                    stagger: 0.02,
                    ease: "power2.out"
                }
            );
        }
    }

    function animateIntro() {
        if (typeof gsap === "undefined") return;

        gsap.set(".dashboard-header-left > *", { opacity: 1, y: 0 });
        gsap.set(".dashboard-header-right > *", { opacity: 1, y: 0 });
        gsap.set(".dashboard-widget", { opacity: 1, scale: 1 });

        gsap.from(".dashboard-header-left > *", {
            opacity: 0,
            y: 10,
            duration: 0.42,
            stagger: 0.05,
            ease: "power2.out"
        });

        gsap.from(".dashboard-header-right > *", {
            opacity: 0,
            y: 8,
            duration: 0.32,
            stagger: 0.04,
            ease: "power2.out",
            delay: 0.08
        });

        gsap.from(".dashboard-widget", {
            opacity: 0,
            y: 14,
            scale: 0.992,
            duration: 0.45,
            stagger: 0.035,
            ease: "power3.out",
            delay: 0.1
        });
    }

    function initHoverMotion() {
        if (typeof gsap === "undefined") return;

        document.querySelectorAll(".dashboard-widget-card").forEach((card) => {
            card.addEventListener("mouseenter", function () {
                if (interaction || !isCanvasMode()) return;
                gsap.to(card, {
                    y: -3,
                    duration: 0.16,
                    ease: "power2.out"
                });
            });

            card.addEventListener("mouseleave", function () {
                if (interaction || !isCanvasMode()) return;
                gsap.to(card, {
                    y: 0,
                    duration: 0.16,
                    ease: "power2.out"
                });
            });
        });
    }

    function startDrag(e, widget) {
        if (!customizeMode || !isCanvasMode()) return;

        const rect = widget.getBoundingClientRect();
        const canvasRect = canvas.getBoundingClientRect();

        interaction = {
            type: "drag",
            widget,
            offsetX: e.clientX - rect.left,
            offsetY: e.clientY - rect.top,
            canvasRect
        };

        elevate(widget);
        document.body.classList.add("dashboard-dragging");
    }

    function startResize(e, widget, axis) {
        if (!customizeMode || !isCanvasMode()) return;

        const stored = getStoredFrame(widget);

        interaction = {
            type: "resize",
            widget,
            axis,
            startX: e.clientX,
            startY: e.clientY,
            startW: stored.w,
            startH: stored.h,
            startLeft: stored.x,
            startTop: stored.y
        };

        elevate(widget);
        document.body.classList.add("dashboard-resizing");
    }

    function onPointerMove(e) {
        if (!interaction || !isCanvasMode()) return;

        if (interaction.type === "drag") {
            const { widget, offsetX, offsetY, canvasRect } = interaction;
            const shellWidth = canvas.clientWidth;

            const stored = getStoredFrame(widget);
            const w = stored.w;
            const h = stored.h;

            const nextX = clamp(e.clientX - canvasRect.left - offsetX, 0, Math.max(0, shellWidth - w));
            const nextY = Math.max(0, e.clientY - canvasRect.top - offsetY);

            const nextFrame = {
                x: nextX,
                y: nextY,
                w,
                h
            };

            applyWidgetFrame(widget, nextFrame, true);
            updateCanvasHeight();
        }

        if (interaction.type === "resize") {
            const { widget, axis, startX, startY, startW, startH, startLeft, startTop } = interaction;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;

            let nextW = startW;
            let nextH = startH;

            if (axis === "x" || axis === "xy") {
                nextW = startW + dx;
            }

            if (axis === "y" || axis === "xy") {
                nextH = startH + dy;
            }

            const nextFrame = {
                x: startLeft,
                y: startTop,
                w: nextW,
                h: nextH
            };

            applyWidgetFrame(widget, nextFrame, true);
            updateCanvasHeight();
        }
    }

    function endInteraction() {
        if (!interaction) return;

        const widget = interaction.widget;
        interaction = null;

        document.body.classList.remove("dashboard-dragging");
        document.body.classList.remove("dashboard-resizing");

        refreshDashboardUI();
        saveLocal();
        saveServer();

        if (typeof gsap !== "undefined" && widget && isCanvasMode()) {
            gsap.fromTo(
                widget,
                { scale: 0.996 },
                { scale: 1, duration: 0.18, ease: "power2.out" }
            );
        }
    }

    function initInteractions() {
        getWidgets().forEach((widget) => {
            const dragHandle = widget.querySelector(".widget-drag-handle");
            const resizeHandles = widget.querySelectorAll(".widget-resize");

            if (dragHandle) {
                dragHandle.addEventListener("mousedown", function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    startDrag(e, widget);
                });
            }

            resizeHandles.forEach((handle) => {
                handle.addEventListener("mousedown", function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    startResize(e, widget, handle.dataset.resize || "xy");
                });
            });

            widget.addEventListener("mousedown", function () {
                elevate(widget);
            });
        });

        window.addEventListener("mousemove", onPointerMove);
        window.addEventListener("mouseup", endInteraction);
    }

    function resetLayout() {
        localStorage.removeItem(storageKey);
        applyLayout(defaultLayout);
        refreshDashboardUI();
        saveLocal();
        saveServer();
    }

    loadInitialLayout();
    animateIntro();
    initHoverMotion();
    initInteractions();
    refreshDashboardUI();
    lastResponsiveMode = getResponsiveMode();

    if (customizeBtn) {
        customizeBtn.addEventListener("click", function () {
            if (!isCanvasMode()) return;
            setCustomizeMode(!customizeMode);
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener("click", function () {
            setCustomizeMode(false);
            resetLayout();
        });
    }

    if (exportBtn) {
        exportBtn.addEventListener("click", function () {
            window.print();
        });
    }

    window.addEventListener("resize", liveResizeRefresh);
    window.addEventListener("orientationchange", liveResizeRefresh);

    if ("ResizeObserver" in window) {
        const resizeObserver = new ResizeObserver(() => {
            liveResizeRefresh();
        });

        resizeObserver.observe(shell);
        resizeObserver.observe(canvas);
    }

    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) {
            liveResizeRefresh();
        }
    });
});