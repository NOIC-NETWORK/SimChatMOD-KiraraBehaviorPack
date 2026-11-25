# ==================== P3.5 — Kirara 蓝图化 ====================
# Kirara 聊天 / Agent / TTS / 人设 / 记忆 / 重置
# 所有后端路由从 lmbrew.py 迁入，对外 URL 完全不变

import os
import sys
import json
import queue
import smtplib
import threading
import datetime
import time
import random
import string
import hashlib
import re
import shutil
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Blueprint, request, jsonify, send_from_directory, Response, stream_with_context

# 目录基准：本文件位于 <项目根>/kirara/services/kirara_server.py
SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))   # kirara/services
KIRARA_DIR = os.path.dirname(SERVICES_DIR)                  # kirara
PROJECT_ROOT = os.path.dirname(KIRARA_DIR)                  # 项目根
if SERVICES_DIR not in sys.path:
    sys.path.insert(0, SERVICES_DIR)

from jrvs import JRVS_Kernel, resolve_persona_system, get_persona_options, DEFAULT_PERSONA
from kirara_tts import (
    TTS_AVAILABLE,
    get_voice_presets,
    list_tts_voices,
    synthesize_to_data_uri,
    DEFAULT_VOICE_SELECTOR,
)
from agent import (
    AgentLoop, list_agent_tools,
    agent_runs,
    save_pending_state, load_pending_state, discard_pending_state, DEFAULT_APPROVAL_TTL,
    configure_shell, DEFAULT_SHELL_TIMEOUT,
)

kirara_bp = Blueprint('kirara', __name__, static_folder=None)

jrvs_kernel = None

def init_jrvs():
    global jrvs_kernel
    if jrvs_kernel is None:
        # 记忆库不入库，首次运行先把目录骨架建好（幂等，失败不影响内核启动）
        try:
            from init_memory import ensure_memory_layout

            ensure_memory_layout()
        except Exception as e:
            print(f"[Kirara] 记忆库目录初始化失败: {e}")
        try:
            jrvs_kernel = JRVS_Kernel()
            jrvs_kernel.enable_router_mode()
            apply_knowledge_base_options(jrvs_kernel)
            print("[Kirara] JRVS Kernel 初始化成功")
        except Exception as e:
            print(f"[Kirara] JRVS Kernel 初始化失败: {e}")
            jrvs_kernel = None

def apply_knowledge_base_options(kernel):
    """将 options.json 中的知识库配置应用到已初始化的 kernel（首次初始化与保存配置时复用）。"""
    try:
        opts = load_kirara_options()
        kb_path = opts.get('knowledge_base_path') or ''
        kernel.configure_knowledge_base(
            enabled=opts.get('knowledge_base_enabled', True),
            top_k=opts.get('knowledge_base_top_k', 4),
            min_score=opts.get('knowledge_base_min_score', 0.30),
            path=kb_path.strip() or None,
        )
    except Exception as e:
        print(f"[Kirara] 知识库配置应用失败: {e}")

@kirara_bp.route('/kirara')
def kirara_page():
    return send_from_directory(KIRARA_DIR, 'kirara.html')

@kirara_bp.route('/kirara/<path:filename>')
def serve_kirara(filename):
    return send_from_directory(KIRARA_DIR, filename)

@kirara_bp.route('/apps/kirara/<path:filename>')
def serve_kirara_apps(filename):
    return send_from_directory(KIRARA_DIR, filename)

