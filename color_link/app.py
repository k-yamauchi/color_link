from flask import Flask, render_template, jsonify, request
from color_link.game.color_link import ColorLinkGame
from color_link.agents.rule_based_agent import RuleBasedAgent
from color_link.agents.rl_agent import RLAgent
from color_link.agents.hybrid_agent import HybridAgent
import argparse
import os
import logging
import threading
import time
from datetime import datetime

# ロギングの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
game = ColorLinkGame()
rule_agent = RuleBasedAgent()
rl_agent = RLAgent()
hybrid_agent = HybridAgent()

# 現在使用中のAIエージェント
current_agent = None

# トレーニング関連のグローバル変数
training_thread = None
training_active = False
training_stats = {
    'games_played': 0,
    'games_won': 0,
    'win_rate': 0,
    'avg_turns': 0,
    'start_time': None,
    'elapsed_time': 0
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/new_game', methods=['POST'])
def new_game():
    data = request.json
    sequence_length = data.get('sequenceLength', 3)
    ai_type = data.get('aiType', None)
    debug_mode = data.get('debugMode', False)
    
    logger.info(f"新しいゲームを開始: シーケンス長={sequence_length}, AIタイプ={ai_type}, デバッグモード={debug_mode}")
    
    # AIタイプに基づいてエージェントを選択
    global current_agent
    if ai_type == 'rule':
        current_agent = rule_agent
    elif ai_type == 'rl':
        current_agent = rl_agent
        # 学習モード設定
        rl_agent.learning_mode = data.get('learningMode', False)
        if data.get('learningMode', False):
            rl_agent.load_q_table()
    elif ai_type == 'hybrid':
        current_agent = hybrid_agent
        # 学習モード設定
        hybrid_agent.learning_mode = data.get('learningMode', False)
        if data.get('learningMode', False):
            hybrid_agent.load_q_table()
    else:
        current_agent = None
    
    # 新しいゲームを開始
    game.new_game(sequence_length)
    
    state = game.get_state(hide_sequence=not debug_mode)
    logger.info(f"ゲーム状態: ターン={state['currentTurn']}/{state['maxTurns']}, 終了={state['gameOver']}")
    
    return jsonify({
        'game_state': state,
        'message': '新しいゲームを開始しました'
    })

@app.route('/api/make_move', methods=['POST'])
def make_move():
    data = request.json
    color = data.get('color')
    column = data.get('column')
    
    logger.info(f"プレイヤー移動: 色={color}, 列={column}")
    
    # 移動前の状態を保存（強化学習用）
    prev_state = game.get_state()
    
    # 移動の実行
    result = game.make_move(color, column)
    
    # 現在の状態を取得
    current_state = game.get_state(hide_sequence=not game.game_over and not data.get('debugMode', False))
    
    logger.info(f"移動結果: HIT={result['hits']}, BLOW={result['blows']}, ターン={current_state['currentTurn']}/{current_state['maxTurns']}, 終了={current_state['gameOver']}, 勝利={current_state['winner']}")
    
    # 強化学習の場合、学習データを更新
    if current_agent == rl_agent and rl_agent.learning_mode:
        reward = rl_agent.calculate_reward(current_state)
        rl_agent.learn(prev_state, {'color': color, 'column': column}, reward, current_state)
        
        # ゲーム終了時にQ値テーブルを保存
        if current_state['gameOver']:
            rl_agent.save_q_table()
    
    return jsonify({
        'game_state': current_state,
        'result': result
    })

@app.route('/api/ai_move', methods=['GET'])
def ai_move():
    logger.info(f"AI行動のリクエストを受信: current_agent={current_agent}")
    
    if current_agent is None:
        logger.warning("AIが選択されていません")
        return jsonify({'error': 'AIが選択されていません'}), 400
    
    try:
        # 移動前の状態を保存（強化学習用）
        prev_state = game.get_state()
        
        # AIによる次の行動の決定
        action = current_agent.decide_next_move(game.get_state())
        logger.info(f"AI行動: 色={action['color']}, 列={action['column']}")
        
        # 実際に移動を行う
        result = game.make_move(action['color'], action['column'])
        
        # 現在の状態を取得
        debug_mode = request.args.get('debugMode', 'false').lower() == 'true'
        current_state = game.get_state(hide_sequence=not game.game_over and not debug_mode)
        logger.info(f"AI移動結果: HIT={result['hits']}, BLOW={result['blows']}, ターン={current_state['currentTurn']}/{current_state['maxTurns']}, 終了={current_state['gameOver']}, 勝利={current_state['winner']}")
        
        # 強化学習の場合、学習データを更新
        if current_agent == rl_agent and rl_agent.learning_mode:
            reward = rl_agent.calculate_reward(current_state)
            rl_agent.learn(prev_state, action, reward, current_state)
            
            # ゲーム終了時にQ値テーブルを保存
            if current_state['gameOver']:
                rl_agent.save_q_table()
        
        return jsonify({
            'action': action,
            'game_state': current_state,
            'result': result
        })
    except Exception as e:
        logger.error(f"AI行動処理中にエラーが発生: {str(e)}", exc_info=True)
        return jsonify({'error': f'AI行動処理中にエラーが発生: {str(e)}'}), 500

@app.route('/api/save_model', methods=['POST'])
def save_model():
    if rl_agent.learning_mode:
        rl_agent.save_q_table()
        return jsonify({'success': True, 'message': 'モデルを保存しました'})
    return jsonify({'success': False, 'message': '学習モードが有効ではありません'})

@app.route('/api/start_training', methods=['POST'])
def start_training():
    global training_thread, training_active, training_stats
    
    if training_active:
        return jsonify({'success': False, 'message': 'トレーニングは既に実行中です'})
    
    # トレーニングパラメータの取得
    data = request.json
    num_games = data.get('numGames', 1000)
    sequence_length = data.get('sequenceLength', 3)
    agent_type = data.get('agentType', 'rl')  # 'rl' または 'hybrid'
    
    # トレーニング統計情報の初期化
    training_stats = {
        'games_played': 0,
        'games_won': 0,
        'win_rate': 0,
        'avg_turns': 0,
        'start_time': datetime.now().isoformat(),
        'elapsed_time': 0
    }
    
    # トレーニングを開始
    training_active = True
    
    def training_process():
        global training_active, training_stats
        logger.info(f"トレーニングを開始: {num_games}ゲーム, シーケンス長={sequence_length}, エージェント={agent_type}")
        
        total_turns = 0
        
        # エージェントを選択
        agent = rl_agent if agent_type == 'rl' else hybrid_agent
        
        # エージェントを学習モードに設定
        agent.learning_mode = True
        agent.load_q_table()  # 既存のQテーブルをロード
        
        try:
            for i in range(num_games):
                if not training_active:  # 停止リクエストがあれば中断
                    break
                
                # 新しいゲームを開始（トレーニング用のゲームインスタンス）
                training_game = ColorLinkGame()
                training_game.new_game(sequence_length)
                
                # このゲームでの総ターン数
                game_turns = 0
                
                # ゲームが終了するまでプレイ
                while not training_game.game_over:
                    if not training_active:  # 停止リクエストがあれば中断
                        break
                    
                    # 現在の状態を取得
                    state = training_game.get_state()
                    
                    # エージェントに次の行動を決定させる
                    action = agent.decide_next_move(state)
                    
                    # 行動を実行
                    result = training_game.make_move(action['color'], action['column'])
                    
                    # 新しい状態を取得
                    new_state = training_game.get_state()
                    
                    # 報酬を計算し、学習させる
                    reward = agent.calculate_reward(new_state)
                    agent.learn(state, action, reward, new_state)
                    
                    game_turns += 1
                
                # ゲーム終了後の統計情報更新
                training_stats['games_played'] += 1
                if training_game.winner:
                    training_stats['games_won'] += 1
                total_turns += game_turns
                
                # 進捗率と統計を更新
                training_stats['win_rate'] = (training_stats['games_won'] / training_stats['games_played']) * 100
                training_stats['avg_turns'] = total_turns / training_stats['games_played']
                
                # 100ゲームごとにログ出力とモデル保存
                if i % 100 == 0:
                    logger.info(f"トレーニング進捗: {i}/{num_games} ゲーム完了, "
                                f"勝率: {training_stats['win_rate']:.2f}%, "
                                f"平均ターン: {training_stats['avg_turns']:.2f}")
                    agent.save_q_table()
            
            # トレーニング完了後の最終保存
            agent.save_q_table()
            logger.info(f"トレーニング完了: {training_stats['games_played']}ゲーム, "
                        f"勝率: {training_stats['win_rate']:.2f}%, "
                        f"平均ターン: {training_stats['avg_turns']:.2f}")
        
        except Exception as e:
            logger.error(f"トレーニング中にエラーが発生: {str(e)}", exc_info=True)
        
        finally:
            # トレーニング終了
            training_active = False
    
    # トレーニングをバックグラウンドスレッドで実行
    training_thread = threading.Thread(target=training_process)
    training_thread.daemon = True  # メインプログラム終了時にスレッドも終了
    training_thread.start()
    
    return jsonify({
        'success': True,
        'message': f'トレーニングを開始しました: {num_games}ゲーム'
    })

@app.route('/api/training_status', methods=['GET'])
def training_status():
    global training_active, training_stats
    
    # 経過時間を更新
    if training_active and training_stats['start_time']:
        start_time = datetime.fromisoformat(training_stats['start_time'])
        elapsed = (datetime.now() - start_time).total_seconds()
        training_stats['elapsed_time'] = elapsed
    
    return jsonify({
        'active': training_active,
        'stats': training_stats
    })

@app.route('/api/stop_training', methods=['POST'])
def stop_training():
    global training_active
    
    if not training_active:
        return jsonify({'success': False, 'message': 'トレーニングは実行中ではありません'})
    
    # トレーニングを停止
    training_active = False
    logger.info("トレーニングの停止をリクエストしました")
    
    return jsonify({
        'success': True,
        'message': 'トレーニングを停止しました'
    })

def main():
    parser = argparse.ArgumentParser(description='カラーリンクゲームサーバー')
    parser.add_argument('--host', default='127.0.0.1', help='ホストアドレス')
    parser.add_argument('--port', type=int, default=5000, help='ポート番号')
    parser.add_argument('--debug', action='store_true', help='デバッグモード')
    
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == '__main__':
    main() 