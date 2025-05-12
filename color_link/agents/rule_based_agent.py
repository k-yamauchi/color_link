import random
from typing import Dict, Any, List, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)

class RuleBasedAgent:
    def __init__(self):
        self.colors = ['red', 'blue', 'yellow', 'green', 'purple']
        self.possible_sequences = []
        self.last_column = -1
        logger.info("ルールベースエージェントが初期化されました")
    
    def decide_next_move(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """ルールベースでの次の行動を決定する"""
        board = game_state['board']
        history = game_state['history']
        sequence_length = game_state.get('sequenceLength', 3)
        
        logger.info(f"行動決定開始: 履歴数={len(history)}, 可能シーケンス数={len(self.possible_sequences)}")
        
        # ゲーム開始時は可能なシーケンスを全て列挙
        if len(history) == 0:
            self.possible_sequences = self._generate_all_sequences(sequence_length)
            logger.info(f"初期シーケンス生成: {len(self.possible_sequences)}個のシーケンス")
            # ランダムな列と色で開始
            action = {
                'color': random.choice(self.colors),
                'column': random.randint(0, 4)
            }
            logger.info(f"初期行動: 色={action['color']}, 列={action['column']}")
            return action
        
        # 直前の行動結果からシーケンスを絞り込む
        if len(history) > 0:
            last_move = history[-1]
            column = last_move['column']
            hits = last_move['hits']
            blows = last_move['blows']
            
            logger.info(f"前回の結果: 列={column}, HIT={hits}, BLOW={blows}")
            
            # 現在の列の状態
            column_state = [board[i][column]['color'] for i in range(sequence_length)]
            logger.info(f"列の状態: {column_state}")
            
            # シーケンスを絞り込む
            prev_count = len(self.possible_sequences)
            self.possible_sequences = self._filter_sequences(self.possible_sequences, column_state, hits, blows)
            logger.info(f"シーケンス絞り込み: {prev_count} -> {len(self.possible_sequences)}個")
        
        # 絞り込んだ候補がなければランダム選択
        if len(self.possible_sequences) == 0:
            logger.info("候補がないため、ランダム選択します")
            action = {
                'color': random.choice(self.colors),
                'column': random.randint(0, 4)
            }
            logger.info(f"ランダム行動: 色={action['color']}, 列={action['column']}")
            return action
        
        # 最も情報が得られる行動を選択
        action = self._choose_best_action(game_state, self.possible_sequences)
        logger.info(f"選択された行動: 色={action['color']}, 列={action['column']}, 候補数={len(self.possible_sequences)}")
        
        # 可能性のあるターゲットシーケンスを表示（最大5つ）
        if len(self.possible_sequences) <= 5:
            logger.info(f"可能性のあるターゲット: {self.possible_sequences}")
        else:
            logger.info(f"可能性のあるターゲット（一部）: {self.possible_sequences[:5]}... 他{len(self.possible_sequences)-5}個")
        
        return action
    
    def _generate_all_sequences(self, sequence_length: int) -> List[List[str]]:
        """可能なすべてのシーケンスを生成"""
        all_sequences = []
        
        def backtrack(current_sequence):
            if len(current_sequence) == sequence_length:
                all_sequences.append(current_sequence.copy())
                return
            
            for color in self.colors:
                current_sequence.append(color)
                backtrack(current_sequence)
                current_sequence.pop()
        
        backtrack([])
        return all_sequences
    
    def _filter_sequences(self, sequences: List[List[str]], column_state: List[str], 
                          hits: int, blows: int) -> List[List[str]]:
        """HITとBLOWの結果に基づいてシーケンス候補を絞り込む"""
        filtered = []
        
        for sequence in sequences:
            # このシーケンスがカラムの状態と同じHIT/BLOWになるか検証
            h, b = self._calculate_hits_blows(sequence, column_state)
            if h == hits and b == blows:
                filtered.append(sequence)
        
        return filtered
    
    def _calculate_hits_blows(self, sequence: List[str], column_state: List[str]) -> Tuple[int, int]:
        """シーケンスとカラム状態からHITとBLOWを計算"""
        hits = 0
        blows = 0
        
        # コピーを作成
        seq_copy = sequence.copy()
        col_copy = column_state.copy()
        
        # HITをチェック
        for i in range(len(sequence)):
            if seq_copy[i] == col_copy[i]:
                hits += 1
                seq_copy[i] = None
                col_copy[i] = None
        
        # BLOWをチェック
        for i in range(len(sequence)):
            if seq_copy[i] is not None:
                for j in range(len(column_state)):
                    if col_copy[j] is not None and seq_copy[i] == col_copy[j]:
                        blows += 1
                        col_copy[j] = None
                        break
        
        return hits, blows
    
    def _choose_best_action(self, game_state: Dict[str, Any], 
                           possible_sequences: List[List[str]]) -> Dict[str, Any]:
        """最も情報量の多い行動を選択"""
        board = game_state['board']
        sequence_length = game_state.get('sequenceLength', 3)
        
        # 前回と同じ列は避ける
        available_columns = [i for i in range(5) if i != self.last_column]
        if len(available_columns) == 0:
            available_columns = list(range(5))
        
        logger.info(f"利用可能な列: {available_columns}")
        
        best_action = None
        best_score = -1
        
        action_scores = []
        
        for column in available_columns:
            for color in self.colors:
                # この行動のスコアを計算
                score = self._evaluate_action(game_state, column, color, possible_sequences)
                action_scores.append((color, column, score))
                
                if score > best_score:
                    best_score = score
                    best_action = {'color': color, 'column': column}
        
        # 上位5つのスコアをログに出力
        sorted_scores = sorted(action_scores, key=lambda x: x[2], reverse=True)
        logger.info(f"トップスコア: {sorted_scores[:5]}")
        
        # 最適な行動がなければランダム選択
        if best_action is None:
            best_action = {
                'color': random.choice(self.colors),
                'column': random.choice(available_columns)
            }
            logger.info("最適な行動が見つからなかったため、ランダム選択します")
        
        self.last_column = best_action['column']
        return best_action
    
    def _evaluate_action(self, game_state: Dict[str, Any], column: int, color: str, 
                         possible_sequences: List[List[str]]) -> float:
        """行動の情報量を評価"""
        board = game_state.get('board', [])
        sequence_length = game_state.get('sequenceLength', 3)
        
        # ボードの構造をチェック
        if not board or len(board) < sequence_length or len(board[0]) <= column:
            logger.warning(f"不正なボード構造またはカラム: board={board}, column={column}")
            return random.random()  # ランダムなスコアを返す
        
        # この行動後の列の状態をシミュレート
        # 注意: 正確なシミュレーションのため、現在の列の配置をシフトさせて新しい色を先頭に追加
        try:
            current_column = [board[i][column]['color'] for i in range(sequence_length)]
            new_column_state = [color] + current_column[:-1] if sequence_length > 1 else [color]
            
            logger.debug(f"シミュレーション - 列{column}に色{color}を挿入: {current_column} -> {new_column_state}")
            
            # 各HIT/BLOWの組み合わせに対する可能性を計算
            possibilities = {}
            
            for sequence in possible_sequences:
                hits, blows = self._calculate_hits_blows(sequence, new_column_state)
                key = f"{hits}:{blows}"
                
                if key not in possibilities:
                    possibilities[key] = 0
                possibilities[key] += 1
            
            # 情報量を計算（エントロピー）
            # 可能な状態が多いほど情報量が大きい
            total = len(possible_sequences)
            if total == 0:
                return 0
            
            entropy = 0
            
            for count in possibilities.values():
                prob = count / total
                entropy -= prob * np.log2(prob) if prob > 0 else 0
            
            # 赤色だけを選び続けないようにランダム要素を追加
            if random.random() < 0.1:  # 10%の確率で少しランダム性を加える
                entropy += random.random() * 0.5
            
            # HIT数が多そうな行動を優先（特に候補が少ないとき）
            if len(possible_sequences) < 10:
                max_hit_key = max(possibilities.keys(), key=lambda k: int(k.split(':')[0]) if k.split(':')[0].isdigit() else 0, default="0:0")
                max_hit = int(max_hit_key.split(':')[0]) if max_hit_key.split(':')[0].isdigit() else 0
                entropy += max_hit * 0.2  # HITが多いほど少しボーナス
            
            logger.debug(f"行動の評価 - 列{column}に色{color}を挿入: エントロピー={entropy:.4f}")
            return entropy
            
        except (IndexError, KeyError, ValueError) as e:
            logger.warning(f"行動評価中にエラー: {str(e)}, board={board}, column={column}")
            return random.random()  # エラーが発生した場合はランダムなスコアを返す 