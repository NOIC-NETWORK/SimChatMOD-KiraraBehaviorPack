#!/usr/bin/env python3
# jrvs_tui.py
# Kirara JRVS (Joint Ratiocination Visual System) Terminal UI
# Author: Barry Molynton(Founder, Chairman and CTO of TeleVideo Inc.)
# Version: 1.0 Alpha
import os
import sys
import time
import threading
import subprocess

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(SERVICE_DIR)
sys.path.insert(0, SERVICE_DIR)

try:
    from jrvs import JRVS_Kernel, MODELS, check_environ
    print("[TUI] JRVS模块导入成功")
except ImportError as e:
    print(f"[TUI] 导入JRVS模块失败: {e}")
    sys.exit(1)

class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GREY = '\033[90m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class JRVS_TUI:
    def __init__(self):
        self.kernel = None
        self.running = True
        self.session_id = "tui_session"
        self.deep_think_mode = False
        self.show_thinking = False
        
        self.commands = {
            "/help": {"desc": "显示帮助信息", "func": self.cmd_help},
            "/exit": {"desc": "退出TUI", "func": self.cmd_exit},
            "/model": {"desc": "切换模型 (/model list 查看列表)", "func": self.cmd_model},
            "/memory": {"desc": "查看记忆库", "func": self.cmd_memory},
            "/deep": {"desc": "切换深度思考模式", "func": self.cmd_deep},
            "/clear": {"desc": "清空屏幕", "func": self.cmd_clear},
            "/status": {"desc": "显示系统状态", "func": self.cmd_status},
            "/save": {"desc": "手动保存当前对话到记忆", "func": self.cmd_save},
        }

    def _print_banner(self):
        banner = f"""
{Colors.PURPLE}{Colors.BOLD}
                                                                             x       x
        K    K   IIIII   RRRRR         A       RRRRR         A             xxx     xxx
       K  K       I     R    R       A A      R    R       A A          xxxxxxx    x     x
      KK         I     RRRRR       AAAAA     RRRRR       AAAAA      xxxxxxxxxxxxx      xxx
     K  K       I     R    R     A     A    R    R     A     A        xxxxxxx       xxxxxxx
    K    K   IIIII   R     R   A       A   R     R   A       A         xxx           xxx
                                                                       x             x
{Colors.RESET}
{Colors.CYAN}{Colors.BOLD}JOINT RATIOCINATION VISUAL SYSTEM (JRVS) - Terminal UI{Colors.RESET}
{Colors.GREY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}
"""
        print(banner)

    def _print_prompt(self):
        model_name = self.kernel.get_current_model()["name"] if self.kernel else "Unknown"
        deep_indicator = f"{Colors.YELLOW}[Deep]{Colors.RESET} " if self.deep_think_mode else ""
        
        prompt = f"\n{deep_indicator}{Colors.GREEN}{model_name}{Colors.RESET} > "
        return prompt

    def _print_separator(self):
        print(f"\n{Colors.GREY}────────────────────────────────────────────────────────────────────────────{Colors.RESET}")

    def _print_message(self, role, content):
        if role == "user":
            print(f"\n{Colors.BLUE}{Colors.BOLD}[User]{Colors.RESET}")
        elif role == "kirara":
            print(f"\n{Colors.PURPLE}{Colors.BOLD}[Kirara]{Colors.RESET}")
        elif role == "system":
            print(f"\n{Colors.YELLOW}[System]{Colors.RESET}")
        elif role == "error":
            print(f"\n{Colors.RED}[Error]{Colors.RESET}")
        elif role == "info":
            print(f"\n{Colors.CYAN}[Info]{Colors.RESET}")
        
        lines = content.split('\n')
        for line in lines:
            print(f"  {line}")

    def init_kernel(self):
        print(f"{Colors.YELLOW}[TUI] 正在初始化JRVS Kernel...{Colors.RESET}")
        
        try:
            check_environ()
            
            api_client_instance = None
            try:
                from api_client import init_models
                api_client_instance = init_models()
                print(f"{Colors.GREEN}[TUI] API客户端初始化成功{Colors.RESET}")
            except Exception:
                print(f"{Colors.GREY}[TUI] API客户端初始化失败，将以独立模式运行{Colors.RESET}")

            self.kernel = JRVS_Kernel(api_client=api_client_instance)
            self.kernel.enable_router_mode()
            
            print(f"{Colors.GREEN}[TUI] JRVS Kernel初始化完成！{Colors.RESET}")
            print(f"{Colors.GREEN}[TUI] 当前模型: {self.kernel.get_current_model()['name']}{Colors.RESET}")
            
            if self.kernel.simulation_mode:
                print(f"{Colors.YELLOW}[TUI] 当前运行在模拟模式下（未检测到LLM后端）{Colors.RESET}")
                
            return True
        except Exception as e:
            print(f"{Colors.RED}[TUI] Kernel初始化失败: {e}{Colors.RESET}")
            return False

    def cmd_help(self, args):
        print(f"\n{Colors.BOLD}{Colors.CYAN}可用命令:{Colors.RESET}")
        for cmd, info in self.commands.items():
            print(f"  {Colors.BLUE}{cmd}{Colors.RESET} - {info['desc']}")
        print(f"\n{Colors.GREY}提示: 直接输入文字即可与Kirara聊天{Colors.RESET}")

    def cmd_exit(self, args):
        print(f"\n{Colors.PURPLE}再见啦~ Kirara会想念你的！(≧∀≦)ゞ{Colors.RESET}")
        self.running = False

    def cmd_model(self, args):
        if not self.kernel:
            self._print_message("error", "Kernel未初始化")
            return
        
        if not args or args[0] == "list":
            models = self.kernel.get_available_models()
            print(f"\n{Colors.BOLD}{Colors.CYAN}可用模型:{Colors.RESET}")
            for m in models:
                current = " (当前)" if m["key"] == self.kernel.current_model else ""
                print(f"  {Colors.GREEN}{m['key']}{Colors.RESET} - {m['name']}{current}")
        else:
            model_key = args[0]
            success, message = self.kernel.switch_model(model_key)
            if success:
                self._print_message("info", f"已切换到: {message}")
            else:
                self._print_message("error", message)

    def cmd_memory(self, args):
        if not self.kernel:
            self._print_message("error", "Kernel未初始化")
            return
        
        memory = self.kernel.get_raw_memory()
        if memory:
            print(f"\n{Colors.BOLD}{Colors.CYAN}记忆库内容:{Colors.RESET}")
            print(f"{Colors.GREY}{memory}{Colors.RESET}")
        else:
            self._print_message("info", "记忆库为空")

    def cmd_deep(self, args):
        self.deep_think_mode = not self.deep_think_mode
        status = "启用" if self.deep_think_mode else "禁用"
        self._print_message("info", f"深度思考模式已{status}")

    def cmd_clear(self, args):
        os.system('cls' if os.name == 'nt' else 'clear')
        self._print_banner()

    def cmd_status(self, args):
        if not self.kernel:
            self._print_message("error", "Kernel未初始化")
            return
        
        current_model = self.kernel.get_current_model()
        print(f"\n{Colors.BOLD}{Colors.CYAN}系统状态:{Colors.RESET}")
        print(f"  {Colors.GREEN}当前模型:{Colors.RESET} {current_model['name']}")
        print(f"  {Colors.GREEN}深度思考:{Colors.RESET} {'开启' if self.deep_think_mode else '关闭'}")
        print(f"  {Colors.GREEN}路由模式:{Colors.RESET} {'开启' if self.kernel.router_mode else '关闭'}")
        print(f"  {Colors.GREEN}模拟模式:{Colors.RESET} {'开启' if self.kernel.simulation_mode else '关闭'}")
        print(f"  {Colors.GREEN}工作记忆:{Colors.RESET} {len(self.kernel._get_working_memory(self.session_id))} 条消息")

    def cmd_save(self, args):
        if not self.kernel:
            self._print_message("error", "Kernel未初始化")
            return
        
        self._print_message("info", "对话历史已自动保存到记忆库")

    def _parse_command(self, input_text):
        parts = input_text.strip().split(' ', 1)
        cmd = parts[0]
        args = parts[1].split() if len(parts) > 1 else []
        
        if cmd in self.commands:
            self.commands[cmd]["func"](args)
            return True
        return False

    def _display_thinking_steps(self, thinking_status):
        if not thinking_status or not self.show_thinking:
            return
        
        print(f"\n{Colors.YELLOW}{Colors.BOLD}[思考过程]{Colors.RESET}")
        for step in thinking_status:
            phase = step.get("phase", "unknown")
            status = step.get("status", "")
            message = step.get("message", "")
            
            phase_color = {
                "draft": Colors.CYAN,
                "reflect": Colors.YELLOW,
                "polish": Colors.PURPLE
            }.get(phase, Colors.WHITE)
            
            print(f"  {phase_color}[{phase}]{Colors.RESET} {status}: {message}")
            
            if "critique" in step and step["critique"]:
                print(f"    {Colors.RED}审查: {step['critique']}{Colors.RESET}")

    def chat_loop(self):
        print(f"\n{Colors.PURPLE}{Colors.BOLD}欢迎使用Kirara TUI！(≧∀≦)ゞ{Colors.RESET}")
        print(f"{Colors.GREY}输入 /help 查看可用命令，直接输入文字即可开始聊天{Colors.RESET}")
        self._print_separator()

        while self.running:
            try:
                user_input = input(self._print_prompt())
                
                if not user_input.strip():
                    continue
                
                if self._parse_command(user_input):
                    continue

                print(f"\n{Colors.BLUE}{Colors.BOLD}[User]{Colors.RESET}")
                print(f"  {user_input}")
                print(f"\n{Colors.YELLOW}思考中...{Colors.RESET}", end='', flush=True)

                result = self.kernel.chat(
                    user_input,
                    session_id=self.session_id,
                    deep_think=self.deep_think_mode
                )

                print('\r', end='', flush=True)
                print(' ' * 20 + '\r', end='', flush=True)

                if result.get("deep_think", False):
                    self._display_thinking_steps(result.get("thinking_status"))
                    print(f"\n{Colors.YELLOW}最终置信度: {result.get('final_confidence', 0):.2f}{Colors.RESET}")

                self._print_separator()
                self._print_message("kirara", result.get("response", "无响应"))

                routing_info = result.get("routing_info")
                if routing_info:
                    action = routing_info.get("action", "")
                    model = routing_info.get("model", "")
                    print(f"\n{Colors.GREY}[路由信息] 动作: {action}, 模型: {model}{Colors.RESET}")

            except KeyboardInterrupt:
                print(f"\n\n{Colors.PURPLE}再见啦~ (｡･ω･｡)ﾉ{Colors.RESET}")
                self.running = False
            except EOFError:
                print(f"\n{Colors.PURPLE}再见啦~ (｡･ω･｡)ﾉ{Colors.RESET}")
                self.running = False
            except Exception as e:
                print(f"\n{Colors.RED}[错误] {e}{Colors.RESET}")

    def run(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        self._print_banner()
        
        if not self.init_kernel():
            print(f"{Colors.RED}[TUI] 无法初始化Kernel，退出...{Colors.RESET}")
            return

        self.chat_loop()

if __name__ == "__main__":
    tui = JRVS_TUI()
    tui.run()