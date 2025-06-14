import json
import random
import os
import sys
from datetime import datetime # 计算选手年龄
import webbrowser#打开网页
import pygame
from pygame.locals import *
import speech_recognition as sr#语音识别目的
import threading#多线程（利于语音输入）
import time
from typing import Dict, List, Set, Tuple, Optional

SCREEN_SIZE = (1280, 720)
COLORS = {
    'bg': (30, 30, 45),
    'text': (230, 230, 230),
    'input': (80, 80, 100),
    'correct': (80, 220, 120),
    'partial': (255, 200, 100),#黄
    'wrong': (255, 120, 120),
    'white': (255, 255, 255)
}

CURRENT_YEAR = datetime.now().year
FLAG_PATH = "E:\\For_py\\Code_PY\\program\\flags"
FLAG_SIZE = (28, 21)
MAX_ATTEMPTS = 5

VOICE_RECOGNITION_CONFIG = {
    'energy_threshold': 200,
    'pause_threshold': 0.3,
    'phrase_threshold': 0.1,
    'non_speaking_duration': 0.2,
    'timeout': 5,
    'phrase_time_limit': 4
}

REGION_MAP = {
    "Russia": "CIS", "Ukraine": "CIS", "Kazakhstan": "CIS", "Lithuania": "CIS",
    "Denmark": "Europe", "France": "Europe", "Sweden": "Europe", "United Kingdom": "Europe",
    "Estonia": "Europe", "Finland": "Europe", "Poland": "Europe", "Bosnia and Herzegovina": "Europe",
    "Turkey": "Europe", "Israel": "Europe", "Latvia": "Europe", "Germany": "Europe",
    "Slovakia": "Europe", "Czech Republic": "Europe", "Hungary": "Europe", "Norway": "Europe",
    "Serbia": "Europe", "Bulgaria": "Europe", "Spain": "Europe", "Romania": "Europe",
    "United States": "North America", "Canada": "North America",
    "Brazil": "South America", "Argentina": "South America",
    "Australia": "Asia-Pacific", "China": "Asia-Pacific", "Indonesia": "Asia-Pacific",
    "Malaysia": "Asia-Pacific", "Mongolia": "Asia-Pacific",
}#国家与分区

# 一些音节识别
SOUND_VARIANTS = {
    'k': ['c'], 'c': ['k'], 'ph': ['f'], 'f': ['ph'],
    'y': ['i'], 'i': ['y'], 'x': ['ks'], 'ks': ['x'],
    'z': ['s'], 's': ['z'], 'w': ['v'], 'v': ['w'],
    'mple': ['mpo', 'mpel', 'n', 'mpol', 'mpul'],
    'ple': ['po', 'pel', 'pol', 'pul'],
    'mp': ['n', 'np', 'mb']
}

# 经验性错误
COMMON_MISRECOGNITIONS = {
    'simple': ['s1n', 'seen', 'sin', 'simpo', 'simpel', 'symbol', 'sim'],
    'niko': ['nico', 'nicko'],
    'device': ['devise', 'devices'],
    'rain': ['reign', 'rane', 'rein', 'brain'],
    'zeus': ['zoos', 'zooms', 'seems', 'seuss']
}

# 针对Leet Speak风格ID
NUM_TO_LETTER = {
    '0': 'o', 
    '1': 'i', 
    '2': 'z', 
    '3': 'e',
    '4': 'a',
    '5': 's',
    '6': 'g', 
    '7': 't',
    '8': 'b',
    '9': 'g'
}

def load_players(mode: str = "expert") -> List[Dict]:
    """加载选手数据"""
    filename = "players_ez.json" if mode == "noob" else "players.json"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [{"name": k, **v} for k, v in data.items()]

def select_target(players: List[Dict]) -> Dict:
    """随机选择目标选手"""
    return random.choice(players)

def get_player_by_name(players: List[Dict], name: str) -> Optional[Dict]:
    """根据名字查找选手"""
    clean = name.strip().lower().replace(" ", "")
    return next((p for p in players if p["name"].lower().replace(" ", "") == clean), None)

