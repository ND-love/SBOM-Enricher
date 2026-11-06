(function () {
    const sidebarStorageKey = "cert-checker-sidebar-collapsed";
    const modeStorageKey = "cert-checker-active-mode";

    const body = document.body;
    const toggle = document.getElementById("sidebarToggle");
    const stack = document.querySelector("[data-active-mode]");
    const navItems = Array.from(document.querySelectorAll("[data-mode-link]"));
    const modePanels = Array.from(document.querySelectorAll("[data-mode-panel]"));

    let floatingScrollbar = null;
    let floatingScrollbarInner = null;
    let activeWrap = null;
    let syncLock = false;
    let rafId = null;

    function applySidebarState() {
        const collapsed = localStorage.getItem(sidebarStorageKey) === "1";
        body.classList.toggle("sidebar-collapsed", collapsed && window.innerWidth > 1024);
    }

    function setActiveMode(mode, persist = true) {
        if (!stack || !mode) return;

        stack.setAttribute("data-active-mode", mode);

        navItems.forEach((item) => {
            item.classList.toggle("is-active", item.dataset.modeLink === mode);
        });

        modePanels.forEach((panel) => {
            const isActive = panel.dataset.modePanel === mode;
            panel.classList.toggle("is-active", isActive);
        });

        if (persist) {
            sessionStorage.setItem(modeStorageKey, mode);
        }

        requestFloatingScrollbarRefresh();
    }

    function initModeNavigation() {
        if (!stack) return;

        const knownModes = new Set(
            modePanels
                .map((panel) => panel.dataset.modePanel)
                .filter(Boolean)
        );

        const serverMode = stack.getAttribute("data-active-mode") || "check";
        const rememberedMode = sessionStorage.getItem(modeStorageKey);

        const initialMode =
            stack.hasAttribute("data-force-mode") && knownModes.has(serverMode)
                ? serverMode
                : (rememberedMode && knownModes.has(rememberedMode) ? rememberedMode : "check");

        setActiveMode(initialMode);

        navItems.forEach((item) => {
            item.addEventListener("click", (event) => {
                const mode = item.dataset.modeLink;
                if (!knownModes.has(mode)) return;
                if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                event.preventDefault();

                setActiveMode(mode);

                const panel = document.querySelector(`[data-mode-panel="${mode}"]`);
                if (panel) {
                    panel.scrollIntoView({ behavior: "smooth", block: "start" });
                }
            });
        });
    }

    function updateCounter(table, counter) {
        const rows = Array.from(table.querySelectorAll("tbody tr"));
        const visible = rows.filter((row) => !row.classList.contains("is-hidden")).length;
        counter.textContent = `${visible} / ${rows.length}`;
    }

    function initTableSearch() {
        const inputs = document.querySelectorAll("[data-table-search]");
        inputs.forEach((input) => {
            const selector = input.getAttribute("data-table-search");
            const table = selector ? document.querySelector(selector) : null;
            if (!table) return;

            const counter = document.querySelector(`[data-table-counter="${selector}"]`);
            if (counter) updateCounter(table, counter);

            input.addEventListener("input", () => {
                const query = input.value.trim().toLowerCase();
                const rows = table.querySelectorAll("tbody tr");

                rows.forEach((row) => {
                    const text = row.textContent.toLowerCase();
                    row.classList.toggle("is-hidden", query !== "" && !text.includes(query));
                });

                if (counter) updateCounter(table, counter);
            });
        });
    }

    function getTargetCheckboxes() {
        return Array.from(document.querySelectorAll('input[name="target_keys"]'));
    }

    function getTargetLabel(checkbox) {
        const card = checkbox.closest(".version-card");
        const title = card ? card.querySelector(".version-card-title") : null;
        return title ? title.textContent.trim() : checkbox.value;
    }

    function updateTargetCounter() {
        const counter = document.querySelector("[data-target-counter]");
        if (!counter) return;

        const checkedCount = getTargetCheckboxes().filter((box) => box.checked).length;
        counter.textContent = `${checkedCount} / 5`;
    }

    function renderSelectedTargets() {
        const container = document.querySelector("[data-selected-targets]");
        if (!container) return;

        container.innerHTML = "";

        const checked = getTargetCheckboxes().filter((box) => box.checked);

        if (!checked.length) {
            const empty = document.createElement("div");
            empty.className = "selected-targets-empty";
            empty.textContent = "Пока ничего не выбрано";
            container.appendChild(empty);
            return;
        }

        checked.forEach((checkbox) => {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "selected-target-chip";
            chip.dataset.targetKey = checkbox.value;

            const label = document.createElement("span");
            label.className = "selected-target-chip__label";
            label.textContent = getTargetLabel(checkbox);

            const remove = document.createElement("span");
            remove.className = "selected-target-chip__remove";
            remove.textContent = "×";

            chip.appendChild(label);
            chip.appendChild(remove);
            container.appendChild(chip);
        });
    }

    function initTargetSelectionUI() {
        const boxes = getTargetCheckboxes();
        const selectedContainer = document.querySelector("[data-selected-targets]");

        if (!boxes.length || !selectedContainer) return;

        boxes.forEach((box) => {
            box.addEventListener("change", () => {
                const checked = boxes.filter((item) => item.checked);

                if (checked.length > 5) {
                    box.checked = false;
                    alert("Можно выбрать не более 5 систем.");
                }

                updateTargetCounter();
                renderSelectedTargets();
            });
        });

        selectedContainer.addEventListener("click", (event) => {
            const chip = event.target.closest(".selected-target-chip");
            if (!chip) return;

            const targetKey = chip.dataset.targetKey;
            const checkbox = boxes.find((item) => item.value === targetKey);
            if (!checkbox) return;

            checkbox.checked = false;
            updateTargetCounter();
            renderSelectedTargets();
        });

        updateTargetCounter();
        renderSelectedTargets();
    }

    function ensureFloatingScrollbar() {
        if (floatingScrollbar) return;

        floatingScrollbar = document.createElement("div");
        floatingScrollbar.className = "floating-table-scroll is-hidden";

        floatingScrollbarInner = document.createElement("div");
        floatingScrollbarInner.className = "floating-table-scroll__inner";

        floatingScrollbar.appendChild(floatingScrollbarInner);
        document.body.appendChild(floatingScrollbar);

        floatingScrollbar.addEventListener("scroll", () => {
            if (!activeWrap || syncLock) return;

            syncLock = true;
            activeWrap.scrollLeft = floatingScrollbar.scrollLeft;
            requestAnimationFrame(() => {
                syncLock = false;
            });
        }, { passive: true });
    }

    function getVisibleWraps() {
        const activePanel = document.querySelector(".mode-panel.is-active");
        if (!activePanel) return [];

        return Array.from(
            activePanel.querySelectorAll(".table-wrap[data-floating-scroll-target]")
        ).filter((wrap) => wrap.offsetParent !== null);
    }

    function resolveActiveWrap() {
        const wraps = getVisibleWraps();
        if (!wraps.length) return null;

        if (activeWrap && wraps.includes(activeWrap)) {
            return activeWrap;
        }

        return wraps[0];
    }

    function refreshFloatingScrollbar() {
        ensureFloatingScrollbar();

        const wrap = resolveActiveWrap();
        if (!wrap) {
            floatingScrollbar.classList.add("is-hidden");
            activeWrap = null;
            return;
        }

        activeWrap = wrap;

        if (wrap.scrollWidth <= wrap.clientWidth + 2) {
            floatingScrollbar.classList.add("is-hidden");
            return;
        }

        const shell = document.querySelector(".content-shell") || document.querySelector(".main-content");
        const shellRect = shell ? shell.getBoundingClientRect() : { left: 12, right: window.innerWidth - 12 };

        floatingScrollbar.style.left = `${Math.max(12, shellRect.left + 6)}px`;
        floatingScrollbar.style.right = `${Math.max(12, window.innerWidth - shellRect.right + 6)}px`;

        floatingScrollbarInner.style.width = `${wrap.scrollWidth}px`;
        floatingScrollbar.classList.remove("is-hidden");

        if (!syncLock) {
            syncLock = true;
            floatingScrollbar.scrollLeft = wrap.scrollLeft;
            requestAnimationFrame(() => {
                syncLock = false;
            });
        }
    }

    function requestFloatingScrollbarRefresh() {
        if (rafId) return;
        rafId = requestAnimationFrame(() => {
            rafId = null;
            refreshFloatingScrollbar();
        });
    }

    function initFloatingScrollbarBindings() {
        ensureFloatingScrollbar();

        const wraps = document.querySelectorAll(".table-wrap[data-floating-scroll-target]");
        wraps.forEach((wrap) => {
            ["mouseenter", "mousedown", "touchstart", "focusin"].forEach((eventName) => {
                wrap.addEventListener(eventName, () => {
                    activeWrap = wrap;
                    requestFloatingScrollbarRefresh();
                }, { passive: true });
            });

            wrap.addEventListener("scroll", () => {
                if (activeWrap !== wrap) {
                    activeWrap = wrap;
                }

                if (!floatingScrollbar || syncLock) return;

                syncLock = true;
                floatingScrollbar.scrollLeft = wrap.scrollLeft;
                requestAnimationFrame(() => {
                    syncLock = false;
                });
            }, { passive: true });
        });

        window.addEventListener("resize", requestFloatingScrollbarRefresh, { passive: true });
        window.addEventListener("scroll", requestFloatingScrollbarRefresh, { passive: true });
        requestFloatingScrollbarRefresh();
    }

    if (toggle) {
        toggle.addEventListener("click", () => {
            const nextCollapsed = !body.classList.contains("sidebar-collapsed");
            localStorage.setItem(sidebarStorageKey, nextCollapsed ? "1" : "0");
            applySidebarState();
            requestFloatingScrollbarRefresh();
        });
    }

    window.addEventListener("resize", applySidebarState, { passive: true });

    applySidebarState();
    initModeNavigation();
    initTableSearch();
    initTargetSelectionUI();
    initFloatingScrollbarBindings();
})();

