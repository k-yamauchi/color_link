import random
import json
import os
import logging
import numpy as np
from typing import Dict, Any, List, Tuple
from color_link.agents.rule_based_agent import RuleBasedAgent
from color_link.agents.rl_agent import RLAgent

logger = logging.getLogger(__name__)

class HybridAgent:
    def __init__(self, rule_weight: float = 0.7, learning_rate: float = 0.1, discount_factor: float = 0.9):
        """
        ルールベースと強化学習を組み合わせたハイブリッドエージェント
        
        Args:
            rule_weight: ルールベースの意見の重み（0〜1）
            learning_rate: 学習率
            discount_factor: 割引率
        """
        self.colors = ['red', 'blue', 'yellow', 'green', 'purple']
        
        # 両方のエージェントをサブコンポーネントとして初期化
        self.rule_agent = RuleBasedAgent()
        self.rl_agent = RLAgent(learning_rate=learning_rate, discount_factor=discount_factor)
        
        # ハイブリッド設定
        self.rule_weight = rule_weight  # ルールベースの意見の重み（0〜1）
        self.rl_weight = 1.0 - rule_weight  # 強化学習の意見の重み
        
        # ゲーム進行による重み調整用変数
        self.initial_rule_weight = rule_weight
        self.game_progress_factor = 0.5  # ゲームの進行に応じた重み調整係数
        
        # 学習モード
        self._learning_mode = False
        
        # 可能性のあるシーケンス候補（ルールベースエージェントから共有）
        self.possible_sequences = []
        
        # 状態記憶
        self.prev_state = None
        self.prev_action = None
        
        logger.info(f"ハイブリッドエージェントが初期化されました（ルール重み={rule_weight:.2f}）")
    
    @property
    def learning_mode(self):
        return self._learning_mode
    
    @learning_mode.setter
    def learning_mode(self, value):
        self._learning_mode = value
        # 内部のRLエージェントの学習モードも同期させる
        self.rl_agent.learning_mode = value
        logger.info(f"ハイブリッドエージェントの学習モードを {value} に設定しました")
    
    def decide_next_move(self, game_state: Dict[str, Any]) -> Dict[str, Any]:
        """ハイブリッド戦略に基づいて次の行動を決定"""
        try:
            history = game_state['history']
            sequence_length = game_state.get('sequenceLength', 3)
            current_turn = len(history)
            
            # 可能性のあるシーケンスを更新（ルールベースと強化学習で共有）
            self._update_possible_sequences(game_state)
            
            # ゲーム状態に応じた重み調整
            self._adjust_weights(game_state)
            
            # ルールベースエージェントの意見を取得
            try:
                rule_action = self.rule_agent.decide_next_move(game_state)
            except Exception as e:
                logger.error(f"ルールベース行動決定エラー: {str(e)}")
                # エラー時はランダムな行動
                rule_action = {
                    'color': random.choice(self.colors),
                    'column': random.randint(0, 4)
                }
            
            # 強化学習エージェントの意見を取得
            try:
                rl_action = self.rl_agent.decide_next_move(game_state)
            except Exception as e:
                logger.error(f"強化学習行動決定エラー: {str(e)}")
                # エラー時はランダムな行動
                rl_action = {
                    'color': random.choice(self.colors),
                    'column': random.randint(0, 4)
                }
            
            # 行動の決定方法
            action_method = self._decide_action_method(game_state)
            final_action = None
            
            if action_method == 'rule':
                # ルールベースの意見を採用
                final_action = rule_action
                logger.info(f"ルールベース戦略を採用: 色={final_action['color']}, 列={final_action['column']}")
            
            elif action_method == 'rl':
                # 強化学習の意見を採用
                final_action = rl_action
                logger.info(f"強化学習戦略を採用: 色={final_action['color']}, 列={final_action['column']}")
            
            elif action_method == 'weighted':
                # 両方の意見を重み付けで統合
                final_action = self._combine_actions(rule_action, rl_action, game_state)
                logger.info(f"統合戦略を採用: 色={final_action['color']}, 列={final_action['column']} " +
                          f"(ルール重み={self.rule_weight:.2f}, RL重み={self.rl_weight:.2f})")
            
            # 行動を記憶（学習用）
            self.prev_state = game_state
            self.prev_action = final_action
            
            return final_action
            
        except Exception as e:
            # 最終的なフォールバック：何かエラーが起きたら安全にランダムな行動をとる
            logger.error(f"行動決定中に重大なエラー: {str(e)}")
            fallback_action = {
                'color': random.choice(self.colors),
                'column': random.randint(0, 4)
            }
            return fallback_action
    
    def _update_possible_sequences(self, game_state: Dict[str, Any]) -> None:
        """可能性のあるシーケンスを更新（RLエージェントとの共有も行う）"""
        try:
            board = game_state.get('board', [])
            history = game_state.get('history', [])
            sequence_length = game_state.get('sequenceLength', 3)
            
            # ゲーム開始時は可能なシーケンスを全て列挙
            if len(history) == 0:
                self.possible_sequences = self.rule_agent._generate_all_sequences(sequence_length)
                # RLエージェントとも共有
                self.rl_agent.possible_sequences = self.possible_sequences.copy()
                logger.info(f"初期シーケンス生成: {len(self.possible_sequences)}個のシーケンス")
                return
            
            # 直前の行動結果からシーケンスを絞り込む
            if len(history) > 0 and len(board) >= sequence_length:
                last_move = history[-1]
                column = last_move.get('column', 0)
                hits = last_move.get('hits', 0)
                blows = last_move.get('blows', 0)
                
                # カラム番号が有効範囲内か確認
                if column < 0 or column >= len(board[0]):
                    logger.warning(f"無効なカラム番号: {column}, ボード幅: {len(board[0])}")
                    return
                
                # 現在の列の状態
                column_state = [board[i][column]['color'] for i in range(sequence_length)]
                
                # シーケンスを絞り込む
                prev_count = len(self.possible_sequences)
                self.possible_sequences = self.rule_agent._filter_sequences(self.possible_sequences, column_state, hits, blows)
                # RLエージェントとも共有
                self.rl_agent.possible_sequences = self.possible_sequences.copy()
                
                logger.info(f"ハイブリッド: シーケンス絞り込み: {prev_count} -> {len(self.possible_sequences)}個")
        except Exception as e:
            logger.error(f"シーケンス更新中にエラー: {str(e)}")
            # エラーが発生した場合、安全のためシーケンスをリセットせず現状維持
    
    def _decide_action_method(self, game_state: Dict[str, Any]) -> str:
        """状況に応じて採用する戦略を決定"""
        history = game_state['history']
        current_turn = len(history)
        max_turns = game_state.get('maxTurns', 50)
        game_progress = current_turn / max_turns if max_turns > 0 else 0
        
        # 初手はルールベースから開始
        if current_turn == 0:
            return 'rule'
        
        # 可能性のあるシーケンスが少なくなったらルールベースを優先
        if 1 <= len(self.possible_sequences) <= 3:
            return 'rule'
            
        # 終盤（70%以上）は、確実性を高めるためにルールベースを優先
        if game_progress > 0.7:
            return 'rule'
            
        # 中盤はハイブリッド戦略
        if 0.3 <= game_progress <= 0.7:
            return 'weighted'
        
        # それ以外（序盤）は強化学習の探索性を活かす
        # ただし、可能性のあるシーケンスが多すぎる場合はルールベースも考慮
        if len(self.possible_sequences) > 100:
            return 'weighted'
        else:
            # 学習モードではRLの探索をより活かす
            if self.learning_mode and random.random() < 0.3:
                return 'rl'
            return 'weighted'  # より協調的にする
    
    def _adjust_weights(self, game_state: Dict[str, Any]) -> None:
        """ゲームの進行状況に応じて重みを調整"""
        history = game_state['history']
        current_turn = len(history)
        max_turns = game_state.get('maxTurns', 50)
        
        # ゲームの進行度（0〜1）
        game_progress = current_turn / max_turns if max_turns > 0 else 0
        
        # ゲーム終盤になるほどルールベースの重みを大きくする
        # 序盤は探索性を重視、終盤は正確さを重視
        adjusted_rule_weight = self.initial_rule_weight
        
        # 非線形調整：序盤は強化学習寄り、終盤はルールベース寄り
        if game_progress <= 0.3:  # 序盤
            adjusted_rule_weight = self.initial_rule_weight * 0.8
        elif game_progress >= 0.7:  # 終盤
            adjusted_rule_weight = min(0.9, self.initial_rule_weight * 1.3)
        
        # 可能性のあるシーケンス数に応じた調整
        sequence_count = len(self.possible_sequences)
        if sequence_count <= 5:  # 候補が少ない場合はルールベースを重視
            adjusted_rule_weight = min(0.9, adjusted_rule_weight * 1.2)
        elif sequence_count >= 100:  # 候補が多い場合は探索性を重視
            adjusted_rule_weight = max(0.3, adjusted_rule_weight * 0.8)
        
        # 学習モードではRLの重みをやや増やす
        if self.learning_mode:
            adjusted_rule_weight = max(0.3, adjusted_rule_weight * 0.9)
        
        # 重みの更新
        self.rule_weight = min(0.9, max(0.1, adjusted_rule_weight))
        self.rl_weight = 1.0 - self.rule_weight
        
        logger.debug(f"重み調整: 進行度={game_progress:.2f}, " +
                   f"シーケンス候補数={sequence_count}, " +
                   f"ルール重み={self.rule_weight:.2f}")
    
    def _combine_actions(self, rule_action: Dict[str, Any], rl_action: Dict[str, Any], 
                        game_state: Dict[str, Any]) -> Dict[str, Any]:
        """両方のエージェントの意見を統合"""
        # 各色と列の組み合わせに対するスコアを計算
        action_scores = {}
        
        # すべての行動の組み合わせのスコアを初期化
        for color in self.colors:
            for column in range(5):
                action_key = f"{color}:{column}"
                action_scores[action_key] = 0.0
        
        # ルールベースの意見を反映
        rule_key = f"{rule_action['color']}:{rule_action['column']}"
        action_scores[rule_key] += self.rule_weight
        
        # 強化学習の意見を反映
        rl_key = f"{rl_action['color']}:{rl_action['column']}"
        action_scores[rl_key] += self.rl_weight
        
        # 最高スコアの行動を選択（同点の場合はランダム）
        max_score = max(action_scores.values())
        best_actions = [
            action.split(':')
            for action, score in action_scores.items()
            if abs(score - max_score) < 1e-6  # 浮動小数点の比較を考慮
        ]
        
        # 最良行動をランダムに選択
        color, column_str = random.choice(best_actions)
        column = int(column_str)
        
        return {
            'color': color,
            'column': column
        }
    
    def learn(self, prev_state: Dict[str, Any], action: Dict[str, Any], 
              reward: float, new_state: Dict[str, Any]) -> None:
        """学習（強化学習エージェントのみ学習する）"""
        if not self.learning_mode:
            return
        
        # 強化学習エージェントに学習させる
        self.rl_agent.learn(prev_state, action, reward, new_state)
    
    def calculate_reward(self, game_state: Dict[str, Any]) -> float:
        """報酬を計算（強化学習エージェントの報酬計算を利用）"""
        return self.rl_agent.calculate_reward(game_state)
    
    def save_q_table(self) -> None:
        """Q値テーブルを保存（強化学習エージェントの機能を利用）"""
        self.rl_agent.save_q_table()
    
    def load_q_table(self) -> None:
        """Q値テーブルを読み込み（強化学習エージェントの機能を利用）"""
        self.rl_agent.load_q_table() 