def compare_players(guess: Dict, target: Dict) -> Dict:
    """比较猜测的选手和目标选手"""
    region_g = REGION_MAP.get(guess["country"], "Unknown")
    region_t = REGION_MAP.get(target["country"], "Unknown")
    country_status = "exact" if guess["country"] == target["country"] else "region" if region_g == region_t else "none"
    age_g, age_t = CURRENT_YEAR - guess["birth_year"], CURRENT_YEAR - target["birth_year"]
    maj_g, maj_t = guess["majapp"], target["majapp"]
    return {
        "country": {"value": guess["country"], "status": country_status},
        "age": {"value": age_g, "status": "high" if age_g > age_t else "low" if age_g < age_t else "exact"},
        "majapp": {"value": maj_g, "status": "high" if maj_g > maj_t else "low" if maj_g < maj_t else "exact"},
        "name": (guess["name"], guess["name"] == target["name"]),
        "team": (guess["team"], guess["team"] == target["team"]),
        "role": (guess["role"], guess["role"] == target["role"])
    }


class CSGOGuess:
    """CS:GO选手竞猜游戏"""
    
    def __init__(self, players: List[Dict]):
        """初始化游戏界面"""
        pygame.init()
        self.mode = "expert"
        self.screen = pygame.display.set_mode(SCREEN_SIZE)
        pygame.display.set_caption("CS:GO选手竞猜")
        self.font = pygame.font.SysFont("Microsoft YaHei UI", 20)
        self.title_font = pygame.font.SysFont("Microsoft YaHei UI", 28)
        self._run_start_screen()
        self.players = load_players(self.mode)
        #初始化
        self._init_game_state()

        self._init_voice_recognition()

        self._load_resources()
        
    def _init_game_state(self):
        """初始化游戏状态"""
        #逻辑初始化
        self.target = select_target(self.players)
        self.guess_history = []
        self.attempts = 0

        # 输入初始化
        self.input_text = ''
        self.input_active = False
        self.suggestions = []
        self.selected_sugg = -1

        # 光标初始化
        self.cursor_visible = True
        self.cursor_timer = 0

        # 语音初始化
        self.listening = False
        self.voice_tip = ""
        self.voice_tip_timer = 0
        self.voice_tip_duration = 2000
        
        # 初始化选手ID变体
        self._init_player_variants()
        
    def _init_voice_recognition(self):
        """初始化语音识别"""
        try:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300  # 可以尝试200~400
            self.recognizer.dynamic_energy_threshold = True  # 自动适应环境
            self.recognizer.pause_threshold = 0.5   # 适当延长停顿
            self.recognizer.phrase_threshold = 0.1
            self.recognizer.non_speaking_duration = 0.2
        except Exception:
            pass
            
    def _load_resources(self):
        """加载游戏资源"""
        self.heart_full = pygame.image.load(os.path.join(os.path.dirname(__file__), "image", "heart_full.png"))
        self.heart_empty = pygame.image.load(os.path.join(os.path.dirname(__file__), "image", "heart_empty.png"))
        self.heart_full = pygame.transform.scale(self.heart_full, (32, 32))
        self.heart_empty = pygame.transform.scale(self.heart_empty, (32, 32))
        
        self.input_rect = pygame.Rect(50, 650, 400, 40)
        self.mic_rect = pygame.Rect(self.input_rect.right + 10, self.input_rect.top, 40, 40)
        
    def _init_player_variants(self):
        """应对选手LEET SPEAK风格id初始化"""
        self.player_ids = []
        self.player_id_variants = {}
        
        for player in self.players:
            player_id = player["name"].lower()
            self.player_ids.append(player_id)
            variants = self._generate_player_variants(player_id)
            self.player_id_variants[player_id] = variants

    def _generate_player_variants(self, player_id: str) -> Set[str]:
        """生成选手ID的所有可能变体"""
        variants = {player_id}
        variants.update(self._generate_number_variants(player_id))
        variants.update(self._generate_sound_variants(variants))
        variants.update(self._add_common_misrecognitions(player_id))
        return variants
        
    def _generate_number_variants(self, text: str) -> Set[str]:
        """生成数字-字母替换变体"""
        variants = set()
        chars = list(text)
        
        for i, char in enumerate(chars):
            if char.isdigit() and char in NUM_TO_LETTER:
                chars[i] = NUM_TO_LETTER[char]
                variants.add(''.join(chars))
                chars[i] = char
            elif char in NUM_TO_LETTER.values():
                for num, letter in NUM_TO_LETTER.items():
                    if char == letter:
                        chars[i] = num
                        variants.add(''.join(chars))
                        chars[i] = char
                        
        return variants
        
    def _generate_sound_variants(self, base_variants: Set[str]) -> Set[str]:
        """生成发音变体"""
        new_variants = set()
        
        for variant in base_variants:
            for i in range(len(variant)):
                # 检查多字符组合
                for length in range(2, 5):
                    if i + length <= len(variant):
                        chars = variant[i:i+length]
                        for sound, alternatives in SOUND_VARIANTS.items():
                            if chars == sound:
                                for alt in alternatives:
                                    new_variant = variant[:i] + alt + variant[i+length:]
                                    new_variants.add(new_variant)
                                    
                # 检查单个字符替换
                char = variant[i]
                for sound, alternatives in SOUND_VARIANTS.items():
                    if char == sound:
                        for alt in alternatives:
                            new_variant = variant[:i] + alt + variant[i+1:]
                            new_variants.add(new_variant)
                            
        return new_variants
        
    def _add_common_misrecognitions(self, player_id: str) -> Set[str]:
        """添加经验性错误"""
        variants = set()
        for base_id, misrecognitions in COMMON_MISRECOGNITIONS.items():
            if player_id == base_id:
                variants.update(misrecognitions)
        return variants

    #进一步通过字符串相似度确定选手ID
    def _calculate_similarity(self, str1, str2):
        """计算两个字符串的相似度"""
        lcs_length = self._longest_common_subsequence(str1, str2)
        max_length = max(len(str1), len(str2))
        
        base_similarity = lcs_length / max_length if max_length > 0 else 0
        
        length_diff = abs(len(str1) - len(str2))
        if length_diff <= 2:
            base_similarity *= 1.2
        
        if str1 and str2 and str1[0] == str2[0]:
            base_similarity *= 1.1
            
        return min(base_similarity, 1.0)

    def _longest_common_subsequence(self, str1, str2):
        """计算两个字符串的最长公共子序列长度"""
        m, n = len(str1), len(str2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if str1[i-1] == str2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
                    
        return dp[m][n]
    #连接google服务
    def _try_multiple_recognition(self, audio):
        """尝试使用Google语音识别服务"""
        results = []
        try:
            text = self.recognizer.recognize_google(audio, language='en-US')
            results.append(text.lower())
        except sr.UnknownValueError:
            pass
        except sr.RequestError:
            pass
        except Exception:
            pass
        return results

    def _find_closest_match(self, text_list):
        """从多个识别结果中找到最佳匹配"""
        all_matches = []
        
        for text in text_list:
            words = text.lower().split()
            for word in words:
                for player_id in self.player_ids:
                    if word in self.player_id_variants[player_id]:
                        all_matches.append((player_id, 1.0))
                        continue
                        
                    best_variant_score = 0
                    for variant in self.player_id_variants[player_id]:
                        similarity = self._calculate_similarity(word, variant)
                        best_variant_score = max(best_variant_score, similarity)
                    
                    if best_variant_score > 0.3:
                        all_matches.append((player_id, best_variant_score))
        
        unique_matches = {}
        for player_id, score in all_matches:
            if player_id not in unique_matches or score > unique_matches[player_id]:
                unique_matches[player_id] = score
        
        sorted_matches = sorted(unique_matches.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_matches:
            return sorted_matches[0]
        return None, 0
    
    #加入语音识别功能
    def _recognize_voice(self):
        if not hasattr(self, 'recognizer'):
            self.voice_tip = "未找到麦克风设备"
            self.voice_tip_timer = pygame.time.get_ticks()
            return

        self.listening = True
        
        try:
            self.recognizer.energy_threshold = 200 
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.pause_threshold = 0.3 
            self.recognizer.phrase_threshold = 0.1
            self.recognizer.non_speaking_duration = 0.2 
            
            for i in range(2, 0, -1):
                self.voice_tip = f"准备录音... {i}"
                time.sleep(1)
            
            self.voice_tip = "开始录音..."
            
            with sr.Microphone() as source:
                try:
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=2)
                    self.voice_tip = "正在识别..."
                except sr.WaitTimeoutError:
                    raise
                
                recognition_results = self._try_multiple_recognition(audio)
                
                if recognition_results:
                    matched_id, confidence = self._find_closest_match(recognition_results)
                    
                    if matched_id:
                        self.input_text = matched_id
                        self._update_suggestions()
                        self.voice_tip = f"匹配结果: {matched_id} (匹配度: {confidence:.1%})"
                    else:
                        self.voice_tip = "未找到任何匹配"
                else:
                    self.voice_tip = "识别失败，请重试"
                
                self.voice_tip_timer = pygame.time.get_ticks()
        #增加交互，让用户知道问题所在
        except sr.WaitTimeoutError:
            self.voice_tip = "请说话..."
            self.voice_tip_timer = pygame.time.get_ticks()
        except sr.UnknownValueError:
            self.voice_tip = "没听清，请对准麦克风"
            self.voice_tip_timer = pygame.time.get_ticks()
        except sr.RequestError:
            self.voice_tip = "网络连接错误，请检查网络"
            self.voice_tip_timer = pygame.time.get_ticks()
        except Exception:
            self.voice_tip = "识别失败，请重试"
            self.voice_tip_timer = pygame.time.get_ticks()
        finally:
            self.listening = False

    def _draw_mic_button(self):
        """绘制麦克风按钮"""
        color = (200, 50, 50) if self.listening else (100, 100, 100)
        pygame.draw.circle(self.screen, color, self.mic_rect.center, 18)
        
        icon_color = COLORS['white']
        center_x, center_y = self.mic_rect.center
        
        mic_rect = pygame.Rect(center_x - 5, center_y - 8, 10, 16)
        pygame.draw.rect(self.screen, icon_color, mic_rect, border_radius=5)
        
        bottom_rect = pygame.Rect(center_x - 8, center_y + 8, 16, 3)
        pygame.draw.rect(self.screen, icon_color, bottom_rect)
        
        pygame.draw.line(self.screen, icon_color, 
                        (center_x, center_y + 8), 
                        (center_x, center_y + 10), 2)

    def _draw_input(self):
        """绘制输入框"""
        pygame.draw.rect(self.screen, COLORS['correct'] if self.input_active else COLORS['input'], self.input_rect, 2)
        text = self.font.render(self.input_text, True, COLORS['text'])
        self.screen.blit(text, (self.input_rect.x + 5, self.input_rect.y + 5))
        if self.input_active and self.cursor_visible:
            pygame.draw.line(self.screen, COLORS['text'],
                             (self.input_rect.x + 5 + text.get_width(), self.input_rect.y + 5),
                             (self.input_rect.x + 5 + text.get_width(), self.input_rect.y + 35), 2)

    def _update_suggestions(self):
        """更新建议列表"""
        txt = self.input_text.strip().lower()
        self.suggestions = [p for p in self.players if txt in p["name"].lower()][:5]
        self.selected_sugg = -1

    def _draw_suggestions(self):
        """绘制建议列表"""
        for i, p in enumerate(self.suggestions):
            color = COLORS['correct'] if i == self.selected_sugg else COLORS['text']
            self.screen.blit(self.font.render(p["name"], True, color), (50, 620 - i * 30))

    def _handle_suggestion_click(self, pos):
        """处理建议列表点击"""
        base_y = 620
        for i, _ in enumerate(self.suggestions):
            rect = pygame.Rect(50, base_y - i * 30, 400, 30)
            if rect.collidepoint(pos):
                self.selected_sugg = i
                return True
        return False

    def _draw_header(self):
        """绘制页面头部"""
        self.screen.blit(self.title_font.render("CS:GO选手竞猜", True, COLORS['text']), (50, 20))
        for i in range(MAX_ATTEMPTS):
            img = self.heart_full if i < (MAX_ATTEMPTS - self.attempts) else self.heart_empty
            self.screen.blit(img, (1100 + i * 36, 22))

    def _get_status_color(self, status):
        """获取状态对应的颜色"""
        return {
            'exact': COLORS['correct'],
            'region': COLORS['partial'],
            'high': COLORS['wrong'],
            'low': COLORS['wrong'],
            'none': COLORS['wrong']
        }.get(status, COLORS['text'])

    def _draw_history(self):
        """绘制猜测历史"""
        CELL_WIDTHS = [160, 200, 160, 120, 120, 200]
        HEADERS = ["Name", "Team", "Nation", "Majors", "Age", "Role"]
        HEAD_X = (1280 - sum(CELL_WIDTHS)) // 2
        HEAD_Y = 180
        CELL_HEIGHT = 80

        x = HEAD_X
        for i in range(6):
            rect_surface = pygame.Surface((CELL_WIDTHS[i] - 10, CELL_HEIGHT - 10), pygame.SRCALPHA)
            rect_surface.fill((100, 100, 100, 180))
            self.screen.blit(rect_surface, (x + 5, HEAD_Y - CELL_HEIGHT + 5))
            text = self.font.render(HEADERS[i], True, COLORS['white'])
            text_rect = text.get_rect(center=(x + CELL_WIDTHS[i] // 2, HEAD_Y - CELL_HEIGHT // 2))
            self.screen.blit(text, text_rect)
            x += CELL_WIDTHS[i]

        def with_arrow(value, status):
            if status == "high":
                return f"{value} ↑"
            elif status == "low":
                return f"{value} ↓"
            return str(value)

        for row in range(5):
            y = HEAD_Y + row * CELL_HEIGHT
            x = HEAD_X
            if row < len(self.guess_history):
                comp = self.guess_history[row]
                statuses = [
                    'exact' if comp['name'][1] else 'none',
                    'exact' if comp['team'][1] else 'none',
                    comp['country']['status'],
                    comp['majapp']['status'],
                    comp['age']['status'],
                    'exact' if comp['role'][1] else 'none'
                ]
                values = [
                    comp['name'][0], comp['team'][0], comp['country']['value'],
                    with_arrow(comp['majapp']['value'], comp['majapp']['status']),
                    with_arrow(comp['age']['value'], comp['age']['status']), comp['role'][0]
                ]
            else:
                statuses = ['none'] * 6
                values = [''] * 6

            for i in range(6):
                cell_w = CELL_WIDTHS[i]
                color = self._get_status_color(statuses[i])
                rect_surface = pygame.Surface((cell_w - 10, CELL_HEIGHT - 10), pygame.SRCALPHA)
                rect_surface.fill((*color[:3], 200))
                self.screen.blit(rect_surface, (x + 5, y + 5))

                if i == 2 and values[i]:  # 显示国旗
                    try:
                        flag_path = os.path.join(FLAG_PATH, f"{values[i]}.png")
                        flag = pygame.image.load(flag_path)
                        flag = pygame.transform.scale(flag, FLAG_SIZE)
                        flag_rect = flag.get_rect(center=(x + cell_w // 2, y + CELL_HEIGHT // 2))
                        self.screen.blit(flag, flag_rect)
                    except:
                        pass
                elif values[i]:
                    text = self.font.render(values[i], True, COLORS['white'])
                    text_rect = text.get_rect(center=(x + cell_w // 2, y + CELL_HEIGHT // 2))
                    self.screen.blit(text, text_rect)

                x += cell_w

    def _draw_voice_tip(self):
        """绘制语音提示"""
        if not self.voice_tip:
            return
            
        if not self.listening and pygame.time.get_ticks() - self.voice_tip_timer > self.voice_tip_duration:
            self.voice_tip = ""
            return
            
        tip_surface = pygame.Surface((400, 40), pygame.SRCALPHA)
        pygame.draw.rect(tip_surface, (0, 0, 0, 128), tip_surface.get_rect(), border_radius=10)
        
        tip_text = self.font.render(self.voice_tip, True, COLORS['white'])
        text_rect = tip_text.get_rect(center=(200, 20))
        tip_surface.blit(tip_text, text_rect)
        
        self.screen.blit(tip_surface, (self.mic_rect.centerx - 200, self.mic_rect.top - 50))

    def _run_start_screen(self):
        """运行启动屏幕"""
        bg_path = os.path.join(os.path.dirname(__file__), "image", "begin.png")
        bg_image = pygame.image.load(bg_path)
        bg_image = pygame.transform.scale(bg_image, (1280, 720))

        button_width, button_height = 200, 60
        button_spacing = 40
        total_width = (button_width * 2) + button_spacing
        start_x = (1280 - total_width) // 2
        button_y = 580

        noob_rect = pygame.Rect(start_x, button_y, button_width, button_height)
        expert_rect = pygame.Rect(start_x + button_width + button_spacing, button_y, button_width, button_height)

        button_color = (70, 130, 180)
        button_hover = (100, 160, 210)

        running = True
        while running:
            self.screen.blit(bg_image, (0, 0))

            mouse_pos = pygame.mouse.get_pos()
            noob_hover = noob_rect.collidepoint(mouse_pos)
            expert_hover = expert_rect.collidepoint(mouse_pos)

            pygame.draw.rect(self.screen, button_hover if noob_hover else button_color, noob_rect, border_radius=10)
            noob_text = self.title_font.render("Noob", True, (255, 255, 255))
            noob_text_rect = noob_text.get_rect(center=noob_rect.center)
            self.screen.blit(noob_text, noob_text_rect)

            pygame.draw.rect(self.screen, button_hover if expert_hover else button_color, expert_rect, border_radius=10)
            expert_text = self.title_font.render("Expert", True, (255, 255, 255))
            expert_text_rect = expert_text.get_rect(center=expert_rect.center)
            self.screen.blit(expert_text, expert_text_rect)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if noob_rect.collidepoint(mouse_pos):
                        self.mode = "noob"
                        return
                    elif expert_rect.collidepoint(mouse_pos):
                        self.mode = "expert"
                        return

            pygame.display.flip()
            pygame.time.Clock().tick(60)

    def _process_guess(self):
        """处理猜测"""
        name = self.suggestions[self.selected_sugg]["name"] if self.selected_sugg >= 0 else self.input_text.strip()
        guess = get_player_by_name(self.players, name)
        if not guess: return
        self.attempts += 1
        self.guess_history.append(compare_players(guess, self.target))
        self.input_text, self.suggestions, self.selected_sugg = '', [], -1
        if guess["name"] == self.target["name"]:
            self._show_result(True)
        elif self.attempts >= MAX_ATTEMPTS:
            self._show_result(False)

    def _show_result(self, win):
        """显示游戏结果"""
        msg = "恭喜获胜！" if win else f"游戏结束！正确答案：{self.target['name']}"
        self.screen.fill(COLORS['bg'])
        surf = self.title_font.render(msg, True, COLORS['correct'] if win else COLORS['wrong'])
        self.screen.blit(surf, (400, 200))

        box_width, box_height = 600, 300
        box_x, box_y = (1280 - box_width) // 2, 300
        pygame.draw.rect(self.screen, COLORS['input'], (box_x, box_y, box_width, box_height), border_radius=15)

        lines = [
            f"Name: {self.target['name']}",
            f"Team: {self.target['team']}",
            f"Country: {self.target['country']}",
            f"Majors: {self.target['majapp']}",
            f"Age: {datetime.now().year - self.target['birth_year']}",
            f"Role: {self.target['role']}"
        ]

        for i, line in enumerate(lines):
            text = self.font.render(line, True, COLORS['text'])
            self.screen.blit(text, (box_x + 30, box_y + 30 + i * 35))

        button_rect = pygame.Rect(box_x + box_width - 200, box_y + box_height - 60, 160, 40)
        pygame.draw.rect(self.screen, (70, 130, 180), button_rect, border_radius=10)
        button_text = self.font.render("查看 HLTV 页面", True, (255, 255, 255))
        self.screen.blit(button_text, button_text.get_rect(center=button_rect.center))
        #网页跳转
        pygame.display.flip()

        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if button_rect.collidepoint(event.pos):
                        if "link" in self.target:
                            webbrowser.open(self.target["link"])
                    else:
                        waiting = False

        pygame.quit()
        sys.exit()

    def run(self):
        """运行游戏主循环"""
        clock = pygame.time.Clock()
        while True:
            self.screen.fill(COLORS['bg'])
            for event in pygame.event.get():
                if event.type == QUIT:
                    pygame.quit(); sys.exit()
                elif event.type == MOUSEBUTTONDOWN:
                    if self.mic_rect.collidepoint(event.pos):
                        threading.Thread(target=self._recognize_voice).start()
                    elif self._handle_suggestion_click(event.pos):
                        self.input_active = True
                        self._process_guess()
                    elif self.input_rect.collidepoint(event.pos):
                        self.input_active = True
                    else:
                        self.input_active = False
                elif event.type == KEYDOWN and self.input_active:
                    if event.key == K_RETURN:
                        self._process_guess()
                    elif event.key == K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                        self._update_suggestions()
                    elif event.key == K_UP:
                        self.selected_sugg = max(-1, self.selected_sugg - 1)
                    elif event.key == K_DOWN:
                        self.selected_sugg = min(len(self.suggestions) - 1, self.selected_sugg + 1)
                    else:
                        self.input_text += event.unicode
                        self._update_suggestions()

            self.cursor_timer += clock.get_time()
            if self.cursor_timer > 500:
                self.cursor_visible = not self.cursor_visible
                self.cursor_timer = 0

            self._draw_header()
            self._draw_input()
            self._draw_history()
            self._draw_suggestions()
            self._draw_mic_button()
            self._draw_voice_tip()
            pygame.display.flip()
            clock.tick(60)

if __name__ == "__main__":
    CSGOGuess([]).run()
