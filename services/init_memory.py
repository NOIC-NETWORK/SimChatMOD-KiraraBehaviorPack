# -*- coding: utf-8 -*-
"""Kirara 记忆库初始化脚本。

记忆库是 ChromaDB 向量库，属于运行时数据，不入版本库。新克隆下来需要先建好
目录骨架，宿主和桌宠才能直接跑起来：

    memories/kirara_memory/
        long_term/        # Hippo 长期记忆（hippo_long_term 集合）
        knowledge_base/   # 个性化知识库（kirara_knowledge_base 集合）

集合本身由运行时按需创建，这里只准备目录与空的记忆文本，避免预先写入的
集合配置与运行时使用的嵌入函数冲突。

用法：
    py services/init_memory.py    # 手动初始化
宿主首次初始化 JRVS 内核时也会调用 ensure_memory_layout()，保证开箱即跑。
两个函数均幂等，重复执行不会覆盖已有记忆。
"""

import os

SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(SERVICES_DIR)
MEMORIES_DIR = os.path.join(APP_DIR, "memories")
MEMORY_ROOT = os.path.join(MEMORIES_DIR, "kirara_memory")

# 子库目录 -> 说明
MEMORY_SUBDIRS = (
    ("long_term", "Hippo 长期记忆"),
    ("knowledge_base", "个性化知识库"),
)

# 缺失时补一个空文件即可正常启动的记忆文本
SEED_FILES = ("buffer.txt", "mem.txt")


def ensure_memory_layout():
    """创建记忆目录骨架与缺失的空记忆文件；返回本次新建的路径列表。"""
    created = []
    directories = [MEMORIES_DIR, MEMORY_ROOT]
    directories.extend(os.path.join(MEMORY_ROOT, name) for name, _ in MEMORY_SUBDIRS)
    for path in directories:
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            created.append(path)
    for name in SEED_FILES:
        path = os.path.join(MEMORIES_DIR, name)
        if not os.path.exists(path):
            open(path, "w", encoding="utf-8").close()
            created.append(path)
    return created


def init_memory_library():
    """目录骨架 + 打开 ChromaDB 持久化客户端，确认记忆库可用。"""
    created = ensure_memory_layout()
    try:
        import chromadb
    except Exception as error:
        print("[Init] chromadb 不可用，运行时将退化为简化记忆: %s" % error)
        return created
    for name, label in MEMORY_SUBDIRS:
        path = os.path.join(MEMORY_ROOT, name)
        try:
            chromadb.PersistentClient(path=path)
            print("[Init] 记忆库已就绪: %s (%s)" % (name, label))
        except Exception as error:
            print("[Init] 记忆库 %s 初始化失败: %s" % (name, error))
    return created


if __name__ == "__main__":
    new_paths = init_memory_library()
    for path in new_paths:
        print("[Init] 新建: %s" % os.path.relpath(path, APP_DIR))
    if not new_paths:
        print("[Init] 记忆目录已存在，无需创建")
    print("[Init] 记忆库根目录: %s" % MEMORY_ROOT)