@kirara_bp.route('/api/kirara/chat', methods=['POST'])
def kirara_chat():
    try:
        init_jrvs()
        if jrvs_kernel is None:
            return jsonify({'error': 'JRVS Kernel初始化失败'}), 500
        
        data = request.get_json()
        message = data.get('message', '')
        history = data.get('history', [])
        session_id = data.get('session_id')

        if not message:
            return jsonify({'error': '消息内容为空'}), 400

        # 人设提示词：优先使用请求参数，缺省时读取 options.json 持久化配置
        persona_key = data.get('persona')
        if not persona_key:
            persona_key = load_kirara_options().get('persona', DEFAULT_PERSONA)
        system_prompt = build_system_prompt_with_skills(persona_key)
        if system_prompt:
            print(f"[Kirara] 使用人设提示词: persona={persona_key}, system_prompt_len={len(system_prompt)}")

        # 思考模式：优先请求参数，缺省走配置
        think_mode = data.get('think_mode') or load_kirara_options().get('think_mode', 'low')

        # 流式输出：逐 token 推送 SSE，便于前端中途停止（不弹出模型）
        def generate():
            try:
                for token in jrvs_kernel.chat_stream(
                    message,
                    history=history,
                    session_id=session_id,
                    system_prompt=system_prompt,
                    think_mode=think_mode
                ):
                    # reality_check sentinel：模型输出命中违规时下发特殊事件（前端吞气泡+切对话）
                    if isinstance(token, dict) and "__reality_check__" in token:
                        yield f"data: {json.dumps(token, ensure_ascii=False)}\n\n"
                    # 工作流状态事件：技能调用 / hippo 记忆操作（前端渲染工作气泡，不计入正文）
                    elif isinstance(token, dict) and "__workflow__" in token:
                        payload = dict(token["__workflow__"])
                        payload["event"] = "workflow"
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    else:
                        yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except GeneratorExit:
                # 客户端断开（用户点击停止）：直接退出，不抛出异常打断连接
                print("[Kirara] 客户端中止流式生成")
                raise

        resp = Response(stream_with_context(generate()), mimetype='text/event-stream')
        resp.headers['Cache-Control'] = 'no-cache'
        resp.headers['X-Accel-Buffering'] = 'no'
        return resp
    except Exception as e:
        print(f"[Kirara] chat API错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/memory', methods=['GET'])
def kirara_memory():
    try:
        init_jrvs()
        if jrvs_kernel is None:
            return jsonify({'error': 'JRVS Kernel初始化失败'}), 500
        
        memory = jrvs_kernel.get_memory_for_display()
        return jsonify({
            'success': True,
            'memory': memory
        })
    except Exception as e:
        print(f"[Kirara] memory API错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/tts', methods=['POST'])
def kirara_tts():
    """Kirara语音合成API：按所选音色合成 WAV，以 data URI 返回给浏览器播放"""
    try:
        data = request.get_json()
        text = (data.get('text', '') or '').strip()

        if not text:
            return jsonify({'error': '文本内容为空'}), 400
        if not TTS_AVAILABLE:
            return jsonify({'error': 'TTS 引擎不可用：服务器未安装 pyttsx3'}), 503

        # 音色选择：优先请求参数，缺省读取持久化配置
        voice_selector = data.get('voice')
        if not voice_selector:
            voice_selector = load_kirara_options().get('voice', DEFAULT_VOICE_SELECTOR)

        # 限制单次合成长度，避免 SAPI 长时间阻塞
        if len(text) > 2000:
            text = text[:2000]

        audio_uri, voice_name = synthesize_to_data_uri(text, voice_selector)

        return jsonify({
            'success': True,
            'audio': audio_uri,
            'voice': voice_selector,
            'voice_name': voice_name
        })
    except Exception as e:
        print(f"[Kirara] TTS API错误: {e}")
        return jsonify({'error': str(e)}), 503

@kirara_bp.route('/api/kirara/tts/voices', methods=['GET'])
def kirara_tts_voices():
    """枚举可用的预设音色与本机系统语音，供前端动态渲染下拉框"""
    try:
        system_voices, error = (list_tts_voices() if TTS_AVAILABLE else ([], 'pyttsx3 未安装'))
        return jsonify({
            'success': True,
            'tts_available': TTS_AVAILABLE,
            'presets': get_voice_presets(),
            'voices': system_voices,
            'default_voice': DEFAULT_VOICE_SELECTOR,
            'error': error
        })
    except Exception as e:
        print(f"[Kirara] 获取音色列表错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/personas', methods=['GET'])
def kirara_personas():
    """枚举 JRVS-7B SFT 双人设（通过 system prompt 切换）"""
    try:
        return jsonify({
            'success': True,
            'personas': get_persona_options(),
            'default_persona': DEFAULT_PERSONA
        })
    except Exception as e:
        print(f"[Kirara] 获取人设列表错误: {e}")
        return jsonify({'error': str(e)}), 500

def _get_agent_shell_options(options=None):
    """从 options 读取 shell 开关与超时（fail-closed：缺省关闭、10s 超时）。"""
    options = options or load_kirara_options()
    shell_enabled = bool(options.get('agent_shell_enabled'))
    try:
        shell_timeout = int(options.get('agent_shell_timeout') or DEFAULT_SHELL_TIMEOUT)
    except (TypeError, ValueError):
        shell_timeout = DEFAULT_SHELL_TIMEOUT
    return shell_enabled, shell_timeout


def _agent_sse_response(run_id, run_callable, ttl):
    """共享 SSE 运行器：在 worker 线程执行 run_callable(emit)，捕获挂起态并落盘。

    run_callable(emit) -> Optional[pending_state]  返回挂起态表示需要审批，None 表示任务终结。
    """
    event_queue = queue.Queue()
    pending_holder = {'state': None}

    def emit(evt):
        event_queue.put(evt)

    def worker():
        try:
            pending_holder['state'] = run_callable(emit)
        except Exception as e:
            print(f"[Kirara] agent 运行错误: {e}")
            emit({'event': 'error', 'message': f'Agent 运行异常: {e}'})
            pending_holder['state'] = None
        finally:
            # 任务终结则清理挂起态；挂起则落盘等待审批
            state = pending_holder['state']
            if state is None:
                discard_pending_state(run_id)
            else:
                save_pending_state(state, ttl=ttl)
            agent_runs.finish(run_id)
            event_queue.put(None)

    def generate():
        yield f"data: {json.dumps({'event': 'run_started', 'run_id': run_id}, ensure_ascii=False)}\n\n"
        threading.Thread(target=worker, daemon=True).start()
        try:
            while True:
                try:
                    evt = event_queue.get(timeout=60)
                except queue.Empty:
                    # 长推理期间发送心跳注释行，防止连接被代理/浏览器掐断
                    yield ": keepalive\n\n"
                    continue
                if evt is None:
                    break
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except GeneratorExit:
            # 客户端断开：中止任务（fail-closed）
            agent_runs.abort(run_id)
            raise
        finally:
            agent_runs.abort(run_id)   # 兜底：无论何种退出都让循环尽快停止
            agent_runs.remove(run_id)

    resp = Response(stream_with_context(generate()), mimetype='text/event-stream')
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp


@kirara_bp.route('/api/kirara/agent/tools', methods=['GET'])
def kirara_agent_tools():
    """Agent 工具清单与风险分级（前端据此展示；shell 的 enabled 反映当前 options）"""
    try:
        shell_enabled, shell_timeout = _get_agent_shell_options()
        configure_shell(shell_enabled, shell_timeout)
        return jsonify({'success': True, 'tools': list_agent_tools()})
    except Exception as e:
        print(f"[Kirara] agent tools API错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/agent/run', methods=['POST'])
def kirara_agent_run():
    """Agent 运行入口（SSE）。ReAct 循环在后端执行，浏览器只渲染事件。"""
    try:
        init_jrvs()
        if jrvs_kernel is None:
            return jsonify({'error': 'JRVS Kernel初始化失败'}), 500

        data = request.get_json() or {}
        message = (data.get('message') or '').strip()
        if not message:
            return jsonify({'error': '消息内容为空'}), 400

        # 人设：与 /api/kirara/chat 同源（请求参数优先，缺省读持久化配置）
        persona_key = data.get('persona')
        if not persona_key:
            persona_key = load_kirara_options().get('persona', DEFAULT_PERSONA)
        system_prompt = build_system_prompt_with_skills(persona_key)

        options = load_kirara_options()
        try:
            max_turns = int(options.get('agent_max_turns') or 10)
        except (TypeError, ValueError):
            max_turns = 10
        workdir = options.get('agent_workdir') or None
        try:
            ttl = int(options.get('agent_approval_ttl') or DEFAULT_APPROVAL_TTL)
        except (TypeError, ValueError):
            ttl = DEFAULT_APPROVAL_TTL
        shell_enabled, shell_timeout = _get_agent_shell_options(options)

        run_id = agent_runs.create()
        history = data.get('history') or []
        session_id = data.get('session_id')
        workdir_local = workdir
        max_turns_local = max_turns
        shell_enabled_local = shell_enabled
        shell_timeout_local = shell_timeout

        def run_callable(emit):
            # 每次运行前按当前 options 同步 shell 开关（worker 线程内，避免与注册表状态不一致）
            configure_shell(shell_enabled_local, shell_timeout_local)
            run = agent_runs.get(run_id)
            loop = AgentLoop(
                jrvs_kernel,
                workdir=workdir_local,
                max_turns=max_turns_local,
                abort_event=run['abort'] if run else None,
                shell_enabled=shell_enabled_local,
                shell_timeout=shell_timeout_local,
            )
            return loop.run(
                message=message,
                history=history,
                session_id=session_id,
                persona=persona_key,
                run_id=run_id,
                system_prompt=system_prompt,
                emit=emit,
            )

        return _agent_sse_response(run_id, run_callable, ttl)
    except Exception as e:
        print(f"[Kirara] agent run API错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/agent/approve', methods=['POST'])
def kirara_agent_approve():
    """审批挂起的写操作并恢复运行（返回新的 SSE 流）。

    请求：{run_id, decision: 'approve'|'reject', edits?}
    - 加载挂起态（TTL/损坏均 fail-closed）
    - 复用 run_id 重新登记内存条目（新建 abort 事件）
    - 按 persona 重新解析 system_prompt，调用 loop.resume()
    - 若再次挂起 → 落盘新挂起态；终结 → 清理挂起态
    """
    try:
        init_jrvs()
        if jrvs_kernel is None:
            return jsonify({'error': 'JRVS Kernel初始化失败'}), 500

        data = request.get_json() or {}
        run_id = (data.get('run_id') or '').strip()
        decision = (data.get('decision') or '').strip().lower()
        edits = data.get('edits')
        if not run_id:
            return jsonify({'error': 'run_id 为空'}), 400
        if decision not in ('approve', 'reject'):
            return jsonify({'error': "decision 必须为 'approve' 或 'reject'"}), 400

        options = load_kirara_options()
        try:
            ttl = int(options.get('agent_approval_ttl') or DEFAULT_APPROVAL_TTL)
        except (TypeError, ValueError):
            ttl = DEFAULT_APPROVAL_TTL

        state = load_pending_state(run_id, ttl=ttl)
        if state is None:
            return jsonify({'error': '挂起态不存在或已过期（fail-closed），请重新发起任务'}), 410

        persona_key = state.get('persona') or options.get('persona', DEFAULT_PERSONA)
        system_prompt = build_system_prompt_with_skills(persona_key)
        workdir = state.get('workdir') or options.get('agent_workdir') or None
        try:
            max_turns = int(state.get('max_turns') or options.get('agent_max_turns') or 10)
        except (TypeError, ValueError):
            max_turns = 10
        # 审批恢复时以当前 options 重新判定 shell 开关：
        # 若用户在挂起期间关闭了 shell，即使批准，ShellTool 也会 fail-closed 拒绝执行
        shell_enabled, shell_timeout = _get_agent_shell_options(options)

        # 复用 run_id 重新登记（新建 abort 事件，旧的已被原流程清理）
        agent_runs.register(run_id)
        workdir_local = workdir
        max_turns_local = max_turns
        shell_enabled_local = shell_enabled
        shell_timeout_local = shell_timeout
        decision_local = decision
        edits_local = edits

        def run_callable(emit):
            configure_shell(shell_enabled_local, shell_timeout_local)
            run = agent_runs.get(run_id)
            loop = AgentLoop(
                jrvs_kernel,
                workdir=workdir_local,
                max_turns=max_turns_local,
                abort_event=run['abort'] if run else None,
                shell_enabled=shell_enabled_local,
                shell_timeout=shell_timeout_local,
            )
            return loop.resume(state, decision_local, edits_local, system_prompt, emit=emit)

        return _agent_sse_response(run_id, run_callable, ttl)
    except Exception as e:
        print(f"[Kirara] agent approve API错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/agent/abort', methods=['POST'])
def kirara_agent_abort():
    """中止 Agent 运行（Force Eject 同源接线）。

    请求：{run_id}
    - 运行中：set abort event，循环在轮次边界/命令执行窗口内立即终止（shell 进程树被杀）
    - 挂起待审批：删除挂起态文件，审批随即无法恢复（fail-closed）
    - 幂等：run_id 不存在也返回成功（可能刚终结/已清理）
    """
    try:
        data = request.get_json() or {}
        run_id = (data.get('run_id') or '').strip()
        if not run_id:
            return jsonify({'error': 'run_id 为空'}), 400
        run = agent_runs.get(run_id)
        agent_runs.abort(run_id)
        discard_pending_state(run_id)
        print(f"[Kirara] agent abort: run_id={run_id} active={bool(run)}")
        return jsonify({'success': True, 'run_id': run_id, 'was_active': bool(run)})
    except Exception as e:
        print(f"[Kirara] agent abort API错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/agent/tasks', methods=['GET'])
def kirara_agent_tasks_list():
    """列出所有 Agent task session（按修改时间倒序）。

    Task session_id 以 `agent_` 前缀区分于 Chat 的 `default` 会话；
    会话文件由 JRVS_Kernel._save_session 落盘到 sessions_dir/agent_*.json。
    """
    try:
        init_jrvs()
        if jrvs_kernel is None:
            return jsonify({'error': 'JRVS Kernel初始化失败'}), 500

        sessions_dir = getattr(jrvs_kernel, 'sessions_dir', None)
        if not sessions_dir or not os.path.isdir(sessions_dir):
            return jsonify({'success': True, 'tasks': []})

        tasks = []
        for name in os.listdir(sessions_dir):
            if not (name.startswith('agent_') and name.endswith('.json')):
                continue
            sid = name[:-5]
            full = os.path.join(sessions_dir, name)
            try:
                with open(full, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                history = data.get('conversation_history') or []
                first_user = next(
                    (m.get('content', '') for m in history if isinstance(m, dict) and m.get('role') == 'user'),
                    ''
                )
                tasks.append({
                    'session_id': sid,
                    'message': (first_user or '')[:80],
                    'message_count': len(history),
                    'summary': (data.get('summary') or '')[:120],
                    'mtime': int(os.path.getmtime(full))
                })
            except (OSError, ValueError) as e:
                print(f"[Agent] 读取 task session {sid} 失败（已跳过）: {e}")
        tasks.sort(key=lambda t: t.get('mtime', 0), reverse=True)
        return jsonify({'success': True, 'tasks': tasks})
    except Exception as e:
        print(f"[Kirara] agent tasks list API错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/agent/tasks/<path:sid>', methods=['DELETE'])
def kirara_agent_task_delete(sid):
    """删除指定 Agent task session 文件。

    安全约束：
    - 仅允许 `agent_` 前缀的 session_id（拒绝删除 Chat 的 default 会话）
    - 二次校验路径必须位于 sessions_dir 内（防目录穿越）
    """
    try:
        init_jrvs()
        if jrvs_kernel is None:
            return jsonify({'error': 'JRVS Kernel初始化失败'}), 500
        if not sid.startswith('agent_'):
            return jsonify({'error': '非法 session_id（仅允许 agent_ 前缀）'}), 400

        sessions_dir = getattr(jrvs_kernel, 'sessions_dir', None)
        if not sessions_dir:
            return jsonify({'error': '会话目录未就绪'}), 500

        path = os.path.join(sessions_dir, f'{sid}.json')
        if not os.path.abspath(path).startswith(os.path.abspath(sessions_dir) + os.sep):
            return jsonify({'error': '路径越界'}), 400
        if not os.path.isfile(path):
            return jsonify({'error': '任务不存在'}), 404
        os.remove(path)
        print(f"[Kirara] agent task 删除: sid={sid}")
        return jsonify({'success': True, 'session_id': sid})
    except Exception as e:
        print(f"[Kirara] agent task delete API错误: {e}")
        return jsonify({'error': str(e)}), 500

def get_options_path():
    return os.path.join(KIRARA_DIR, 'memories', 'options.json')

DEFAULT_KIRARA_OPTIONS = {
    'max_context': 1024000,
    'online': False,
    'hippo': True,
    'cloud_acceleration': True,
    'think_mode': 'low',
    'persona': DEFAULT_PERSONA,
    'voice': DEFAULT_VOICE_SELECTOR,
    'disable_anime': False,
    'ui_mode': 'chat',            # 'chat' | 'agent'（Chat/Agent 切换开关持久化）
    'agent_max_turns': 10,        # Agent ReAct 最大轮数
    'agent_workdir': None,        # None 时后端解析为项目根
    'agent_shell_enabled': False, # shell 工具默认关闭（开启后仍逐次审批+黑名单+超时+cwd 限定）
    'agent_shell_timeout': 10,    # 单条 shell 命令超时秒数（上限 30，超时杀进程树）
    'agent_approval_ttl': 600,    # 审批挂起态存活秒数（过期/重启后拒绝恢复，fail-closed）
    # 个性化知识库（knowledge_base.md）：抑制 7B 模型对用户个人事实的幻觉
    'knowledge_base_enabled': True,
    'knowledge_base_top_k': 4,       # 注入片段数（1~8）
    'knowledge_base_min_score': 0.30,# 归一化检索阈值（0~1，越高越严格）
    'knowledge_base_path': '',       # 空字符串=自动解析（kirara/ → openmaid/）
    'muted': False,                  # 静音开关：开启后停止当前 TTS 并阻止后续播报
    # 技能（Skill）管理：用户自定义技能列表，每项含 id/name/description/content/enabled/created_at
    # 通过 system prompt 注入或 Agent 工具调用扩展模型能力，前端在「选项 > 技能管理」维护
    'skills': []
}

def load_kirara_options():
    """读取 options.json 并与默认值合并（不写回）。"""
    options = dict(DEFAULT_KIRARA_OPTIONS)
    options_path = get_options_path()
    if os.path.exists(options_path):
        try:
            with open(options_path, 'r', encoding='utf-8') as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                options.update(stored)
        except Exception as e:
            print(f"[Kirara] 读取配置失败，使用默认值: {e}")
    return options

SKILLS_PROMPT_MAX_CHARS = 8000

def build_system_prompt_with_skills(persona_key):
    """
    构造最终 system prompt：人设 SFT 触发词 + 已启用技能 content 拼接。

    实现 skills-design.md §3.3.2 的 trigger=prompt 模式：
    - 调用 resolve_persona_system 获取 SFT 触发词（"JRVS"/"Kirara"）或 None（native）
    - 从 options.json 读取 skills 字段，过滤 enabled=True 的技能
    - 按顺序拼接技能 content 到触发词之后，超过 SKILLS_PROMPT_MAX_CHARS 时截断
    - 与现有 persona system prompt 共存（触发词保持首位以维持 SFT 人设识别）

    Returns: str | None — 返回 None 时模型走原生人设（无 system prompt）
    """
    base_prompt = resolve_persona_system(persona_key)

    try:
        skills = load_kirara_options().get('skills') or []
    except Exception as e:
        print(f"[Kirara] 读取技能列表失败: {e}")
        skills = []

    enabled_skills = [s for s in skills if isinstance(s, dict) and s.get('enabled')]
    if not enabled_skills:
        return base_prompt

    parts = []
    total_len = 0
    for skill in enabled_skills:
        content = (skill.get('content') or '').strip()
        if not content:
            continue
        if total_len + len(content) > SKILLS_PROMPT_MAX_CHARS:
            print(f"[Kirara] 技能 content 超出总长度上限（{SKILLS_PROMPT_MAX_CHARS} 字符），已截断；已启用 {len(parts)} 项技能")
            break
        parts.append(content)
        total_len += len(content)

    if not parts:
        return base_prompt

    skills_block = "\n\n".join(parts)
    print(f"[Kirara] 注入 {len(parts)} 项技能到 system prompt（{total_len} 字符）")
    if base_prompt:
        # SFT 触发词在前，技能指令作为附加提示词片段（保持人设触发词首位以维持 SFT 识别）
        return f"{base_prompt}\n[技能指令]\n{skills_block}"
    # native 人设：无 SFT 触发词，技能指令独立作为 system prompt
    return f"[技能指令]\n{skills_block}"

@kirara_bp.route('/api/kirara/options', methods=['GET'])
def kirara_get_options():
    try:
        return jsonify({
            'success': True,
            'options': load_kirara_options()
        })
    except Exception as e:
        print(f"[Kirara] 获取配置错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/options', methods=['POST'])
def kirara_save_options():
    try:
        options_path = get_options_path()
        data = request.get_json()
        incoming = data.get('options', {})
        if not isinstance(incoming, dict):
            return jsonify({'error': 'options 必须是对象'}), 400

        # 与现有配置合并后写回，避免旧客户端提交时清空新增字段
        options = load_kirara_options()
        options.update(incoming)

        # skills 字段校验：必须是列表，且每项为含必填字段的 dict；非法整体丢弃，保留旧值
        if 'skills' in incoming:
            raw_skills = incoming.get('skills')
            if not isinstance(raw_skills, list):
                return jsonify({'error': 'skills 必须是数组'}), 400
            cleaned_skills = []
            for idx, item in enumerate(raw_skills):
                if not isinstance(item, dict):
                    continue
                name = (item.get('name') or '').strip()
                if not name:
                    continue  # 名称必填，空名称直接丢弃
                cleaned_skills.append({
                    'id': str(item.get('id') or f'skill_{int(__import__("time").time()*1000)}_{idx}'),
                    'name': name[:50],
                    'description': str(item.get('description') or '').strip()[:200],
                    'content': str(item.get('content') or '').strip()[:8000],
                    'enabled': bool(item.get('enabled', True)),
                    'created_at': str(item.get('created_at') or '')
                })
            options['skills'] = cleaned_skills

        os.makedirs(os.path.dirname(options_path), exist_ok=True)
        with open(options_path, 'w', encoding='utf-8') as f:
            json.dump(options, f, indent=4, ensure_ascii=False)

        # 若 kernel 已在运行，热更新知识库配置，无需重启服务
        if jrvs_kernel is not None:
            apply_knowledge_base_options(jrvs_kernel)

        return jsonify({
            'success': True,
            'message': '配置保存成功',
            'options': options
        })
    except Exception as e:
        print(f"[Kirara] 保存配置错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/knowledge/status', methods=['GET'])
def kirara_knowledge_status():
    """个性化知识库运行状态（文件路径/分块数/检索后端/当前开关与阈值）。"""
    try:
        init_jrvs()
        if jrvs_kernel is None:
            return jsonify({'success': False, 'error': 'JRVS Kernel 初始化失败'}), 500
        kb = getattr(jrvs_kernel, 'knowledge_base', None)
        if kb is None:
            return jsonify({'success': False, 'error': '知识库模块不可用'}), 503
        status = kb.status()
        status['success'] = True
        status['enabled'] = bool(getattr(jrvs_kernel, 'kb_enabled', True))
        return jsonify(status)
    except Exception as e:
        print(f"[Kirara] 获取知识库状态错误: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def get_user_path():
    return os.path.join(KIRARA_DIR, 'memories', 'user.json')

@kirara_bp.route('/api/kirara/user/status', methods=['GET'])
def kirara_user_status():
    try:
        user_path = get_user_path()
        is_registered = os.path.exists(user_path)
        
        return jsonify({
            'success': True,
            'is_registered': is_registered,
            'message': '已注册' if is_registered else '未注册'
        })
    except Exception as e:
        print(f"[Kirara] 获取用户状态错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/user/info', methods=['GET'])
def kirara_user_info():
    try:
        user_path = get_user_path()
        if not os.path.exists(user_path):
            return jsonify({'success': False, 'message': '用户未注册'}), 404
        
        with open(user_path, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        
        return jsonify({
            'success': True,
            'user_data': user_data
        })
    except Exception as e:
        print(f"[Kirara] 获取用户信息错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/user/register', methods=['POST'])
def kirara_user_register():
    try:
        user_path = get_user_path()
        data = request.get_json()
        
        required_fields = ['username', 'birthday']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'缺少必要字段: {field}'}), 400
        
        user_data = {
            'username': data['username'],
            'birthday': data['birthday'],
            'contact_info': data.get('contact_info', {}),
            'emergency_contact': data.get('emergency_contact', {}),
            'avatar': data.get('avatar', ''),
            'registered_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        os.makedirs(os.path.dirname(user_path), exist_ok=True)
        with open(user_path, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, indent=4, ensure_ascii=False)
        
        print(f"[Kirara] 用户注册成功: {data['username']}")
        
        return jsonify({
            'success': True,
            'message': '注册成功！',
            'user_data': user_data
        })
    except Exception as e:
        print(f"[Kirara] 用户注册错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/user/reset', methods=['POST'])
def kirara_user_reset():
    try:
        user_path = get_user_path()
        if os.path.exists(user_path):
            os.remove(user_path)
            print("[Kirara] 用户数据已重置")
        
        return jsonify({
            'success': True,
            'message': '用户数据已重置，请重新注册'
        })
    except Exception as e:
        print(f"[Kirara] 重置用户数据错误: {e}")
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/user/update', methods=['POST'])
def kirara_user_update():
    try:
        user_path = get_user_path()
        if not os.path.exists(user_path):
            return jsonify({'error': '用户未注册'}), 404
        
        data = request.get_json()
        
        with open(user_path, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        
        if 'username' in data:
            user_data['username'] = data['username']
        if 'birthday' in data:
            user_data['birthday'] = data['birthday']
        if 'contact_info' in data:
            user_data['contact_info'] = data['contact_info']
        if 'emergency_contact' in data:
            user_data['emergency_contact'] = data['emergency_contact']
        if 'avatar' in data:
            user_data['avatar'] = data['avatar']
        
        with open(user_path, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, indent=4, ensure_ascii=False)
        
        print(f"[Kirara] 用户信息已更新: {user_data['username']}")
        
        return jsonify({
            'success': True,
            'message': '用户信息更新成功！',
            'user_data': user_data
        })
    except Exception as e:
        print(f"[Kirara] 更新用户信息错误: {e}")
        return jsonify({'error': str(e)}), 500

# SMTP 配置文件路径（默认值，用户可在前端设置面板配置）
def get_smtp_config_path():
    return os.path.join(KIRARA_DIR, 'memories', 'smtp_config.json')

DEFAULT_SMTP_CONFIG = {
    'smtp_host': 'smtp.qq.com',
    'smtp_port': 465,
    'smtp_user': '',       # 邮箱账号（完整地址）
    'smtp_pass': '',       # 授权码/密码（默认空 → 未配置时验证码退回控制台打印）
    'from_addr': '',       # 发件人显示地址（空=同 smtp_user）
    'use_ssl': True,       # SSL（465 端口用 True，587 用 False）
    'from_label': 'Kirara 重置服务',
}

def load_smtp_config():
    cfg = dict(DEFAULT_SMTP_CONFIG)
    path = get_smtp_config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                cfg.update(stored)
        except Exception as e:
            print(f'[Reset] 读取 SMTP 配置失败: {e}')
    return cfg

def save_smtp_config(cfg):
    path = get_smtp_config_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f'[Reset] 保存 SMTP 配置失败: {e}')
        return False

_RESET_CODE_STORE = {}
_RESET_CODE_TTL = 300       # 5 分钟有效
_RESET_CODE_MAX_ATTEMPTS = 5
_CODE_POOL = (string.ascii_uppercase + string.digits).replace('O', '').replace('0', '')  # 去掉易混淆字符

def _get_reset_target_paths():
    """返回重置时需要清理的所有路径。"""
    base = os.path.join(KIRARA_DIR, 'memories')
    chroma = os.path.join(base, 'kirara_memory')
    return {
        'options_path': os.path.join(base, 'options.json'),
        'buffer_path': os.path.join(base, 'buffer.txt'),
        'mem_txt_path': os.path.join(base, 'mem.txt'),
        'mem_md_path': os.path.join(base, 'mem.md'),
        'sys_prompt_path': os.path.join(base, 'sysPrompt.txt'),
        'sessions_dir': os.path.join(base, 'sessions'),
        'chroma_path': chroma,
        'chroma_long_term': os.path.join(chroma, 'long_term'),
        'chroma_cognitive': os.path.join(chroma, 'cognitive'),
        'kb_md_path': os.path.join(PROJECT_ROOT, 'knowledge_base.md'),
    }

def _execute_reset():
    """执行重置：清理所有目标文件/目录，并重新初始化。返回 (bool, str)。"""
    paths = _get_reset_target_paths()
    cleaned = []
    errors = []

    def _rm_file(p, label):
        if os.path.exists(p):
            try:
                os.remove(p)
                cleaned.append(label)
            except Exception as e:
                errors.append(f'{label}: {e}')

    def _rm_tree(p, label):
        if os.path.exists(p):
            try:
                shutil.rmtree(p)
                cleaned.append(label)
            except Exception as e:
                errors.append(f'{label}: {e}')

    # 1. options.json → 重写为默认值（保留文件存在，前端需要读）
    try:
        with open(paths['options_path'], 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_KIRARA_OPTIONS, f, ensure_ascii=False, indent=4)
        cleaned.append('options.json→defaults')
    except Exception as e:
        errors.append(f'options.json: {e}')

    # 2. buffer.txt / mem.txt / mem.md / sysPrompt.txt → 删除
    for key in ('buffer_path', 'mem_txt_path', 'mem_md_path', 'sys_prompt_path'):
        _rm_file(paths[key], os.path.basename(paths[key]))

    # 3. sessions/ 目录 → 删除整个目录
    _rm_tree(paths['sessions_dir'], 'sessions/')

    # 4. ChromaDB 两个持久化目录 → 删除
    for key in ('chroma_long_term', 'chroma_cognitive'):
        _rm_tree(paths[key], os.path.basename(paths[key]))

    # 5. knowledge_base.md → 删除
    _rm_file(paths['kb_md_path'], 'knowledge_base.md')

    # 6. 重建 sessions 目录（空目录，避免启动时报错）
    try:
        os.makedirs(paths['sessions_dir'], exist_ok=True)
    except Exception:
        pass

    status = 'OK' if not errors else f'PARTIAL: {"; ".join(errors)}'
    return status, cleaned

def _gen_reset_code():
    """梅森旋转 lite 版生成 6 位字母(大写)-数字组合。
    Python 的 random 模块底层就是 MT19937，这里显式用 Random 实例 + 时间播。"""
    rng = random.Random(time.time() * os.getpid())
    return ''.join(rng.choice(_CODE_POOL) for _ in range(6))

def _send_reset_email(to_addr, code):
    """通过 SMTP 发送验证码。未配置 SMTP 时返回 (False, 'SMTP_NOT_CONFIGURED')。"""
    cfg = load_smtp_config()
    if not cfg.get('smtp_user') or not cfg.get('smtp_pass'):
        # 未配置 SMTP：退回伪发送（验证码只在控制台打印）
        print(f'[Reset] SMTP 未配置，验证码(伪造发送)：{code} → {to_addr}')
        return True, 'FAKE_OK'

    host = cfg['smtp_host']
    port = int(cfg['smtp_port'])
    user = cfg['smtp_user']
    pwd = cfg['smtp_pass']
    from_addr = cfg.get('from_addr') or user
    from_label = cfg.get('from_label') or 'Kirara 重置服务'
    use_ssl = bool(cfg.get('use_ssl', True))

    subject = '【Kirara】重置验证码'
    body = (
        f'尊敬的用户：\n\n'
        f'您正在重置 Kirara 的所有个人数据。\n'
        f'您的验证码是：{code}\n'
        f'有效期 5 分钟。如非您本人操作，请忽略此邮件。\n\n'
        f'—— {from_label}\n'
    )
    # 邮件头必须有 From/To/Subject
    msg = (
        f'From: {from_label} <{from_addr}>\r\n'
        f'To: {to_addr}\r\n'
        f'Subject: {subject}\r\n'
        f'MIME-Version: 1.0\r\n'
        f'Content-Type: text/plain; charset=UTF-8\r\n'
        f'\r\n'
        f'{body}'
    )

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            server.starttls()
        server.login(user, pwd)
        server.sendmail(from_addr, [to_addr], msg.encode('utf-8'))
        server.quit()
        print(f'[Reset] 验证码已通过 SMTP 发送至 {to_addr}')
        return True, 'OK'
    except smtplib.SMTPAuthenticationError:
        return False, 'SMTP_AUTH_FAILED'
    except Exception as e:
        print(f'[Reset] SMTP 发送失败: {e}')
        return False, f'SMTP_ERROR: {type(e).__name__}'

@kirara_bp.route('/api/kirara/reset/smtp-config', methods=['GET', 'POST'])
def kirara_reset_smtp_config():
    """GET: 读取 SMTP 配置（密码字段脱敏为 '***'）；POST: 保存 SMTP 配置。"""
    try:
        if request.method == 'GET':
            cfg = load_smtp_config()
            safe = dict(cfg)
            if safe.get('smtp_pass'):
                safe['smtp_pass'] = '***'  # 前端需要知道"已填"但不回传明文
            return jsonify({'success': True, 'config': safe})

        # POST
        data = request.get_json() or {}
        incoming = {}
        # 字段白名单校验，只接受安全字段
        for k in ('smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass', 'from_addr', 'from_label'):
            if k in data:
                incoming[k] = data[k]
        if 'use_ssl' in data:
            incoming['use_ssl'] = bool(data['use_ssl'])

        current = load_smtp_config()
        # 如果前端传 smtp_pass='***'，表示密码不变（前端用占位符表示"保留原值"）
        if incoming.get('smtp_pass') == '***':
            incoming.pop('smtp_pass', None)

        current.update(incoming)
        ok = save_smtp_config(current)
        if not ok:
            return jsonify({'success': False, 'error': '写入配置失败'}), 500
        return jsonify({'success': True})
    except Exception as e:
        print(f'[Reset] SMTP config API 错误: {e}')
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/reset/request-code', methods=['POST'])
def kirara_reset_request_code():
    """生成验证码并发送到用户邮箱。
    请求体: { "email": "xxx@xxx.com" }
    SMTP 未配置时验证码不会真发，但 API 仍返回 success（验证码只在服务器控制台）——
    这样前端开发时无需真实 SMTP 也能走完整流程验证。"""
    global _RESET_CODE_STORE
    try:
        data = request.get_json() or {}
        to_addr = (data.get('email') or '').strip()
        if not to_addr or '@' not in to_addr or '.' not in to_addr.split('@')[-1]:
            return jsonify({'success': False, 'error': '邮箱格式不合法'}), 400

        # 防刷：同一邮箱 60 秒冷却
        existing = _RESET_CODE_STORE.get(to_addr)
        now = time.time()
        if existing and existing.get('expire_at', 0) > now and (now - existing.get('sent_at', 0) < 60):
            remaining = int(60 - (now - existing['sent_at']))
            return jsonify({'success': False, 'error': f'请 {remaining}s 后再试'}), 429

        code = _gen_reset_code()
        ok, reason = _send_reset_email(to_addr, code)
        if not ok:
            return jsonify({'success': False, 'error': f'验证码发送失败: {reason}'}), 502

        _RESET_CODE_STORE[to_addr] = {
            'code': code,
            'expire_at': now + _RESET_CODE_TTL,
            'sent_at': now,
            'attempts': 0,
        }

        smtp_cfg = load_smtp_config()
        smtp_ready = bool(smtp_cfg.get('smtp_user') and smtp_cfg.get('smtp_pass'))

        return jsonify({
            'success': True,
            'ttl': _RESET_CODE_TTL,
            'smtp_ready': smtp_ready,
            'debug_hint': None if smtp_ready else 'SMTP 未配置，验证码仅在服务器控制台打印（开发模式）',
        })
    except Exception as e:
        print(f'[Reset] request-code API 错误: {e}')
        return jsonify({'error': str(e)}), 500

@kirara_bp.route('/api/kirara/reset/execute', methods=['POST'])
def kirara_reset_execute():
    """验证验证码 + 执行数据清理。
    请求体: { "email": "xxx@xxx.com", "code": "ABC123" }"""
    global _RESET_CODE_STORE
    try:
        data = request.get_json() or {}
        to_addr = (data.get('email') or '').strip()
        code_input = (data.get('code') or '').strip().upper()

        if not to_addr or not code_input:
            return jsonify({'success': False, 'error': '缺少邮箱或验证码'}), 400

        stored = _RESET_CODE_STORE.get(to_addr)
        now = time.time()
        if not stored:
            return jsonify({'success': False, 'error': '请先获取验证码'}), 400
        if stored['expire_at'] < now:
            _RESET_CODE_STORE.pop(to_addr, None)
            return jsonify({'success': False, 'error': '验证码已过期，请重新获取'}), 400
        if stored['attempts'] >= _RESET_CODE_MAX_ATTEMPTS:
            _RESET_CODE_STORE.pop(to_addr, None)
            return jsonify({'success': False, 'error': '验证码尝试次数过多，请重新获取'}), 400
        if stored['code'] != code_input:
            stored['attempts'] += 1
            remaining = _RESET_CODE_MAX_ATTEMPTS - stored['attempts']
            return jsonify({'success': False, 'error': f'验证码错误，还有 {remaining} 次机会'}), 400

        # 验证通过，执行重置
        status, cleaned = _execute_reset()

        # 清掉验证码
        _RESET_CODE_STORE.pop(to_addr, None)

        # 触发 kernel 重新初始化（如果正在运行的话）
        try:
            init_jrvs()
        except Exception as e:
            print(f'[Reset] kernel 重初始化跳过: {e}')

        return jsonify({
            'success': status == 'OK' or status.startswith('OK'),
            'status': status,
            'cleaned': cleaned,
        })
    except Exception as e:
        print(f'[Reset] execute API 错误: {e}')
        return jsonify({'error': str(e)}), 500
