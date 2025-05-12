import random
import json
import os
import logging
import numpy as np
from typing import Dict, Any, List, Tuple
from color_link.agents.rule_based_agent import RuleBasedAgent

logger = logging.getLogger(__name__)

class RLAgent:
    def __init__(self, learning_rate: float = 0.1, discount_factor: float = 0.9, exploration_rate: float = 0.5):
        self.colors = ['red', 'blue', 'yellow', 'green', 'purple']
        self.q_table = {}  # Q値テーブル
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate  # 探索率
        self.learning_mode = False
        self.last_column = -1  # 前回の列を記憶して偏りを防ぐ
        self.last_color = None  # 前回の色を記憶して偏りを防ぐ
        self.exploration_count = 0  # 探索回数のカウント
        
        # 論理的推論のためにルールベースエージェントの機能を利用
        self.rule_agent = RuleBasedAgent()
        self.possible_sequences = []  # 可能性のある色の組み合わせ
        
        # Q値テーブルの初期化
        self._initialize_q_table()
        logger.info("強化学習エージェントが初期化されました")
    
    def _initialize_q_table(self) -> None:
        """Q値テーブルを初期化"""
        # 一部の代表的な状態と行動の組み合わせに初期Q値を設定
        default_state = self._get_state_key({'board': [[{'color': 'red'} for _ in range(5)] for _ in range(5)], 'history': []})
        
        if default_state not in self.q_table:
            self.q_table[default_state] = {}
            
            # すべての色と列の組み合わせに対して初期Q値を設定（少しランダム性を持たせる）
            for color in self.colors:
                for column in range(5):
                    action_key = f"{color}:{column}"
                    # 初期値に微小な乱数を加えて偏りを軽減
                    self.q_table[default_state][action_key] = 0.1 + random.random() * 0.01
    
    def _extract_features(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """ゲーム状態から特徴量を抽出"""
        board = game_state['board']
        history = game_state['history']
        sequence_length = game_state.get('sequenceLength', 3)
        
        # ボードの状態を数値特徴量に変換
        board_features = []
        color_values = {'red': 0, 'blue': 0.25, 'yellow': 0.5, 'green': 0.75, 'purple': 1}
        
        for row in board:
            for cell in row:
                board_features.append(color_values[cell['color']])
        
        # 履歴から特徴量を抽出（直近の操作結果）
        history_features = []
        for h in history[-3:] if len(history) >= 3 else history:
            history_features.extend([h['hits'] / 5, h['blows'] / 5])
        
        # 可能性のある色の組み合わせから特徴量を抽出
        possibility_features = []
        
        # ゲーム開始時は可能なシーケンスを全て列挙
        if len(self.possible_sequences) == 0 and len(history) == 0:
            self.possible_sequences = self.rule_agent._generate_all_sequences(sequence_length)
            logger.info(f"初期シーケンス生成: {len(self.possible_sequences)}個のシーケンス")
        # 直前の行動結果からシーケンスを絞り込む
        elif len(history) > 0:
            last_move = history[-1]
            column = last_move['column']
            hits = last_move['hits']
            blows = last_move['blows']
            
            # 現在の列の状態
            column_state = [board[i][column]['color'] for i in range(sequence_length)]
            
            # シーケンスを絞り込む
            prev_count = len(self.possible_sequences)
            self.possible_sequences = self.rule_agent._filter_sequences(self.possible_sequences, column_state, hits, blows)
            logger.info(f"RL: シーケンス絞り込み: {prev_count} -> {len(self.possible_sequences)}個")
        
        # 可能性のある組み合わせの数を特徴量に変換
        num_possibilities = len(self.possible_sequences)
        if num_possibilities > 0:
            possibility_features.append(min(1.0, num_possibilities / 100))  # 正規化した可能性の数
            
            # 各色の出現頻度を特徴量として追加
            color_counts = {color: 0 for color in self.colors}
            for seq in self.possible_sequences[:min(50, len(self.possible_sequences))]:  # 最大50個までサンプリング
                for color in seq:
                    color_counts[color] += 1
            
            total_counts = sum(color_counts.values()) if sum(color_counts.values()) > 0 else 1
            for color in self.colors:
                possibility_features.append(color_counts[color] / total_counts)
        else:
            # 可能性がない場合はゼロで埋める
            possibility_features = [0.0] * (1 + len(self.colors))
        
        return {
            'board_features': board_features,
            'history_features': history_features,
            'possibility_features': possibility_features
        }
    
    def _get_state_key(self, game_state: Dict[str, Any]) -> str:
        """状態をハッシュ化してキーに変換"""
        features = self._extract_features(game_state)
        
        # 特徴量の精度を下げて状態空間を削減
        simplified_board_features = [round(f * 4) / 4 for f in features['board_features']]
        
        # 可能性のある組み合わせの特徴量を追加
        possibility_info = features['possibility_features']
        
        return json.dumps({
            'board': simplified_board_features,
            'history': features['history_features'],
            'possibilities': possibility_info
        })
    
    def _get_action_key(self, action: Dict[str, Any]) -> str:
        """行動をキーに変換"""
        return f"{action['color']}:{action['column']}"
    
    def _get_diverse_exploration_action(self) -> Dict[str, Any]:
        """より多様な探索行動を生成"""
        # 前回と異なる列を選ぶ
        available_columns = [i for i in range(5) if i != self.last_column]
        if not available_columns:  # 念のため
            available_columns = list(range(5))
        
        # 前回と異なる色を選ぶ確率を高める
        available_colors = self.colors.copy()
        if self.last_color:
            # 80%の確率で前回と異なる色を選ぶ
            if random.random() < 0.8 and self.last_color in available_colors:
                available_colors.remove(self.last_color)
        
        # 可能性のある組み合わせに基づく探索（20%の確率で利用）
        if random.random() < 0.2 and len(self.possible_sequences) > 0:
            try:
                # 可能性のある組み合わせから色の出現頻度を計算
                color_freq = {color: 0 for color in self.colors}
                for seq in self.possible_sequences:
                    for c in seq:
                        color_freq[c] += 1
                
                # 出現頻度に応じた確率で色を選択
                total_freq = sum(color_freq.values())
                if total_freq > 0:
                    # 利用可能な色だけに絞る
                    weights = [color_freq[c] for c in available_colors]
                    
                    # 重みの合計が0より大きいことを確認
                    if sum(weights) > 0:
                        color = random.choices(available_colors, weights=weights, k=1)[0]
                    else:
                        color = random.choice(available_colors)
                else:
                    color = random.choice(available_colors)
            except Exception as e:
                logger.warning(f"色の選択中にエラー: {str(e)}")
                color = random.choice(available_colors)
        else:
            color = random.choice(available_colors)
        
        column = random.choice(available_columns)
        
        # 記憶を更新
        self.last_column = column
        self.last_color = color
        
        self.exploration_count += 1
        logger.debug(f"多様な探索行動: 色={color}, 列={column}, 探索回数={self.exploration_count}")
        
        return {
            'color': color,
            'column': column
        }
    
    def _logical_exploration_action(self) -> Dict[str, Any]:
        """論理的な推論に基づく探索行動"""
        # 可能性のある組み合わせが十分にある場合は論理的な推論を利用
        if len(self.possible_sequences) > 5:
            try:
                # 正しい構造のダミーボードを作成
                sequence_length = 3  # デフォルト値
                dummy_board = [[{'color': 'red'} for _ in range(5)] for _ in range(sequence_length)]
                game_state = {
                    'board': dummy_board, 
                    'history': [], 
                    'sequenceLength': sequence_length
                }
                action = self.rule_agent._choose_best_action(game_state, self.possible_sequences)
                logger.info(f"論理的探索行動: 色={action['color']}, 列={action['column']}")
                
                # 記憶を更新
                self.last_column = action['column']
                self.last_color = action['color']
                
                return action
            except Exception as e:
                logger.warning(f"論理的探索中にエラー: {str(e)}")
                # エラーが発生した場合は多様な探索にフォールバック
                return self._get_diverse_exploration_action()
        else:
            # 可能性のある組み合わせが少ない場合は多様な探索
            return self._get_diverse_exploration_action()
    
    def decide_next_move(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """強化学習に基づいて次の行動を決定"""
        # ゲーム状態から特徴量を抽出し、状態キーを取得
        state_key = self._get_state_key(game_state)
        history_length = len(game_state['history'])
        
        # 探索戦略：序盤は多様な探索を強化
        # 学習モードやゲーム序盤では探索率を上げる
        effective_exploration_rate = self.exploration_rate
        
        # 学習モードの場合は探索率を調整
        if self.learning_mode:
            # 序盤（最初の5手）は積極的に探索
            if history_length < 5:
                effective_exploration_rate = max(0.7, self.exploration_rate)
            # ゲームが進むにつれ徐々に探索率を下げる
            else:
                effective_exploration_rate = max(0.3, self.exploration_rate - history_length * 0.02)
        else:
            # 学習モードでなくても、たまには探索する（10%）
            effective_exploration_rate = 0.1
        
        logger.info(f"行動決定開始: 履歴数={history_length}, 有効探索率={effective_exploration_rate:.2f}")
        
        # 探索 vs 活用（ε-greedy戦略）
        if random.random() < effective_exploration_rate:
            # 50%の確率で論理的探索を使用、それ以外は多様な探索
            if random.random() < 0.5:
                action = self._logical_exploration_action()
            else:
                action = self._get_diverse_exploration_action()
            logger.info(f"探索行動: 色={action['color']}, 列={action['column']}")
            return action
        else:
            # Q値に基づく最適な行動（活用）
            q_values = self.q_table.get(state_key, {})
            
            # この状態のQ値がない場合は初期化
            if not q_values:
                q_values = {}
                for color in self.colors:
                    for column in range(5):
                        action_key = f"{color}:{column}"
                        # 微小なランダム値を加えて初期値に多様性を持たせる
                        q_values[action_key] = 0.1 + random.random() * 0.01
                
                self.q_table[state_key] = q_values
                logger.info(f"新しい状態のQ値を初期化: キー={state_key[:20]}...")
            
            # 最大Q値を持つ行動を選択
            # ただし、同じQ値を持つ行動が複数ある場合はランダムに選択
            max_q_value = max(q_values.values())
            best_actions = [
                (color, int(column))
                for action_key, value in q_values.items()
                if abs(value - max_q_value) < 1e-6  # 浮動小数点の比較を考慮
                for color, column in [action_key.split(':')]
            ]
            
            # 複数の最適行動からランダムに選択
            if best_actions:
                color, column = random.choice(best_actions)
                action = {'color': color, 'column': column}
                # 選ばれた行動を記憶
                self.last_column = column
                self.last_color = color
                logger.info(f"最適行動: 色={color}, 列={column}, Q値={max_q_value:.4f}, 候補数={len(best_actions)}")
                return action
            
            # フォールバック（通常は発生しない）
            logger.warning("最適行動が見つからず、フォールバックを使用")
            return self._get_diverse_exploration_action()
    
    def learn(self, prev_state: Dict[str, Any], action: Dict[str, Any], 
              reward: float, new_state: Dict[str, Any]) -> None:
        """Q値を更新して学習"""
        if not self.learning_mode:
            return
        
        prev_state_key = self._get_state_key(prev_state)
        action_key = self._get_action_key(action)
        
        # 現在の状態・行動に対するQ値を取得
        if prev_state_key not in self.q_table:
            self.q_table[prev_state_key] = {}
        
        if action_key not in self.q_table[prev_state_key]:
            self.q_table[prev_state_key][action_key] = 0.1 + random.random() * 0.01
        
        current_q = self.q_table[prev_state_key][action_key]
        
        # 次の状態における最大Q値を見つける
        next_state_key = self._get_state_key(new_state)
        next_q_values = self.q_table.get(next_state_key, {})
        
        max_next_q = 0
        if next_q_values:
            max_next_q = max(next_q_values.values())
        
        # 学習率を動的に調整（初めての状態・行動ペアの場合は学習率を高くする）
        dynamic_learning_rate = self.learning_rate * 2 if current_q == 0.1 else self.learning_rate
        
        # Q値を更新（Q学習アルゴリズム）
        new_q = current_q + dynamic_learning_rate * (reward + self.discount_factor * max_next_q - current_q)
        
        # 過去の履歴から良い行動をより強化
        if new_state.get('history', []) and len(new_state['history']) > 0:
            last_move = new_state['history'][-1]
            if last_move['hits'] > 0:  # HITがあればさらにボーナス
                new_q += 0.05 * last_move['hits']
        
        # Q値を保存
        self.q_table[prev_state_key][action_key] = new_q
        
        logger.debug(f"Q値更新: {action_key}, {current_q:.4f} -> {new_q:.4f}, 報酬={reward:.4f}")
    
    def calculate_reward(self, game_state: Dict[str, Any]) -> float:
        """行動に対する報酬を計算"""
        if not game_state.get('history'):
            return 0
        
        history = game_state['history']
        last_move = history[-1]
        
        # 基本的な報酬：HITとBLOW
        hit_reward = last_move['hits'] * 5  # HITには高い報酬
        blow_reward = last_move['blows'] * 1  # BLOWにはやや低い報酬
        
        # ゲーム終了時の報酬
        if game_state.get('gameOver'):
            if game_state.get('winner'):
                reward = 50  # 勝利で大きな報酬
                logger.info(f"勝利報酬: +{reward}")
                return reward
            else:
                reward = -20  # 敗北でペナルティ
                logger.info(f"敗北報酬: {reward}")
                return reward
        
        # 可能性のある組み合わせの削減に対する報酬
        possibility_reward = 0
        prev_possibilities_count = len(self.possible_sequences) if hasattr(self, 'prev_possibilities_count') else 0
        curr_possibilities_count = len(self.possible_sequences)
        
        if prev_possibilities_count > 0:
            # 可能性が減少するほど報酬を大きくする
            reduction_ratio = 1 - (curr_possibilities_count / prev_possibilities_count)
            possibility_reward = max(0, reduction_ratio * 10)  # 最大10の報酬
            logger.info(f"可能性削減報酬: {possibility_reward:.2f} (削減率={reduction_ratio:.2f})")
        
        # 次回の報酬計算のために現在の可能性数を保存
        self.prev_possibilities_count = curr_possibilities_count
        
        # 以前の手との比較による追加報酬（HITやBLOWが増えていれば報酬）
        additional_reward = 0
        if len(history) >= 2:
            prev_move = history[-2]
            hit_diff = last_move['hits'] - prev_move['hits']
            blow_diff = last_move['blows'] - prev_move['blows']
            
            if hit_diff > 0:
                additional_reward += hit_diff * 3  # HIT増加は高く評価
            elif hit_diff < 0:
                additional_reward -= abs(hit_diff) * 1  # HIT減少は軽いペナルティ
            
            if blow_diff > 0:
                additional_reward += blow_diff * 1  # BLOW増加も評価
        
        # 同じ手を繰り返すことに対するペナルティ
        repeat_penalty = 0
        if len(history) >= 2:
            # 直前の手と同じ列・色を使った場合の小さなペナルティ
            if (last_move['column'] == history[-2]['column'] and 
                last_move['color'] == history[-2]['color']):
                repeat_penalty = -1
        
        # 可能性の数に応じたボーナス/ペナルティ
        possibility_count_reward = 0
        if curr_possibilities_count == 1:
            # 可能性が1つに絞られた場合は大きなボーナス
            possibility_count_reward = 10
        elif curr_possibilities_count == 0:
            # 可能性がなくなった場合はペナルティ（矛盾した行動）
            possibility_count_reward = -5
        
        total_reward = hit_reward + blow_reward + additional_reward + repeat_penalty + possibility_reward + possibility_count_reward
        
        logger.debug(f"報酬計算: HIT={hit_reward}, BLOW={blow_reward}, 追加={additional_reward}, " +
                    f"ペナルティ={repeat_penalty}, 可能性削減={possibility_reward}, " +
                    f"可能性数={possibility_count_reward}, 合計={total_reward}")
        
        return total_reward
    
    def save_q_table(self) -> None:
        """Q値テーブルをJSONファイルに保存"""
        try:
            directory = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'models')
            os.makedirs(directory, exist_ok=True)
            
            file_path = os.path.join(directory, 'q_table.json')
            # バックアップを作成
            backup_path = os.path.join(directory, 'q_table_backup.json')
            if os.path.exists(file_path):
                try:
                    import shutil
                    shutil.copy2(file_path, backup_path)
                    logger.info(f"Q値テーブルのバックアップを作成: {backup_path}")
                except Exception as e:
                    logger.warning(f"バックアップ作成に失敗: {e}")
            
            # テーブルサイズを確認（大きすぎる場合は警告）
            table_size = len(self.q_table)
            if table_size > 1000:
                logger.warning(f"Q値テーブルが大きい: {table_size}状態")
            
            with open(file_path, 'w') as f:
                json.dump(self.q_table, f)
            
            logger.info(f"Q値テーブルを保存しました: {file_path} ({table_size}状態)")
        except Exception as e:
            logger.error(f"Q値テーブルの保存に失敗しました: {e}")
            print(f"Q値テーブルの保存に失敗しました: {e}")
    
    def load_q_table(self) -> None:
        """Q値テーブルをJSONファイルから読み込み"""
        try:
            file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'models', 'q_table.json')
            if not os.path.exists(file_path):
                logger.info("Q値テーブルファイルが見つかりません。新しいテーブルを初期化します。")
                return
            
            with open(file_path, 'r') as f:
                self.q_table = json.load(f)
            
            table_size = len(self.q_table)
            logger.info(f"Q値テーブルを読み込みました: {file_path} ({table_size}状態)")
        except Exception as e:
            logger.error(f"Q値テーブルの読み込みに失敗しました: {e}")
            print(f"Q値テーブルの読み込みに失敗しました: {e}") 