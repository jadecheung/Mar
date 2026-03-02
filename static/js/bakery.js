/* ============================================
   BAKERY MANAGEMENT GAME - Core Logic
   Materials, recipes, lottery, baking
   ============================================ */

const BakeryGame = (() => {
    // ---- Material Definitions ----
    const MATERIALS = {
        flour:     { name: 'Flour',     emoji: '\uD83C\uDF3E', weight: 20 },
        butter:    { name: 'Butter',    emoji: '\uD83E\uDDC8', weight: 12 },
        sugar:     { name: 'Sugar',     emoji: '\uD83C\uDF6C', weight: 14 },
        eggs:      { name: 'Eggs',      emoji: '\uD83E\uDD5A', weight: 15 },
        yeast:     { name: 'Yeast',     emoji: '\uD83E\uDEE7', weight: 16 },
        milk:      { name: 'Milk',      emoji: '\uD83E\uDD5B', weight: 13 },
        salt:      { name: 'Salt',      emoji: '\uD83E\uDDC2', weight: 18 },
        chocolate: { name: 'Chocolate', emoji: '\uD83C\uDF6B', weight: 6 },
        cream:     { name: 'Cream',     emoji: '\uD83C\uDF76', weight: 8 },
        almonds:   { name: 'Almonds',   emoji: '\uD83E\uDD5C', weight: 5 }
    };

    const MATERIAL_KEYS = Object.keys(MATERIALS);

    // ---- Bread Recipes ----
    const RECIPES = {
        'Basic Bread': {
            emoji: '\uD83C\uDF5E',
            ingredients: { flour: 3, yeast: 1, salt: 1 },
            description: 'Simple and satisfying'
        },
        'Baguette': {
            emoji: '\uD83E\uDD56',
            ingredients: { flour: 4, yeast: 1, salt: 1, milk: 1 },
            description: 'Crispy French classic'
        },
        'Sourdough': {
            emoji: '\uD83E\uDED3',
            ingredients: { flour: 5, salt: 1, yeast: 1 },
            description: 'Tangy artisan loaf'
        },
        'Brioche': {
            emoji: '\uD83E\uDDC1',
            ingredients: { flour: 3, butter: 2, eggs: 2, sugar: 1, yeast: 1 },
            description: 'Rich and buttery'
        },
        'Croissant': {
            emoji: '\uD83E\uDD50',
            ingredients: { flour: 3, butter: 3, yeast: 1, eggs: 1, milk: 1 },
            description: 'Flaky and golden',
            special: true
        },
        'Pretzel': {
            emoji: '\uD83E\uDD68',
            ingredients: { flour: 3, salt: 2, yeast: 1, butter: 1 },
            description: 'Twisted and salty'
        },
        'Cinnamon Roll': {
            emoji: '\uD83C\uDF00',
            ingredients: { flour: 3, butter: 2, sugar: 2, yeast: 1, eggs: 1 },
            description: 'Sweet spiraled delight'
        },
        'Chocolate Bread': {
            emoji: '\uD83C\uDF6B',
            ingredients: { flour: 3, chocolate: 2, butter: 1, sugar: 1, yeast: 1 },
            description: 'Decadent cocoa swirl'
        }
    };

    // ---- Game State ----
    let inventory = {};
    let lotteryChances = 5;
    let breadsMade = 0;
    let breadLog = [];
    let isBaking = false;
    let hasSpeedUpgrade = false;
    let tetrisUnlocked = false;
    const BAKE_TIME_MS = 3000;

    // ---- Initialize ----
    function init() {
        // Start with empty inventory
        MATERIAL_KEYS.forEach(key => { inventory[key] = 0; });

        renderInventory();
        renderRecipes();
        updateStats();
        updateLotteryUI();

        // Init Tetris
        Tetris.init('tetris-canvas', 'tetris-next-canvas', {
            onGoalReached: handleTetrisGoal,
            onGameEnd: handleTetrisEnd
        });
    }

    // ---- Lottery System ----
    function spinLottery() {
        if (lotteryChances <= 0 || isBaking) return;

        lotteryChances--;
        updateStats();

        // Give 1-3 random materials (weighted)
        const count = weightedRandom([
            { value: 1, weight: 25 },
            { value: 2, weight: 50 },
            { value: 3, weight: 25 }
        ]);

        const awarded = [];
        for (let i = 0; i < count; i++) {
            const mat = weightedMaterialPick();
            inventory[mat]++;
            awarded.push(mat);
        }

        // Animate lottery button
        const btn = document.getElementById('lottery-btn');
        btn.classList.add('spinning');
        setTimeout(() => btn.classList.remove('spinning'), 500);

        // Show result
        showLotteryResult(awarded);
        renderInventory();
        renderRecipes();
        updateLotteryUI();
    }

    function weightedMaterialPick() {
        const totalWeight = MATERIAL_KEYS.reduce((sum, k) => sum + MATERIALS[k].weight, 0);
        let rand = Math.random() * totalWeight;
        for (const key of MATERIAL_KEYS) {
            rand -= MATERIALS[key].weight;
            if (rand <= 0) return key;
        }
        return MATERIAL_KEYS[MATERIAL_KEYS.length - 1];
    }

    function weightedRandom(options) {
        const total = options.reduce((s, o) => s + o.weight, 0);
        let rand = Math.random() * total;
        for (const opt of options) {
            rand -= opt.weight;
            if (rand <= 0) return opt.value;
        }
        return options[options.length - 1].value;
    }

    function showLotteryResult(awarded) {
        const container = document.getElementById('lottery-result');
        container.innerHTML = `
            <div class="lottery-result-title">You received:</div>
            <div class="lottery-items">
                ${awarded.map((mat, i) => `
                    <div class="lottery-item" style="animation-delay: ${i * 0.15}s">
                        <span class="item-emoji">${MATERIALS[mat].emoji}</span>
                        <span class="item-name">${MATERIALS[mat].name}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    // ---- Baking ----
    function canBake(recipeName) {
        const recipe = RECIPES[recipeName];
        if (!recipe) return false;
        return Object.entries(recipe.ingredients).every(
            ([mat, qty]) => (inventory[mat] || 0) >= qty
        );
    }

    function bakeBread(recipeName) {
        if (isBaking || !canBake(recipeName)) return;

        const recipe = RECIPES[recipeName];
        isBaking = true;

        // Consume materials
        Object.entries(recipe.ingredients).forEach(([mat, qty]) => {
            inventory[mat] -= qty;
        });

        renderInventory();
        renderRecipes();

        // Show oven overlay
        const bakeTime = hasSpeedUpgrade ? BAKE_TIME_MS / 2 : BAKE_TIME_MS;
        showOvenProgress(recipeName, recipe, bakeTime);

        // After baking completes
        setTimeout(() => {
            isBaking = false;
            breadsMade++;
            lotteryChances += 2;

            breadLog.unshift(`${recipe.emoji} ${recipeName}`);
            if (breadLog.length > 50) breadLog.pop();

            hideOvenProgress();
            updateStats();
            updateLotteryUI();
            renderRecipes();
            renderBreadLog();

            showToast(`${recipe.emoji} ${recipeName} baked!`, 'success');
            showToast('+2 lottery chances!', 'info');

            // Special: Croissant triggers Tetris
            if (recipeName === 'Croissant' && !hasSpeedUpgrade) {
                setTimeout(() => openTetris(), 600);
            }
        }, bakeTime);
    }

    function showOvenProgress(recipeName, recipe, duration) {
        const overlay = document.getElementById('oven-overlay');
        overlay.querySelector('.oven-bread-name').textContent = `${recipe.emoji} ${recipeName}`;
        overlay.classList.add('active');
        if (hasSpeedUpgrade) overlay.classList.add('super-speed');

        const bar = overlay.querySelector('.oven-progress-bar');
        bar.style.width = '0%';
        bar.style.transition = 'none';

        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                bar.style.transition = `width ${duration}ms linear`;
                bar.style.width = '100%';
            });
        });
    }

    function hideOvenProgress() {
        const overlay = document.getElementById('oven-overlay');
        overlay.classList.remove('active', 'super-speed');
    }

    // ---- Tetris Integration ----
    function openTetris() {
        const overlay = document.getElementById('tetris-overlay');
        overlay.classList.add('active');
        showToast('\uD83E\uDD50 Croissant bonus! Play Tetris!', 'special');
    }

    function startTetrisGame() {
        document.getElementById('tetris-start-btn').style.display = 'none';
        document.getElementById('tetris-close-btn').style.display = 'none';
        Tetris.start();
    }

    function closeTetris() {
        Tetris.stop();
        const overlay = document.getElementById('tetris-overlay');
        overlay.classList.remove('active');
        document.getElementById('tetris-start-btn').style.display = '';
        document.getElementById('tetris-close-btn').style.display = '';
        document.getElementById('tetris-score').textContent = '0';
        document.getElementById('tetris-lines').textContent = '0';
    }

    function handleTetrisGoal(score) {
        // Player reached 100! Upgrade time!
        hasSpeedUpgrade = true;
        playGreatJobSound();

        setTimeout(() => {
            closeTetris();
            showCelebration();
            updateStats();
        }, 500);
    }

    function handleTetrisEnd(score, reachedGoal) {
        if (!reachedGoal) {
            document.getElementById('tetris-close-btn').style.display = '';
            showToast(`Game over! Score: ${score}. Try again next croissant!`, 'info');
        }
    }

    // ---- Sound: "Great Job!" ----
    function playGreatJobSound() {
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

            // Celebratory ascending jingle
            const notes = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
            const durations = [0.15, 0.15, 0.15, 0.4];

            let time = audioCtx.currentTime;
            notes.forEach((freq, i) => {
                // Main tone
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'triangle';
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.3, time);
                gain.gain.exponentialRampToValueAtTime(0.01, time + durations[i] + 0.1);
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                osc.start(time);
                osc.stop(time + durations[i] + 0.15);

                // Harmony
                const osc2 = audioCtx.createOscillator();
                const gain2 = audioCtx.createGain();
                osc2.type = 'sine';
                osc2.frequency.value = freq * 1.5; // Fifth above
                gain2.gain.setValueAtTime(0.15, time);
                gain2.gain.exponentialRampToValueAtTime(0.01, time + durations[i] + 0.1);
                osc2.connect(gain2);
                gain2.connect(audioCtx.destination);
                osc2.start(time);
                osc2.stop(time + durations[i] + 0.15);

                time += durations[i];
            });

            // Final sparkle
            const sparkle = audioCtx.createOscillator();
            const sparkleGain = audioCtx.createGain();
            sparkle.type = 'sine';
            sparkle.frequency.setValueAtTime(2093, time);
            sparkle.frequency.exponentialRampToValueAtTime(4186, time + 0.3);
            sparkleGain.gain.setValueAtTime(0.15, time);
            sparkleGain.gain.exponentialRampToValueAtTime(0.01, time + 0.4);
            sparkle.connect(sparkleGain);
            sparkleGain.connect(audioCtx.destination);
            sparkle.start(time);
            sparkle.stop(time + 0.5);
        } catch (e) {
            // Web Audio not available
        }
    }

    // ---- Celebration ----
    function showCelebration() {
        const overlay = document.getElementById('celebration-overlay');
        overlay.classList.add('active');
    }

    function dismissCelebration() {
        const overlay = document.getElementById('celebration-overlay');
        overlay.classList.remove('active');
    }

    // ---- Rendering ----
    function renderInventory() {
        const list = document.getElementById('material-list');
        list.innerHTML = MATERIAL_KEYS.map(key => {
            const mat = MATERIALS[key];
            const count = inventory[key] || 0;
            return `
                <div class="material-row" id="mat-${key}">
                    <div class="material-info">
                        <span class="material-emoji">${mat.emoji}</span>
                        <span class="material-name">${mat.name}</span>
                    </div>
                    <span class="material-count">${count}</span>
                </div>
            `;
        }).join('');
    }

    function renderRecipes() {
        const grid = document.getElementById('recipes-grid');
        grid.innerHTML = Object.entries(RECIPES).map(([name, recipe]) => {
            const bakeable = canBake(name);
            const cardClass = isBaking ? '' : (bakeable ? 'can-bake' : '');
            const btnClass = bakeable && !isBaking ? 'ready' : 'disabled';
            const btnText = isBaking ? 'Oven in use...' : (bakeable ? 'Bake!' : 'Need materials');

            return `
                <div class="recipe-card ${cardClass}"
                     ${bakeable && !isBaking ? `onclick="BakeryGame.bakeBread('${name}')"` : ''}>
                    ${recipe.special ? '<span class="croissant-badge">Tetris Bonus!</span>' : ''}
                    <div class="recipe-name">
                        <span class="bread-emoji">${recipe.emoji}</span>
                        ${name}
                    </div>
                    <div style="font-size:0.78rem;color:var(--text-muted);margin-bottom:6px;">${recipe.description}</div>
                    <div class="recipe-ingredients">
                        ${Object.entries(recipe.ingredients).map(([mat, qty]) => {
                            const has = (inventory[mat] || 0) >= qty;
                            return `<span class="ingredient-tag ${has ? 'has' : 'missing'}">${MATERIALS[mat].emoji} ${MATERIALS[mat].name} x${qty}</span>`;
                        }).join('')}
                    </div>
                    <button class="bake-btn ${btnClass}">${btnText}</button>
                </div>
            `;
        }).join('');
    }

    function renderBreadLog() {
        const logEl = document.getElementById('bread-log-list');
        if (!logEl) return;
        logEl.innerHTML = breadLog.map(entry =>
            `<div class="bread-log-entry">${entry}</div>`
        ).join('');
    }

    function updateStats() {
        document.getElementById('stat-breads').textContent = breadsMade;
        document.getElementById('stat-chances').textContent = lotteryChances;

        const speedBadge = document.getElementById('speed-badge');
        if (hasSpeedUpgrade) {
            speedBadge.classList.add('active');
        }
    }

    function updateLotteryUI() {
        const chancesEl = document.getElementById('lottery-chances-display');
        const btn = document.getElementById('lottery-btn');
        chancesEl.textContent = lotteryChances;
        btn.disabled = lotteryChances <= 0;
        btn.textContent = lotteryChances > 0 ? `\uD83C\uDFB0 Spin Lottery!` : 'No chances left';
    }

    // ---- Toast Notifications ----
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }

    // ---- Public API ----
    return {
        init,
        spinLottery,
        bakeBread,
        startTetrisGame,
        closeTetris,
        dismissCelebration
    };
})();

// Boot the game on DOM load
document.addEventListener('DOMContentLoaded', () => {
    BakeryGame.init();
});
