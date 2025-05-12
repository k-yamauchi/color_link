import random
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

class ColorLinkGame:
    def __init__(self):
        self.colors = ['red', 'blue', 'yellow', 'green', 'purple']
        self.board = []
        self.target_sequence = []
        self.history = []
        self.game_over = False
        self.winner = False
        self.max_turns = 50
        self.sequence_length = 3
        
    def new_game(self, sequence_length: int = 3) -> None:
        """新しいゲームを開始する"""
        self.sequence_length = sequence_length
        
        # ボードの初期化（5x5グリッド）
        self.board = []
        for _ in range(5):
            row = []
            for _ in range(5):
                row.append({'color': random.choice(self.colors)})
            self.board.append(row)
        
        # 目標シーケンスをランダム生成
        self.target_sequence = [random.choice(self.colors) for _ in range(sequence_length)]
        
        self.history = []
        self.game_over = False
        self.winner = False
        print(f"新しいゲームを開始しました。目標シーケンス: {self.target_sequence}")
    
    def make_move(self, color: str, column: int) -> Dict[str, Any]:
        """指定された色を指定された列に挿入する"""
        if self.game_over:
            return {'valid': False, 'message': 'ゲームは終了しています'}
        
        if color not in self.colors or column < 0 or column >= 5:
            return {'valid': False, 'message': '無効な移動です'}
        
        # 列に色を挿入してシフト
        for i in range(4, 0, -1):
            self.board[i][column]['color'] = self.board[i-1][column]['color']
        self.board[0][column]['color'] = color
        
        # 結果を判定
        hits, blows = self.check_sequence(column)
        
        # 履歴に記録
        self.history.append({
            'color': color,
            'column': column,
            'hits': hits,
            'blows': blows
        })
        
        # 現在のターン数
        current_turn = len(self.history)
        
        # ゲーム終了チェック
        if hits == self.sequence_length:
            self.game_over = True
            self.winner = True
            print(f"勝利！シーケンスが一致しました。ターン数: {current_turn}")
        elif current_turn >= self.max_turns:
            self.game_over = True
            self.winner = False
            print(f"敗北。最大ターン数 {self.max_turns} に達しました。正解は {self.target_sequence} でした。")
        
        # 現在の状態をログ出力
        column_colors = [self.board[i][column]['color'] for i in range(self.sequence_length)]
        print(f"移動: 色={color}, 列={column}, 列の上部={column_colors}")
        print(f"結果: {hits} HIT / {blows} BLOW, ターン={current_turn}/{self.max_turns}, ゲーム終了={self.game_over}")
        
        return {
            'valid': True,
            'hits': hits,
            'blows': blows,
            'game_over': self.game_over,
            'winner': self.winner,
            'current_turn': current_turn,
            'max_turns': self.max_turns
        }
    
    def check_sequence(self, column: int) -> Tuple[int, int]:
        """指定された列の上部と目標シーケンスを比較してHITとBLOWを計算する"""
        hits = 0
        blows = 0
        
        # コピーを作成して一致チェック
        column_colors = [self.board[i][column]['color'] for i in range(self.sequence_length)]
        target_copy = self.target_sequence.copy()
        column_copy = column_colors.copy()
        
        # HITチェック（色と位置が一致）
        for i in range(self.sequence_length):
            if i < len(column_colors) and i < len(self.target_sequence) and column_colors[i] == self.target_sequence[i]:
                hits += 1
                target_copy[i] = None
                column_copy[i] = None
        
        # BLOWチェック（色のみ一致）
        for i in range(self.sequence_length):
            if i < len(column_copy) and column_copy[i] is not None:
                for j in range(self.sequence_length):
                    if j < len(target_copy) and target_copy[j] is not None and column_copy[i] == target_copy[j]:
                        blows += 1
                        target_copy[j] = None
                        break
        
        return hits, blows
    
    def get_state(self, hide_sequence: bool = True) -> Dict[str, Any]:
        """ゲームの現在の状態を取得する"""
        return {
            'board': self.board,
            'history': self.history,
            'gameOver': self.game_over,
            'winner': self.winner,
            'targetSequence': None if hide_sequence else self.target_sequence,
            'sequenceLength': self.sequence_length,
            'maxTurns': self.max_turns,
            'currentTurn': len(self.history)
        } 