/* =========================================================
   SPACE PARTICLES BACKGROUND
   ---------------------------------------------------------
   Что можно удобно менять:
   - PARTICLE_COUNT: сколько частиц
   - BASE_SPEED: базовая скорость
   - MOUSE_RADIUS: радиус отталкивания от мышки
   - MOUSE_FORCE: сила отталкивания
   - SIZE_MIN / SIZE_MAX: размер точек
   - ALPHA_MIN / ALPHA_MAX: яркость точек
   ========================================================= */

(function initSpaceParticles() {
    const canvas = document.getElementById("spaceParticles");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    /* ---------- твои настройки: НЕ МЕНЯЛ ---------- */
    const PARTICLE_COUNT = 200;   // сколько частиц на экране
    const BASE_SPEED = 0.05;      // базовая скорость дрейфа
    const MOUSE_RADIUS = 80;      // радиус влияния мышки
    const MOUSE_FORCE = 8;        // сила отталкивания от курсора
    const SIZE_MIN = 0.8;         // минимальный размер точки
    const SIZE_MAX = 2.8;         // максимальный размер точки
    const ALPHA_MIN = 0.01;       // минимальная яркость
    const ALPHA_MAX = 0.3;        // максимальная яркость
    const TWINKLE_SPEED_MIN = 0.0003; // скорость "дыхания" яркости
    const TWINKLE_SPEED_MAX = 0.0012;
    const TRAIL_ALPHA = 0.1;      // чем меньше, тем длиннее ощущение "шлейфа"

    /* ---------- новые настройки перерождения ---------- #R.D.A*/
    const RESPAWN_RADIUS_MIN = 12;   // минимально близко к месту смерти
    const RESPAWN_RADIUS_MAX = 110;  // максимально далеко от места смерти

    const FADE_OUT_FRAMES_MIN = 180; // минимальная длина затухания
    const FADE_OUT_FRAMES_MAX = 400; // максимальная длина затухания

    const FADE_IN_FRAMES_MIN = 80;   // минимальная длина проявления
    const FADE_IN_FRAMES_MAX = 180;  // максимальная длина проявления

    const GLOBAL_RESPAWN_CHANCE = 0.08;
    // маленький шанс переродиться в случайной точке,
    // чтобы экран со временем не пустел в центре

    let width = 0;
    let height = 0;
    let dpr = Math.max(1, window.devicePixelRatio || 1);

    const mouse = {
        x: null,
        y: null,
        active: false
    };

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function getRespawnPoint(baseX, baseY) {
        // Иногда рождаем частицу в случайной точке,
        // чтобы поддерживать равномерность поля.
        if (Math.random() < GLOBAL_RESPAWN_CHANCE) {
            return {
                x: Math.random() * width,
                y: Math.random() * height
            };
        }

        const angle = Math.random() * Math.PI * 2;
        const radius =
            RESPAWN_RADIUS_MIN +
            Math.random() * (RESPAWN_RADIUS_MAX - RESPAWN_RADIUS_MIN);

        return {
            x: clamp(baseX + Math.cos(angle) * radius, 0, width),
            y: clamp(baseY + Math.sin(angle) * radius, 0, height)
        };
    }

    class Particle {
        constructor() {
            this.reset(true);
        }

        reset(initial = false, origin = null) {
            let spawnPoint;

            if (initial || !origin) {
                spawnPoint = {
                    x: Math.random() * width,
                    y: Math.random() * height
                };
            } else {
                spawnPoint = getRespawnPoint(origin.x, origin.y);
            }

            this.x = spawnPoint.x;
            this.y = spawnPoint.y;

            this.size = SIZE_MIN + Math.random() * (SIZE_MAX - SIZE_MIN);
            this.baseAlpha = ALPHA_MIN + Math.random() * (ALPHA_MAX - ALPHA_MIN);
            this.alpha = initial ? this.baseAlpha : 0;

            const angle = Math.random() * Math.PI * 2;
            const speed = BASE_SPEED + Math.random() * 0.25;

            this.vx = Math.cos(angle) * speed;
            this.vy = Math.sin(angle) * speed;

            this.noiseSeed = Math.random() * 1000;
            this.twinkleSpeed =
                TWINKLE_SPEED_MIN +
                Math.random() * (TWINKLE_SPEED_MAX - TWINKLE_SPEED_MIN);
            this.twinkleOffset = Math.random() * Math.PI * 2;

            this.life = initial ? Math.random() * 1000 : 0;
            this.maxLife = 500 + Math.random() * 5000;

            /* фазы жизни */
            this.phase = initial ? "alive" : "fadingIn";

            /* затухание/проявление */
            this.fadeProgress = 0;
            this.fadeOutDuration =
                FADE_OUT_FRAMES_MIN +
                Math.random() * (FADE_OUT_FRAMES_MAX - FADE_OUT_FRAMES_MIN);

            this.fadeInDuration =
                FADE_IN_FRAMES_MIN +
                Math.random() * (FADE_IN_FRAMES_MAX - FADE_IN_FRAMES_MIN);

            /* точка смерти */
            this.deathX = this.x;
            this.deathY = this.y;
        }

        startDying() {
            if (this.phase === "fadingOut") return;

            this.phase = "fadingOut";
            this.fadeProgress = 0;
            this.deathX = clamp(this.x, 0, width);
            this.deathY = clamp(this.y, 0, height);
        }

        update(time) {
            const twinkle =
                this.baseAlpha *
                (0.72 + 0.28 * Math.sin(time * this.twinkleSpeed + this.twinkleOffset));

            /* очень лёгкое плавание */
            const driftX = Math.sin(time * 0.00025 + this.noiseSeed) * 0.15;
            const driftY = Math.cos(time * 0.00022 + this.noiseSeed) * 0.15;

            this.vx += driftX;
            this.vy += driftY;

            /* ограничиваем скорость, чтобы не разлетались слишком резко */
            this.vx *= 0.25;
            this.vy *= 0.25;

            this.x += this.vx;
            this.y += this.vy;

            /* реакция на мышку */
            if (mouse.active && mouse.x !== null && mouse.y !== null) {
                const dx = this.x - mouse.x;
                const dy = this.y - mouse.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < MOUSE_RADIUS && dist > 0.001) {
                    const force = (1 - dist / MOUSE_RADIUS) * MOUSE_FORCE;
                    this.vx += (dx / dist) * force;
                    this.vy += (dy / dist) * force;
                }
            }

            const margin = 80;
            const out =
                this.x < -margin ||
                this.x > width + margin ||
                this.y < -margin ||
                this.y > height + margin;

            /* если улетела за границы — тоже начинаем умирание */
            if (out && this.phase !== "fadingOut") {
                this.startDying();
            }

            /* если жизнь закончилась — начинаем затухание */
            if (this.phase === "alive" && this.life > this.maxLife) {
                this.startDying();
            }

            /* обычная жизнь */
            if (this.phase === "alive") {
                this.life += 1;
                this.alpha = twinkle;
            }

            /* затухание */
            if (this.phase === "fadingOut") {
                this.fadeProgress += 1;

                const fadeK = Math.max(0, 1 - this.fadeProgress / this.fadeOutDuration);
                this.alpha = twinkle * fadeK;

                /* в конце чуть замедляется */
                this.vx *= 0.985;
                this.vy *= 0.985;

                if (fadeK <= 0.01) {
                    this.reset(false, {
                        x: this.deathX,
                        y: this.deathY
                    });
                }
            }

            /* мягкое проявление новой частицы #R.D.A*/
            if (this.phase === "fadingIn") {
                this.fadeProgress += 1;

                const appearK = Math.min(1, this.fadeProgress / this.fadeInDuration);
                this.alpha = twinkle * appearK;

                if (appearK >= 1) {
                    this.phase = "alive";
                    this.life = 0;
                    this.alpha = twinkle;
                }
            }

            /* возле курсора чуть ярче */
            if (mouse.active && mouse.x !== null && mouse.y !== null) {
                const dx = this.x - mouse.x;
                const dy = this.y - mouse.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < MOUSE_RADIUS && dist > 0.001) {
                    const force = (1 - dist / MOUSE_RADIUS) * MOUSE_FORCE;
                    this.alpha = Math.min(1, this.alpha + force * 0.05);
                }
            }
        }

        draw() {
            if (this.alpha <= 0.001) return;

            /* основная светящаяся точка */
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);

            const glow = ctx.createRadialGradient(
                this.x,
                this.y,
                0,
                this.x,
                this.y,
                this.size * 4.6
            );

            glow.addColorStop(0, `rgba(255,255,255,${this.alpha})`);
            glow.addColorStop(0.35, `rgba(210,225,255,${this.alpha * 0.45})`);
            glow.addColorStop(1, "rgba(210,225,255,0)");

            ctx.fillStyle = glow;
            ctx.fill();

            /* маленькое ядро точки */
            ctx.beginPath();
            ctx.arc(this.x, this.y, Math.max(0.55, this.size * 0.42), 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255,255,255,${Math.min(1, this.alpha + 0.15)})`;
            ctx.fill();
        }
    }

    const particles = [];

    function resizeCanvas() {
        width = window.innerWidth;
        height = window.innerHeight;
        dpr = Math.max(1, window.devicePixelRatio || 1);

        canvas.width = Math.floor(width * dpr);
        canvas.height = Math.floor(height * dpr);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;

        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        if (!particles.length) {
            for (let i = 0; i < PARTICLE_COUNT; i += 1) {
                particles.push(new Particle());
            }
        }
    }

    function clearFrame() {
        /* не #R.D.Aполностью очищаем холст,
           а даём лёгкое затухание для ощущения живого движения */
        ctx.clearRect(0, 0, width, height);

        ctx.fillStyle = `rgba(0, 0, 0, ${TRAIL_ALPHA})`;
        ctx.fillRect(0, 0, width, height);
    }

    function animate(time) {
        clearFrame();

        for (const particle of particles) {
            particle.update(time);
            particle.draw();
        }

        requestAnimationFrame(animate);
    }

    window.addEventListener("resize", resizeCanvas);

    window.addEventListener("mousemove", (event) => {
        mouse.x = event.clientX;
        mouse.y = event.clientY;
        mouse.active = true;
    });

    window.addEventListener("mouseleave", () => {
        mouse.active = false;
        mouse.x = null;
        mouse.y = null;
    });

    window.addEventListener("touchstart", (event) => {
        const touch = event.touches[0];
        if (!touch) return;
        mouse.x = touch.clientX;
        mouse.y = touch.clientY;
        mouse.active = true;
    }, { passive: true });

    window.addEventListener("touchmove", (event) => {
        const touch = event.touches[0];
        if (!touch) return;
        mouse.x = touch.clientX;
        mouse.y = touch.clientY;
        mouse.active = true;
    }, { passive: true });

    window.addEventListener("touchend", () => {
        mouse.active = false;
        mouse.x = null;
        mouse.y = null;
    });

    resizeCanvas();

    if (prefersReducedMotion) {
        /* если у пользователя отключены анимации,
           просто рисуем один статичный кадр */
        clearFrame();
        for (const particle of particles) {
            particle.draw();
        }
        return;
    }

    requestAnimationFrame(animate);
})();