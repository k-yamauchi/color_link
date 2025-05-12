document.addEventListener('DOMContentLoaded', () => {
    // ゲーム状態
    let gameState = null;
    let selectedColor = 'red';
    let aiEnabled = false;
    let aiType = 'none';
    let aiDelay = 1000;
    let aiInterval = null;
    let learningMode = false;
    let debugMode = false;
    let gameMode = 'normal'; // 'normal', 'eval', 'train'
    let trainInterval = null;
    const aiIntervalDelay = 1000;
    
    // 評価モードの状態
    let evalStats = {
        totalGames: 0,
        completedGames: 0,
        currentAgentIndex: 0,
        agents: [],
        isRunning: false,
        // 各エージェントの個別データは agents 配列内に保存
        // 例: { type: 'rule', wins: 0, totalTurns: 0, minTurns: Infinity, completedGames: 0 }
    };
    
    // トレーニングモードの状態
    let trainStats = {
        totalEpisodes: 0,
        completedEpisodes: 0,
        wins: 0,
        totalReward: 0,
        isRunning: false,
        explorationRate: 0.5,
        elapsedTime: 0,
        lastUpdate: null,
        agentType: 'rl'  // 'rl' または 'hybrid'
    };
    
    // DOM要素
    const gameBoard = document.getElementById('game-board');
    const historyList = document.getElementById('history-list');
    const messageBox = document.getElementById('message-box');
    const targetSequence = document.getElementById('target-sequence');
    const newGameBtn = document.getElementById('new-game');
    const aiMoveBtn = document.getElementById('ai-move');
    const aiTypeSelect = document.getElementById('ai-type');
    const aiOptions = document.getElementById('ai-options');
    const rlOptions = document.getElementById('rl-options');
    const sequenceLengthSelect = document.getElementById('sequence-length');
    const aiDelayInput = document.getElementById('ai-delay');
    const delayValue = document.getElementById('delay-value');
    const learningModeCheck = document.getElementById('learning-mode');
    const debugModeCheck = document.getElementById('debug-mode');
    const gameModeSelect = document.getElementById('game-mode');
    
    // 評価モード要素
    const evalPanel = document.getElementById('eval-panel');
    const evalGamesInput = document.getElementById('eval-games');
    const evalSeqLengthSelect = document.getElementById('eval-seq-length');
    const startEvalBtn = document.getElementById('start-eval');
    const stopEvalBtn = document.getElementById('stop-eval');
    const winRateSpan = document.getElementById('win-rate');
    const avgTurnsSpan = document.getElementById('avg-turns');
    const minTurnsSpan = document.getElementById('min-turns');
    const progressValueSpan = document.getElementById('progress-value');
    const progressBarFill = document.querySelector('#eval-progress .progress-bar-fill');
    
    // エージェント選択と比較表示要素
    const evalRuleAgentCheck = document.getElementById('eval-rule-agent');
    const evalRLAgentCheck = document.getElementById('eval-rl-agent');
    const evalHybridAgentCheck = document.getElementById('eval-hybrid-agent');
    const evalComparisonDiv = document.getElementById('eval-comparison');
    const comparisonResultsTable = document.getElementById('comparison-results');
    
    // トレーニングモード要素
    const trainPanel = document.getElementById('train-panel');
    const trainEpisodesInput = document.getElementById('train-episodes');
    const trainSeqLengthSelect = document.getElementById('train-seq-length');
    const trainExplorationInput = document.getElementById('train-exploration');
    const explorationValueSpan = document.getElementById('exploration-value');
    const startTrainBtn = document.getElementById('start-train');
    const stopTrainBtn = document.getElementById('stop-train');
    const saveModelBtn = document.getElementById('save-model');
    const completedEpisodesSpan = document.getElementById('completed-episodes');
    const trainWinRateSpan = document.getElementById('train-win-rate');
    const avgRewardSpan = document.getElementById('avg-reward');
    const trainProgressValueSpan = document.getElementById('train-progress-value');
    const trainProgressBarFill = document.querySelector('#train-progress .progress-bar-fill');
    const trainAgentType = document.getElementById('train-agent-type');  // 追加: エージェント選択用要素
    
    // ログ表示用の要素
    const trainLogElement = document.getElementById('train-log');
    
    // トレーニングログの追加
    function addTrainingLog(message, type = 'info') {
        if (!trainLogElement) return;

        const now = new Date();
        const timeStr = now.toLocaleTimeString();
        
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${type}`;
        
        const timeSpan = document.createElement('span');
        timeSpan.className = 'log-time';
        timeSpan.textContent = `[${timeStr}]`;
        
        const messageSpan = document.createElement('span');
        messageSpan.className = 'log-message';
        messageSpan.textContent = ` ${message}`;
        
        logEntry.appendChild(timeSpan);
        logEntry.appendChild(messageSpan);
        
        trainLogElement.appendChild(logEntry);
        trainLogElement.scrollTop = trainLogElement.scrollHeight;
        
        // ログが多すぎる場合は古いものを削除
        while (trainLogElement.childNodes.length > 100) {
            trainLogElement.removeChild(trainLogElement.firstChild);
        }
    }
    
    // 色の定義
    const colors = {
        'red': '#e53935',
        'blue': '#1e88e5',
        'yellow': '#fdd835',
        'green': '#43a047',
        'purple': '#8e24aa'
    };
    
    // 初期化
    initGame();
    setupEventListeners();
    
    // イベントリスナーの設定
    function setupEventListeners() {
        // 新しいゲームボタン
        newGameBtn.addEventListener('click', startNewGame);
        
        // AI行動ボタン
        aiMoveBtn.addEventListener('click', toggleAIPlay);
        
        // 色選択ボタン
        document.querySelectorAll('.color-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                selectedColor = btn.dataset.color;
                
                // 選択状態の更新
                document.querySelectorAll('.color-btn').forEach(b => {
                    b.classList.remove('selected');
                });
                btn.classList.add('selected');
            });
        });
        
        // ゲームモード変更
        gameModeSelect.addEventListener('change', (e) => {
            const prevGameMode = gameMode;
            gameMode = e.target.value;
            
            // パネルの表示/非表示
            evalPanel.style.display = gameMode === 'eval' ? 'block' : 'none';
            trainPanel.style.display = gameMode === 'train' ? 'block' : 'none';
            
            // 自動プレイは必ず停止
            stopAIAutoPlay();
            
            // モードによってAI設定を変更（変更のみで自動開始はしない）
            if (gameMode === 'eval') {
                if (aiType === 'none') {
                    aiTypeSelect.value = 'rule';
                    aiType = 'rule';
                    aiEnabled = true;
                }
                showMessage('エージェント評価モードでは「評価開始」ボタンを押すとAIが自動的にプレイします。');
            } else if (gameMode === 'train') {
                // トレーニングモードでは選択されたエージェントタイプを使用
                const selectedTrainAgent = trainAgentType.value;
                aiTypeSelect.value = selectedTrainAgent;
                aiType = selectedTrainAgent;
                aiEnabled = true;
                learningModeCheck.checked = true;
                learningMode = true;
                showMessage('強化学習トレーニングモードでは「トレーニング開始」ボタンを押すとバックグラウンドでAIが学習します。');
            } else {
                // 通常モードでは何もしない（ユーザーの設定を維持）
                showMessage('通常モードでは「AI行動」ボタンを押すとAIの自動プレイが開始/停止します。');
            }
            
            // AI関連オプションの表示/非表示を更新
            aiOptions.style.display = aiEnabled ? 'flex' : 'none';
            rlOptions.style.display = (aiType === 'rl' || aiType === 'hybrid') ? 'flex' : 'none';
            
            // AI行動ボタンの有効/無効を更新
            aiMoveBtn.disabled = !aiEnabled || (gameState && gameState.gameOver);
            
            // 前回のモードと違う場合のみ新しいゲームを開始
            if (prevGameMode !== gameMode) {
                startNewGame();
            }
        });
        
        // AIタイプ変更
        aiTypeSelect.addEventListener('change', (e) => {
            aiType = e.target.value;
            aiEnabled = aiType !== 'none';
            
            // AI関連オプションの表示/非表示
            aiOptions.style.display = aiEnabled ? 'flex' : 'none';
            rlOptions.style.display = aiType === 'rl' ? 'flex' : 'none';
            
            // AI行動ボタンの有効/無効
            aiMoveBtn.disabled = !aiEnabled || (gameState && gameState.gameOver);
            
            // 自動プレイは必ず停止する
            stopAIAutoPlay();
            
            // AIタイプが変更されたことをユーザーに通知
            if (aiEnabled) {
                showMessage(`AIタイプを「${aiType === 'rule' ? 'ルールベース' : '強化学習'}」に変更しました。「AI行動」ボタンを押すとAIが動作します。`);
            } else {
                showMessage('AIを無効にしました。');
            }
        });
        
        // AI速度変更
        aiDelayInput.addEventListener('input', (e) => {
            aiDelay = parseInt(e.target.value);
            delayValue.textContent = (aiDelay / 1000).toFixed(1) + '秒';
            
            // 自動プレイ中なら再開
            if (aiInterval) {
                stopAIAutoPlay();
                startAIAutoPlay();
            }
        });
        
        // 学習モード切り替え
        learningModeCheck.addEventListener('change', (e) => {
            learningMode = e.target.checked;
        });
        
        // デバッグモード切り替え
        debugModeCheck.addEventListener('change', (e) => {
            debugMode = e.target.checked;
            updateTargetSequence();
        });
        
        // 評価モード関連
        startEvalBtn.addEventListener('click', startEvaluation);
        stopEvalBtn.addEventListener('click', stopEvaluation);
        
        // トレーニングモード関連
        startTrainBtn.addEventListener('click', startTraining);
        stopTrainBtn.addEventListener('click', stopTraining);
        saveModelBtn.addEventListener('click', saveTrainedModel);
        
        // 探索率変更
        trainExplorationInput.addEventListener('input', (e) => {
            trainStats.explorationRate = parseFloat(e.target.value);
            explorationValueSpan.textContent = trainStats.explorationRate.toFixed(1);
        });
        
        // エージェントタイプ変更
        trainAgentType.addEventListener('change', (e) => {
            trainStats.agentType = e.target.value;
            
            // トレーニングモードがアクティブならAIタイプも同期
            if (gameMode === 'train') {
                aiTypeSelect.value = trainStats.agentType;
                aiType = trainStats.agentType;
                
                // 学習オプションの表示/非表示を更新
                rlOptions.style.display = (aiType === 'rl' || aiType === 'hybrid') ? 'flex' : 'none';
            }
            
            // エージェントタイプが変更されたときのメッセージ
            if (trainStats.agentType === 'hybrid') {
                addTrainingLog('ハイブリッドエージェントを選択しました。ルールベースと強化学習の組み合わせで学習します。', 'info');
            } else {
                addTrainingLog('強化学習エージェントを選択しました。純粋な強化学習で学習します。', 'info');
            }
        });
    }
    
    // ゲームの初期化
    function initGame() {
        // 最初の色を選択
        document.querySelector('.color-btn[data-color="red"]').classList.add('selected');
        
        // ゲーム開始
        startNewGame();
    }
    
    // 新しいゲームを開始
    function startNewGame() {
        // 必ず自動プレイを停止
        stopAIAutoPlay();
        
        const sequenceLength = parseInt(sequenceLengthSelect.value);
        
        // APIリクエスト
        fetch('/api/new_game', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sequenceLength: sequenceLength,
                aiType: aiType,
                learningMode: learningMode,
                debugMode: debugMode,
                gameMode: gameMode
            })
        })
        .then(response => response.json())
        .then(data => {
            gameState = data.game_state;
            
            // UIの更新
            renderGameBoard();
            renderHistory();
            updateTargetSequence();
            
            // メッセージ表示
            showMessage('新しいゲームを開始しました。色と列を選んでプレイしましょう！');
            
            // AI行動ボタンの有効化（ゲームが終了していなければ）
            aiMoveBtn.disabled = !aiEnabled || (gameState && gameState.gameOver);
            
            // モードに関係なく、新しいゲーム開始時には自動的にAIを開始しない
            // 評価モードの場合は、startEvaluation関数が呼ばれたときに自動的に開始する
        })
        .catch(error => {
            console.error('エラー:', error);
            showMessage('ゲーム開始中にエラーが発生しました。');
        });
    }
    
    // ゲームボードの描画
    function renderGameBoard() {
        if (!gameState) return;
        
        gameBoard.innerHTML = '';
        
        for (let i = 0; i < 5; i++) {
            for (let j = 0; j < 5; j++) {
                const cell = document.createElement('div');
                cell.className = 'board-cell';
                cell.style.backgroundColor = colors[gameState.board[i][j].color];
                
                // 列クリックで色を挿入
                cell.dataset.column = j;
                cell.addEventListener('click', () => makeMove(selectedColor, j));
                
                gameBoard.appendChild(cell);
            }
        }
    }
    
    // 履歴の描画
    function renderHistory() {
        if (!gameState) return;
        
        historyList.innerHTML = '';
        
        // 履歴を新しい順に表示
        const sortedHistory = [...gameState.history].reverse();
        
        for (const move of sortedHistory) {
            const item = document.createElement('div');
            item.className = 'history-item';
            
            const colorDiv = document.createElement('div');
            colorDiv.className = 'history-color';
            colorDiv.style.backgroundColor = colors[move.color];
            
            const columnDiv = document.createElement('div');
            columnDiv.className = 'history-column';
            columnDiv.textContent = `列${move.column + 1}`;
            
            const resultDiv = document.createElement('div');
            resultDiv.className = 'history-result';
            resultDiv.innerHTML = `
                <span class="hit-blow hit">${move.hits} HIT</span> / 
                <span class="hit-blow blow">${move.blows} BLOW</span>
            `;
            
            item.appendChild(colorDiv);
            item.appendChild(columnDiv);
            item.appendChild(resultDiv);
            historyList.appendChild(item);
        }
    }
    
    // ターゲットシーケンスの表示
    function updateTargetSequence() {
        if (!gameState) return;
        
        const sequenceCells = targetSequence.querySelector('.sequence-cells');
        sequenceCells.innerHTML = '';
        
        const sequenceLength = gameState.sequenceLength || 3;
        
        if (debugMode || gameState.gameOver) {
            // デバッグモードかゲーム終了時はシーケンスを表示
            for (let i = 0; i < sequenceLength; i++) {
                const container = document.createElement('div');
                container.className = 'sequence-cell-container';
                
                // 位置のラベル追加
                const label = document.createElement('div');
                label.className = 'sequence-label';
                label.textContent = `${i + 1}:`;
                
                const cell = document.createElement('div');
                cell.className = 'sequence-cell';
                if (gameState.targetSequence) {
                    cell.style.backgroundColor = colors[gameState.targetSequence[i]];
                }
                
                container.appendChild(label);
                container.appendChild(cell);
                sequenceCells.appendChild(container);
            }
        } else {
            // そうでなければ「?」を表示
            for (let i = 0; i < sequenceLength; i++) {
                const container = document.createElement('div');
                container.className = 'sequence-cell-container';
                
                // 位置のラベル追加
                const label = document.createElement('div');
                label.className = 'sequence-label';
                label.textContent = `${i + 1}:`;
                
                const cell = document.createElement('div');
                cell.className = 'sequence-cell';
                cell.style.backgroundColor = '#ccc';
                cell.textContent = '?';
                cell.style.display = 'flex';
                cell.style.justifyContent = 'center';
                cell.style.alignItems = 'center';
                
                container.appendChild(label);
                container.appendChild(cell);
                sequenceCells.appendChild(container);
            }
        }
    }
    
    // メッセージの表示
    function showMessage(message) {
        messageBox.textContent = message;
    }
    
    // プレイヤーの移動
    function makeMove(color, column) {
        if (!gameState || gameState.gameOver) return;
        
        // AIの自動プレイを停止
        stopAIAutoPlay();
        
        // APIリクエスト
        fetch('/api/make_move', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                color: color,
                column: column,
                debugMode: debugMode
            })
        })
        .then(response => response.json())
        .then(data => {
            if (!data.result.valid) {
                showMessage(data.result.message);
                return;
            }
            
            gameState = data.game_state;
            
            // UIの更新
            renderGameBoard();
            renderHistory();
            updateTargetSequence();
            
            // 現在のターン数と最大ターン数
            const currentTurn = gameState.currentTurn || gameState.history.length;
            const maxTurns = gameState.maxTurns || 12;
            
            // ゲーム終了チェック
            if (gameState.gameOver) {
                if (gameState.winner) {
                    showMessage(`おめでとうございます！正解を見つけました！(${currentTurn}ターン)`);
                } else {
                    showMessage(`ゲームオーバー。正解を見つけられませんでした。(${maxTurns}ターン)`);
                }
                aiMoveBtn.disabled = true;
            } else if (data.result.hits > 0 || data.result.blows > 0) {
                showMessage(`${data.result.hits} HIT / ${data.result.blows} BLOW (${currentTurn}/${maxTurns}ターン)`);
            } else {
                showMessage(`一致する色はありませんでした。(${currentTurn}/${maxTurns}ターン)`);
            }
        })
        .catch(error => {
            console.error('エラー:', error);
            showMessage('移動中にエラーが発生しました。');
        });
    }
    
    // AIプレイのトグル
    function toggleAIPlay() {
        if (!gameState || gameState.gameOver) return;
        
        // AIが有効かチェック
        if (!aiEnabled) {
            showMessage('AIが選択されていません。AIタイプを選択してください。');
            return;
        }
        
        if (aiInterval) {
            // AIが自動プレイ中なら停止
            stopAIAutoPlay();
            aiMoveBtn.textContent = 'AI行動';
            showMessage('AIの自動行動を停止しました。');
        } else {
            // 停止中なら開始
            startAIAutoPlay();
            aiMoveBtn.textContent = 'AI停止';
            showMessage('AIの自動行動を開始しました。');
        }
    }
    
    // AI自動プレイの開始
    function startAIAutoPlay() {
        if (aiInterval) {
            clearInterval(aiInterval);
        }
        
        if (!aiEnabled || !gameState || gameState.gameOver) return;
        
        aiInterval = setInterval(() => {
            if (gameState && !gameState.gameOver) {
                makeAIMove();
            } else {
                stopAIAutoPlay();
            }
        }, aiDelay);
    }
    
    // AI自動プレイの停止
    function stopAIAutoPlay() {
        if (aiInterval) {
            clearInterval(aiInterval);
            aiInterval = null;
            
            // ボタンのテキストを元に戻す
            if (aiMoveBtn) {
                aiMoveBtn.textContent = 'AI行動';
            }
        }
    }
    
    // AI移動
    function makeAIMove() {
        if (!gameState || gameState.gameOver) return;
        
        // AIが有効かチェック
        if (!aiEnabled) {
            showMessage('AIが選択されていません。AIタイプを選択してください。');
            return;
        }
        
        console.log(`AI行動を実行します: タイプ=${aiType}`);
        
        // ボタンを一時的に無効化
        aiMoveBtn.disabled = true;
        
        // APIリクエスト
        fetch(`/api/ai_move?debugMode=${debugMode}`)
            .then(response => {
                console.log('AI行動のレスポンスを受信:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('AI行動のデータを受信:', data);
                if (data.error) {
                    showMessage(data.error);
                    aiMoveBtn.disabled = false;
                    return;
                }
                
                gameState = data.game_state;
                
                // UIの更新
                renderGameBoard();
                renderHistory();
                updateTargetSequence();
                
                // 現在のターン数と最大ターン数
                const currentTurn = gameState.currentTurn || gameState.history.length;
                const maxTurns = gameState.maxTurns || 12;
                
                // AIの行動を表示
                const colorName = {
                    'red': '赤',
                    'blue': '青',
                    'yellow': '黄',
                    'green': '緑',
                    'purple': '紫'
                }[data.action.color];
                
                showMessage(`AIは ${colorName} を列${data.action.column + 1}に挿入しました。結果: ${data.result.hits} HIT / ${data.result.blows} BLOW (${currentTurn}/${maxTurns}ターン)`);
                
                // ゲーム終了チェック
                if (gameState.gameOver) {
                    if (gameState.winner) {
                        showMessage(`AIが正解を見つけました！(${currentTurn}ターン)`);
                    } else {
                        showMessage(`ゲームオーバー。AIは正解を見つけられませんでした。(${maxTurns}ターン)`);
                    }
                    aiMoveBtn.disabled = true;
                } else {
                    aiMoveBtn.disabled = false;
                }
            })
            .catch(error => {
                console.error('AI行動中にエラーが発生しました:', error);
                showMessage('AI行動中にエラーが発生しました。');
                aiMoveBtn.disabled = false;
            });
    }
    
    // エージェント評価モードの開始
    function startEvaluation() {
        if (evalStats.isRunning) return;
        
        // 選択されたエージェントを確認
        const useRuleAgent = evalRuleAgentCheck.checked;
        const useRLAgent = evalRLAgentCheck.checked;
        const useHybridAgent = evalHybridAgentCheck.checked;
        
        if (!useRuleAgent && !useRLAgent && !useHybridAgent) {
            showMessage('少なくとも1つのエージェントを選択してください。');
            return;
        }
        
        // 評価設定
        evalStats = {
            totalGames: parseInt(evalGamesInput.value),
            completedGames: 0,
            currentAgentIndex: 0,
            agents: [],
            isRunning: true
        };
        
        // 選択されたエージェントを設定
        if (useRuleAgent) {
            evalStats.agents.push({
                type: 'rule',
                name: 'ルールベース',
                wins: 0,
                totalTurns: 0,
                minTurns: Infinity,
                completedGames: 0
            });
        }
        
        if (useRLAgent) {
            evalStats.agents.push({
                type: 'rl',
                name: '強化学習',
                wins: 0,
                totalTurns: 0,
                minTurns: Infinity,
                completedGames: 0
            });
        }
        
        if (useHybridAgent) {
            evalStats.agents.push({
                type: 'hybrid',
                name: 'ハイブリッド',
                wins: 0,
                totalTurns: 0,
                minTurns: Infinity,
                completedGames: 0
            });
        }
        
        // UIの更新
        winRateSpan.textContent = '0%';
        avgTurnsSpan.textContent = '0';
        minTurnsSpan.textContent = '-';
        progressValueSpan.textContent = `0/${evalStats.totalGames * evalStats.agents.length}`;
        progressBarFill.style.width = '0%';
        
        // 比較表示を初期化
        comparisonResultsTable.innerHTML = '';
        evalComparisonDiv.style.display = evalStats.agents.length > 1 ? 'block' : 'none';
        
        startEvalBtn.disabled = true;
        stopEvalBtn.disabled = false;
        
        showMessage(`エージェント評価を開始します。${evalStats.agents.length}種類のエージェントで各${evalStats.totalGames}ゲームを実行します...`);
        
        // 評価プロセスの開始
        runEvaluationGame();
    }
    
    // 評価ゲームの実行
    function runEvaluationGame() {
        if (!evalStats.isRunning) return;
        
        // 現在のエージェント情報
        const currentAgent = evalStats.agents[evalStats.currentAgentIndex];
        
        // 新しいゲームのパラメータ設定
        const sequenceLength = parseInt(evalSeqLengthSelect.value);
        
        // AIタイプを現在のエージェントに合わせる
        aiType = currentAgent.type;
        
        fetch('/api/new_game', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sequenceLength: sequenceLength,
                aiType: aiType,
                learningMode: false,
                debugMode: true,
                gameMode: 'eval'
            })
        })
        .then(response => response.json())
        .then(data => {
            gameState = data.game_state;
            
            // UIの更新
            renderGameBoard();
            renderHistory();
            updateTargetSequence();
            
            // 評価のためのAI自動プレイ
            runEvaluationLoop();
        })
        .catch(error => {
            console.error('評価ゲームの開始中にエラー:', error);
            showMessage('評価ゲームの開始中にエラーが発生しました。');
            stopEvaluation();
        });
    }
    
    // 評価ループ（AI自動プレイ）
    function runEvaluationLoop() {
        if (!evalStats.isRunning || !gameState) return;
        
        // 現在のエージェント
        const currentAgent = evalStats.agents[evalStats.currentAgentIndex];
        
        if (gameState.gameOver) {
            // ゲーム結果の記録
            currentAgent.completedGames++;
            
            if (gameState.winner) {
                currentAgent.wins++;
                const turns = gameState.currentTurn;
                currentAgent.totalTurns += turns;
                
                if (turns < currentAgent.minTurns) {
                    currentAgent.minTurns = turns;
                }
            }
            
            // 総進捗の更新
            evalStats.completedGames++;
            
            // 評価統計の更新
            updateEvaluationStats();
            
            // 次のゲームか次のエージェントか終了
            if (currentAgent.completedGames < evalStats.totalGames) {
                // 同じエージェントで次のゲーム
                setTimeout(runEvaluationGame, 500);
            } else if (evalStats.currentAgentIndex < evalStats.agents.length - 1) {
                // 次のエージェントに進む
                evalStats.currentAgentIndex++;
                setTimeout(runEvaluationGame, 500);
            } else {
                // 全エージェントの評価が完了
                showMessage(`評価完了！全${evalStats.completedGames}ゲームの評価が終了しました。`);
                
                // 比較結果を表示（複数エージェントの場合）
                if (evalStats.agents.length > 1) {
                    displayComparisonResults();
                }
                
                stopEvaluation();
            }
            
            return;
        }
        
        // AIによる行動
        fetch(`/api/ai_move?debugMode=true&evaluationMode=true`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error('AI行動エラー:', data.error);
                    return;
                }
                
                gameState = data.game_state;
                
                // UIの更新
                renderGameBoard();
                renderHistory();
                updateTargetSequence();
                
                // 評価速度を調整（より速く）
                setTimeout(runEvaluationLoop, 10);
            })
            .catch(error => {
                console.error('評価中にエラー:', error);
                stopEvaluation();
            });
    }
    
    // 評価統計の更新
    function updateEvaluationStats() {
        // 現在のエージェント
        const currentAgent = evalStats.agents[evalStats.currentAgentIndex];
        
        // 現在選択されているエージェントの統計を表示
        const winRate = currentAgent.completedGames > 0 ? 
            (currentAgent.wins / currentAgent.completedGames * 100).toFixed(1) : '0';
        
        const avgTurns = currentAgent.wins > 0 ? 
            (currentAgent.totalTurns / currentAgent.wins).toFixed(1) : '0';
        
        // UI更新
        winRateSpan.textContent = `${winRate}%`;
        avgTurnsSpan.textContent = avgTurns;
        minTurnsSpan.textContent = currentAgent.minTurns < Infinity ? currentAgent.minTurns : '-';
        
        // プログレスバー更新（全体の進捗）
        const totalGamesToPlay = evalStats.totalGames * evalStats.agents.length;
        progressValueSpan.textContent = `${evalStats.completedGames}/${totalGamesToPlay}`;
        const progress = (evalStats.completedGames / totalGamesToPlay * 100).toFixed(1);
        progressBarFill.style.width = `${progress}%`;
        
        // 現在評価中のエージェント表示を更新
        const agentTypes = {
            'rule': 'ルールベース',
            'rl': '強化学習',
            'hybrid': 'ハイブリッド'
        };
        
        showMessage(`評価中: ${agentTypes[currentAgent.type]}エージェント (${currentAgent.completedGames}/${evalStats.totalGames}ゲーム完了)`);
    }
    
    // 評価の停止
    function stopEvaluation() {
        evalStats.isRunning = false;
        startEvalBtn.disabled = false;
        stopEvalBtn.disabled = true;
        
        // 複数エージェントを評価した場合は比較結果を表示
        if (evalStats.agents && evalStats.agents.length > 1 && evalStats.completedGames > 0) {
            displayComparisonResults();
        }
        
        // 通常モードに戻す
        startNewGame();
    }
    
    // 強化学習トレーニングの開始
    function startTraining() {
        if (trainStats.isRunning) return;
        
        // トレーニング設定
        const numGames = parseInt(trainEpisodesInput.value);
        const sequenceLength = parseInt(trainSeqLengthSelect.value);
        const agentType = trainAgentType.value;  // エージェントタイプを取得
        
        trainStats = {
            totalEpisodes: numGames,
            completedEpisodes: 0,
            wins: 0,
            totalReward: 0,
            isRunning: true,
            explorationRate: parseFloat(trainExplorationInput.value),
            elapsedTime: 0,
            lastUpdate: new Date(),
            agentType: agentType  // エージェントタイプを保存
        };
        
        // UIの更新
        completedEpisodesSpan.textContent = '0';
        trainWinRateSpan.textContent = '0%';
        avgRewardSpan.textContent = '0';
        trainProgressValueSpan.textContent = `0/${trainStats.totalEpisodes}`;
        trainProgressBarFill.style.width = '0%';
        
        startTrainBtn.disabled = true;
        stopTrainBtn.disabled = false;
        
        // ログをクリア
        trainLogElement.innerHTML = '';
        
        showMessage(`強化学習トレーニングを開始します。${numGames}ゲームを実行します...`);
        addTrainingLog(`トレーニングを開始: ${numGames}ゲーム, シーケンス長=${sequenceLength}, エージェント=${agentType === 'rl' ? '強化学習' : 'ハイブリッド'}`, 'success');
        
        // トレーニングプロセスの開始
        fetch('/api/start_training', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                numGames: numGames,
                sequenceLength: sequenceLength,
                agentType: agentType  // エージェントタイプをAPIに送信
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                addTrainingLog(data.message, 'success');
                
                // 定期的にトレーニング状態を取得
                trainInterval = setInterval(fetchTrainingStatus, 1000);
            } else {
                showMessage('トレーニングの開始に失敗しました: ' + data.message);
                addTrainingLog('トレーニング開始失敗: ' + data.message, 'error');
                stopTraining();
            }
        })
        .catch(error => {
            console.error('トレーニング開始エラー:', error);
            showMessage('トレーニングの開始中にエラーが発生しました。');
            addTrainingLog('トレーニング開始エラー: ' + error.message, 'error');
            stopTraining();
        });
    }
    
    // トレーニング状態の取得
    function fetchTrainingStatus() {
        if (!trainStats.isRunning) return;
        
        fetch('/api/training_status')
            .then(response => response.json())
            .then(data => {
                // 非アクティブの場合、トレーニング完了
                if (!data.active) {
                    addTrainingLog('トレーニングが完了しました', 'success');
                    showMessage('トレーニングが完了しました！');
                    stopTraining();
                    return;
                }
                
                const stats = data.stats;
                
                // 統計の更新
                if (stats) {
                    // 前回の表示から変化がある場合だけログに表示
                    if (trainStats.completedEpisodes !== stats.games_played) {
                        const newGames = stats.games_played - trainStats.completedEpisodes;
                        
                        if (newGames > 0 && stats.games_played % 10 === 0) {
                            addTrainingLog(
                                `進捗: ${stats.games_played}/${trainStats.totalEpisodes} ゲーム完了 ` +
                                `(勝率: ${stats.win_rate.toFixed(1)}%, 平均ターン: ${stats.avg_turns.toFixed(1)})`, 
                                'info'
                            );
                        }
                    }
                    
                    trainStats.completedEpisodes = stats.games_played;
                    trainStats.wins = stats.games_won;
                    trainStats.elapsedTime = stats.elapsed_time;
                    
                    // UI更新
                    updateTrainingStats(stats);
                }
            })
            .catch(error => {
                console.error('トレーニング状態取得エラー:', error);
                addTrainingLog('状態取得エラー: ' + error.message, 'warning');
            });
    }
    
    // トレーニング統計の更新
    function updateTrainingStats(stats) {
        if (!stats) return;
        
        // UI更新
        completedEpisodesSpan.textContent = stats.games_played;
        trainWinRateSpan.textContent = `${stats.win_rate.toFixed(1)}%`;
        avgRewardSpan.textContent = stats.avg_turns.toFixed(1);
        
        // 経過時間を表示
        const elapsedTime = formatTime(stats.elapsed_time);
        
        // プログレスバー更新
        trainProgressValueSpan.textContent = `${stats.games_played}/${trainStats.totalEpisodes} (${elapsedTime})`;
        const progress = (stats.games_played / trainStats.totalEpisodes * 100);
        trainProgressBarFill.style.width = `${Math.min(100, progress)}%`;
    }
    
    // 秒数を時間:分:秒形式に変換
    function formatTime(seconds) {
        seconds = Math.floor(seconds);
        const hrs = Math.floor(seconds / 3600);
        seconds %= 3600;
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        
        return `${hrs > 0 ? hrs + ':' : ''}${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    
    // トレーニングの停止
    function stopTraining() {
        if (trainInterval) {
            clearInterval(trainInterval);
            trainInterval = null;
        }
        
        if (!trainStats.isRunning) return;
        
        trainStats.isRunning = false;
        startTrainBtn.disabled = false;
        stopTrainBtn.disabled = true;
        
        addTrainingLog('トレーニング停止をリクエスト...', 'warning');
        
        fetch('/api/stop_training', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('トレーニングを停止しました。');
                    addTrainingLog('トレーニングを停止しました', 'success');
                } else {
                    showMessage('トレーニングの停止に失敗しました: ' + data.message);
                    addTrainingLog('トレーニング停止失敗: ' + data.message, 'error');
                }
                
                // 通常モードに戻す
                startNewGame();
            })
            .catch(error => {
                console.error('トレーニング停止エラー:', error);
                showMessage('トレーニングの停止中にエラーが発生しました。');
                addTrainingLog('トレーニング停止エラー: ' + error.message, 'error');
            });
    }
    
    // モデルの保存
    function saveTrainedModel() {
        fetch('/api/save_model', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('モデルを保存しました。');
                } else {
                    showMessage('モデルの保存に失敗しました: ' + data.message);
                }
            })
            .catch(error => {
                console.error('モデル保存エラー:', error);
                showMessage('モデルの保存中にエラーが発生しました。');
            });
    }
    
    // 比較結果の表示
    function displayComparisonResults() {
        // 比較表示を有効化
        evalComparisonDiv.style.display = 'block';
        comparisonResultsTable.innerHTML = '';
        
        // 勝率でソート
        const sortedAgents = [...evalStats.agents].sort((a, b) => {
            const winRateA = a.completedGames > 0 ? (a.wins / a.completedGames) : 0;
            const winRateB = b.completedGames > 0 ? (b.wins / b.completedGames) : 0;
            return winRateB - winRateA;  // 降順
        });
        
        // 最もパフォーマンスが良いエージェント
        const bestAgent = sortedAgents[0];
        
        // 各エージェントの行を追加
        sortedAgents.forEach(agent => {
            const row = document.createElement('tr');
            
            // 勝者を強調
            if (agent === bestAgent) {
                row.classList.add('winner-row');
            }
            
            const winRate = agent.completedGames > 0 ? 
                (agent.wins / agent.completedGames * 100).toFixed(1) : '0';
            
            const avgTurns = agent.wins > 0 ? 
                (agent.totalTurns / agent.wins).toFixed(1) : '-';
            
            const minTurns = agent.minTurns < Infinity ? agent.minTurns : '-';
            
            row.innerHTML = `
                <td class="agent-name">${agent.name}</td>
                <td>${winRate}%</td>
                <td>${avgTurns}</td>
                <td>${minTurns}</td>
            `;
            
            comparisonResultsTable.appendChild(row);
        });
        
        // 比較メッセージ
        const bestWinRate = bestAgent.completedGames > 0 ? 
            (bestAgent.wins / bestAgent.completedGames * 100).toFixed(1) : '0';
        
        showMessage(`評価の結果、${bestAgent.name}エージェントが${bestWinRate}%の勝率で最も良いパフォーマンスを示しました。`);
    }
}); 