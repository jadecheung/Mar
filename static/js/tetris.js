/* ============================================
   TETRIS MINIGAME
   Triggered when player bakes a croissant
   Goal: Score 100 points to earn 2x speed upgrade
   ============================================ */

const Tetris = (() => {
    // ---- Constants ----
    const COLS = 10;
    const ROWS = 20;
    const BLOCK_SIZE = 28;
    const NEXT_BLOCK_SIZE = 20;

    // Scoring: each line = 25pts, so 4 lines = 100 (the "relatively easy bar")
    const SCORE_PER_LINES = {
        1: 25,
        2: 60,
        3: 100,
        4: 160
    };

    const GOAL_SCORE = 100;

    // Tetromino definitions (4 rotation states each)
    const PIECES = {
        I: {
            color: '#00f0f0',
            shapes: [
                [[0,0],[1,0],[2,0],[3,0]],
                [[0,0],[0,1],[0,2],[0,3]],
                [[0,0],[1,0],[2,0],[3,0]],
                [[0,0],[0,1],[0,2],[0,3]]
            ]
        },
        O: {
            color: '#f0f000',
            shapes: [
                [[0,0],[1,0],[0,1],[1,1]],
                [[0,0],[1,0],[0,1],[1,1]],
                [[0,0],[1,0],[0,1],[1,1]],
                [[0,0],[1,0],[0,1],[1,1]]
            ]
        },
        T: {
            color: '#a000f0',
            shapes: [
                [[0,0],[1,0],[2,0],[1,1]],
                [[0,0],[0,1],[0,2],[1,1]],
                [[1,0],[0,1],[1,1],[2,1]],
                [[1,0],[1,1],[1,2],[0,1]]
            ]
        },
        S: {
            color: '#00f000',
            shapes: [
                [[1,0],[2,0],[0,1],[1,1]],
                [[0,0],[0,1],[1,1],[1,2]],
                [[1,0],[2,0],[0,1],[1,1]],
                [[0,0],[0,1],[1,1],[1,2]]
            ]
        },
        Z: {
            color: '#f00000',
            shapes: [
                [[0,0],[1,0],[1,1],[2,1]],
                [[1,0],[0,1],[1,1],[0,2]],
                [[0,0],[1,0],[1,1],[2,1]],
                [[1,0],[0,1],[1,1],[0,2]]
            ]
        },
        J: {
            color: '#0000f0',
            shapes: [
                [[0,0],[0,1],[1,1],[2,1]],
                [[0,0],[1,0],[0,1],[0,2]],
                [[0,0],[1,0],[2,0],[2,1]],
                [[1,0],[1,1],[0,2],[1,2]]
            ]
        },
        L: {
            color: '#f0a000',
            shapes: [
                [[2,0],[0,1],[1,1],[2,1]],
                [[0,0],[0,1],[0,2],[1,2]],
                [[0,0],[1,0],[2,0],[0,1]],
                [[0,0],[1,0],[1,1],[1,2]]
            ]
        }
    };

    const PIECE_NAMES = Object.keys(PIECES);

    // ---- Game State ----
    let canvas, ctx, nextCanvas, nextCtx;
    let board, currentPiece, nextPiece, score, linesCleared;
    let gameRunning, gameOver, goalReached;
    let dropInterval, dropTimer, lastTime;
    let onGoalReached, onGameEnd;
    let animationId;

    // ---- Initialize ----
    function init(canvasId, nextCanvasId, callbacks = {}) {
        canvas = document.getElementById(canvasId);
        ctx = canvas.getContext('2d');
        canvas.width = COLS * BLOCK_SIZE;
        canvas.height = ROWS * BLOCK_SIZE;

        nextCanvas = document.getElementById(nextCanvasId);
        nextCtx = nextCanvas.getContext('2d');
        nextCanvas.width = 4 * NEXT_BLOCK_SIZE;
        nextCanvas.height = 4 * NEXT_BLOCK_SIZE;

        onGoalReached = callbacks.onGoalReached || (() => {});
        onGameEnd = callbacks.onGameEnd || (() => {});

        document.addEventListener('keydown', handleInput);
    }

    function start() {
        board = Array.from({ length: ROWS }, () => Array(COLS).fill(null));
        score = 0;
        linesCleared = 0;
        gameRunning = true;
        gameOver = false;
        goalReached = false;
        dropInterval = 800;
        lastTime = 0;
        dropTimer = 0;

        nextPiece = randomPiece();
        spawnPiece();
        updateScoreDisplay();

        if (animationId) cancelAnimationFrame(animationId);
        animationId = requestAnimationFrame(gameLoop);
    }

    function stop() {
        gameRunning = false;
        if (animationId) {
            cancelAnimationFrame(animationId);
            animationId = null;
        }
        document.removeEventListener('keydown', handleInput);
    }

    // ---- Piece Logic ----
    function randomPiece() {
        const name = PIECE_NAMES[Math.floor(Math.random() * PIECE_NAMES.length)];
        return {
            name,
            color: PIECES[name].color,
            rotation: 0,
            x: 3,
            y: 0
        };
    }

    function getShape(piece) {
        return PIECES[piece.name].shapes[piece.rotation];
    }

    function spawnPiece() {
        currentPiece = nextPiece;
        currentPiece.x = Math.floor((COLS - 3) / 2);
        currentPiece.y = 0;
        nextPiece = randomPiece();
        drawNext();

        if (collides(currentPiece, 0, 0)) {
            gameRunning = false;
            gameOver = true;
            onGameEnd(score, goalReached);
        }
    }

    function collides(piece, dx, dy, newRotation) {
        const rot = newRotation !== undefined ? newRotation : piece.rotation;
        const shape = PIECES[piece.name].shapes[rot];
        for (const [bx, by] of shape) {
            const nx = piece.x + bx + dx;
            const ny = piece.y + by + dy;
            if (nx < 0 || nx >= COLS || ny >= ROWS) return true;
            if (ny >= 0 && board[ny][nx]) return true;
        }
        return false;
    }

    function lockPiece() {
        const shape = getShape(currentPiece);
        for (const [bx, by] of shape) {
            const x = currentPiece.x + bx;
            const y = currentPiece.y + by;
            if (y >= 0 && y < ROWS && x >= 0 && x < COLS) {
                board[y][x] = currentPiece.color;
            }
        }
        clearLines();
        spawnPiece();
    }

    function clearLines() {
        let cleared = 0;
        for (let y = ROWS - 1; y >= 0; y--) {
            if (board[y].every(cell => cell !== null)) {
                board.splice(y, 1);
                board.unshift(Array(COLS).fill(null));
                cleared++;
                y++; // recheck this row
            }
        }
        if (cleared > 0) {
            linesCleared += cleared;
            score += SCORE_PER_LINES[cleared] || cleared * 25;
            updateScoreDisplay();

            // Speed up slightly
            dropInterval = Math.max(200, 800 - linesCleared * 30);

            // Check goal
            if (score >= GOAL_SCORE && !goalReached) {
                goalReached = true;
                gameRunning = false;
                onGoalReached(score);
            }
        }
    }

    // ---- Input ----
    function handleInput(e) {
        if (!gameRunning) return;

        switch (e.key) {
            case 'ArrowLeft':
                e.preventDefault();
                if (!collides(currentPiece, -1, 0)) currentPiece.x--;
                break;
            case 'ArrowRight':
                e.preventDefault();
                if (!collides(currentPiece, 1, 0)) currentPiece.x++;
                break;
            case 'ArrowDown':
                e.preventDefault();
                if (!collides(currentPiece, 0, 1)) currentPiece.y++;
                break;
            case 'ArrowUp':
                e.preventDefault();
                rotatePiece();
                break;
            case ' ':
                e.preventDefault();
                hardDrop();
                break;
        }
    }

    function rotatePiece() {
        const newRot = (currentPiece.rotation + 1) % 4;
        if (!collides(currentPiece, 0, 0, newRot)) {
            currentPiece.rotation = newRot;
        } else if (!collides(currentPiece, -1, 0, newRot)) {
            currentPiece.x--;
            currentPiece.rotation = newRot;
        } else if (!collides(currentPiece, 1, 0, newRot)) {
            currentPiece.x++;
            currentPiece.rotation = newRot;
        }
    }

    function hardDrop() {
        while (!collides(currentPiece, 0, 1)) {
            currentPiece.y++;
        }
        lockPiece();
    }

    // ---- Game Loop ----
    function gameLoop(time) {
        if (!gameRunning) return;

        const delta = time - lastTime;
        lastTime = time;
        dropTimer += delta;

        if (dropTimer >= dropInterval) {
            dropTimer = 0;
            if (!collides(currentPiece, 0, 1)) {
                currentPiece.y++;
            } else {
                lockPiece();
            }
        }

        draw();
        animationId = requestAnimationFrame(gameLoop);
    }

    // ---- Drawing ----
    function draw() {
        ctx.fillStyle = '#1a1a2e';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw grid lines
        ctx.strokeStyle = '#2a2a4e';
        ctx.lineWidth = 0.5;
        for (let x = 0; x <= COLS; x++) {
            ctx.beginPath();
            ctx.moveTo(x * BLOCK_SIZE, 0);
            ctx.lineTo(x * BLOCK_SIZE, canvas.height);
            ctx.stroke();
        }
        for (let y = 0; y <= ROWS; y++) {
            ctx.beginPath();
            ctx.moveTo(0, y * BLOCK_SIZE);
            ctx.lineTo(canvas.width, y * BLOCK_SIZE);
            ctx.stroke();
        }

        // Draw board
        for (let y = 0; y < ROWS; y++) {
            for (let x = 0; x < COLS; x++) {
                if (board[y][x]) {
                    drawBlock(ctx, x, y, board[y][x], BLOCK_SIZE);
                }
            }
        }

        // Draw ghost piece
        if (currentPiece) {
            let ghostY = currentPiece.y;
            while (!collides(currentPiece, 0, ghostY - currentPiece.y + 1)) {
                ghostY++;
            }
            const shape = getShape(currentPiece);
            ctx.globalAlpha = 0.2;
            for (const [bx, by] of shape) {
                drawBlock(ctx, currentPiece.x + bx, ghostY + by, currentPiece.color, BLOCK_SIZE);
            }
            ctx.globalAlpha = 1;

            // Draw current piece
            for (const [bx, by] of shape) {
                drawBlock(ctx, currentPiece.x + bx, currentPiece.y + by, currentPiece.color, BLOCK_SIZE);
            }
        }

        // Draw game over text
        if (gameOver) {
            ctx.fillStyle = 'rgba(0,0,0,0.7)';
            ctx.fillRect(0, canvas.height / 2 - 40, canvas.width, 80);
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 24px Fredoka One, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('GAME OVER', canvas.width / 2, canvas.height / 2 + 8);
        }
    }

    function drawBlock(context, x, y, color, size) {
        const px = x * size;
        const py = y * size;
        context.fillStyle = color;
        context.fillRect(px + 1, py + 1, size - 2, size - 2);

        // Highlight
        context.fillStyle = 'rgba(255,255,255,0.2)';
        context.fillRect(px + 1, py + 1, size - 2, 3);
        context.fillRect(px + 1, py + 1, 3, size - 2);

        // Shadow
        context.fillStyle = 'rgba(0,0,0,0.2)';
        context.fillRect(px + size - 3, py + 1, 2, size - 2);
        context.fillRect(px + 1, py + size - 3, size - 2, 2);
    }

    function drawNext() {
        nextCtx.fillStyle = '#1a1a2e';
        nextCtx.fillRect(0, 0, nextCanvas.width, nextCanvas.height);

        if (nextPiece) {
            const shape = PIECES[nextPiece.name].shapes[0];
            // Center the piece in the preview
            let minX = 4, maxX = 0, minY = 4, maxY = 0;
            for (const [bx, by] of shape) {
                minX = Math.min(minX, bx);
                maxX = Math.max(maxX, bx);
                minY = Math.min(minY, by);
                maxY = Math.max(maxY, by);
            }
            const pw = maxX - minX + 1;
            const ph = maxY - minY + 1;
            const offsetX = (4 - pw) / 2 - minX;
            const offsetY = (4 - ph) / 2 - minY;

            for (const [bx, by] of shape) {
                drawBlock(nextCtx, bx + offsetX, by + offsetY, nextPiece.color, NEXT_BLOCK_SIZE);
            }
        }
    }

    function updateScoreDisplay() {
        const scoreEl = document.getElementById('tetris-score');
        const linesEl = document.getElementById('tetris-lines');
        if (scoreEl) scoreEl.textContent = score;
        if (linesEl) linesEl.textContent = linesCleared;
    }

    // ---- Public API ----
    return { init, start, stop, GOAL_SCORE };
})();
